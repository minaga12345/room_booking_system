from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from .models import Booking
from .serializers import BookingSerializer
from penalties.models import Penalty
from datetime import date
from django.utils import timezone
from notifications.models import Notification
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import api_view

class BookingPagination(PageNumberPagination):
    page_size = 5  # Limit to 5 bookings per page


class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all().order_by('-status')
    serializer_class = BookingSerializer
    pagination_class = BookingPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'user__username', 'room__name']  # Fields for filtering
    search_fields = ['user__username', 'room__name']  # Enable search functionality

    @api_view(['GET'])
    def admin_bookings(request):
        bookings = Booking.objects.all().order_by('-start_time')  # Fetch all bookings sorted by start_time (descending)
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def my_bookings(self, request):
        """
        Fetch bookings for the currently logged-in user.
        """
        user = request.user
        user_bookings = Booking.objects.filter(user=user)
        serializer = self.get_serializer(user_bookings, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='count-pending')
    def count_pending(self, request):
        """
        Return the count of bookings with status 'pending'.
        Allow filtering by user and room.
        """
        filters = {}
        user = request.query_params.get('user')
        room = request.query_params.get('room')

        if user:
            filters['user__username'] = user  # Filter by username
        if room:
            filters['room__name'] = room  # Filter by room name

        count = Booking.objects.filter(status='pending', **filters).count()
        return Response({'remaining_approvals': count})

    def get_queryset(self):
        queryset = super().get_queryset()
        filters = {}

        status = self.request.query_params.get('status')
        user = self.request.query_params.get('user')
        room = self.request.query_params.get('room')

        if status:
            filters['status'] = status
        if user:
            filters['user__username'] = user
        if room:
            filters['room__name'] = room

        print(f"Filters applied: {filters}")
        queryset = queryset.filter(**filters)
        print(f"Filtered queryset: {queryset}")
        return queryset

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """
        Approve a pending booking and notify the user.
        """
        try:
            booking = self.get_object()
            if booking.status == 'approved':
                return Response({"message": "Booking is already approved."}, status=400)

            booking.status = 'approved'
            booking.is_approved = True
            booking.save()

            Notification.objects.create(
                user=booking.user,
                message=f"Your booking for {booking.room.name} has been approved.",
                notification_type='booking_update'
            )
            return Response({"message": "Booking approved successfully."}, status=200)
        except Exception as e:
            return Response({"error": f"Error approving booking: {str(e)}"}, status=500)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def cancel(self, request, pk=None):
        """
        Cancel a booking and apply penalties if applicable.
        """
        try:
            booking = self.get_object()
            if booking.status == 'canceled':
                return Response({"message": "Booking is already canceled."}, status=400)

            if booking.status not in ['canceled', 'checked_in']:
                self.apply_penalty(booking, "Canceled by admin.")

            booking.status = 'canceled'
            booking.save()

            Notification.objects.create(
                user=booking.user,
                message=f"Your booking for {booking.room.name} has been canceled.",
                notification_type='booking_update'
            )
            return Response({"message": "Booking canceled successfully."}, status=200)
        except Exception as e:
            return Response({"error": f"Error canceling booking: {str(e)}"}, status=500)

    def check_for_penalty(self, booking):
        """
        Check if a penalty should be applied for late cancellation or no-show.
        """
        if booking.end_time < timezone.now() and not booking.is_approved:
            penalty, created = Penalty.objects.get_or_create(
                user=booking.user,
                booking=booking,
                reason="Late cancellation or no-show",
                defaults={
                    "amount": 50.00,
                    "status": "unpaid"
                }
            )
            if created:
                Notification.objects.create(
                    user=booking.user,
                    message=f"A penalty of ${penalty.amount} has been imposed for {penalty.reason}.",
                    notification_type='penalty_reminder'
                )

    def destroy(self, request, *args, **kwargs):
        """
        Apply penalty for late cancellation before deleting a booking.
        """
        booking = self.get_object()
        self.check_for_penalty(booking)
        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        """
        Validate and create a new booking.
        """
        try:
            booking = serializer.save()

            # Send notification
            Notification.objects.create(
                user=booking.user,
                message=f"Your booking for {booking.room.name} has been successfully created.",
                notification_type='booking_update',
            )
        except Exception as e:
            print(f"Error during booking creation: {e}")
            raise ValidationError({"detail": f"Booking creation failed: {e}"})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def check_in(self, request, pk=None):
        """
        Mark a booking as checked in and notify the user.
        """
        try:
            booking = self.get_object()

            # Ensure the logged-in user is the owner of the booking
            if booking.user != request.user:
                raise PermissionDenied("You do not have permission to check in for this booking.")

            # Ensure the booking is approved and within the valid check-in period
            if booking.status != 'approved':
                return Response({"message": "Only approved bookings can be checked in."}, status=400)

            current_time = timezone.now()
            if current_time < booking.start_time or current_time > booking.end_time:
                return Response({"message": "Check-in is only allowed during the booking period."}, status=400)

            # Update the booking status to checked_in
            booking.status = 'checked_in'
            booking.save()
            print(f"Booking {booking.id} status updated to 'checked_in'.")

            # Create a notification for the user
            Notification.objects.create(
                user=booking.user,
                message=f"You have successfully checked in for your booking at {booking.room.name}.",
                notification_type='booking_update'
            )

            return Response({"message": "Check-in successful."}, status=200)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=403)
        except Exception as e:
            return Response({"error": f"Error during check-in: {str(e)}"}, status=500)
        
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def check_out(self, request, pk=None):
        """
        Handle check-out for a booking. Apply penalties for overstaying.
        """
        try:
            booking = self.get_object()
            print(f"Debug: Booking {booking.id} fetched successfully.")

            # Ensure the logged-in user is the owner of the booking
            if booking.user != request.user:
                raise PermissionDenied("You do not have permission to check out for this booking.")

            # Ensure the booking is checked in before checking out
            if booking.status != 'checked_in':
                return Response({"message": "Only checked-in bookings can be checked out."}, status=400)

            current_time = timezone.now()
            print(f"Debug: Current time is {current_time}, Booking end time is {booking.end_time}.")

            # Apply penalty if user overstayed
            if current_time > booking.end_time:
                self.apply_penalty(booking, reason="Overstay")
                penalty_amount = booking.calculate_penalty()
                print(f"Debug: Penalty applied for overstaying. Amount: {penalty_amount}.")

                penalty_message = f"A penalty of ${penalty_amount} has been imposed for overstaying."
                Notification.objects.create(
                    user=booking.user,
                    message=penalty_message,
                    notification_type='penalty_reminder',
                )
                return Response(
                    {"message": "Check-out successful with penalty.", "penalty_imposed": True, "penalty_amount": penalty_amount},
                    status=200,
                )

            # Update the booking status to 'completed' or a valid status
            booking.status = 'completed'  # Ensure this matches STATUS_CHOICES
            booking.save()
            print(f"Debug: Booking {booking.id} status updated to 'completed'.")

            # Create a notification for the user
            Notification.objects.create(
                user=booking.user,
                message=f"You have successfully checked out from your booking at {booking.room.name}.",
                notification_type='booking_update'
            )
            print(f"Debug: Notification sent for booking {booking.id}.")

            return Response({"message": "Check-out successful.", "penalty_imposed": False}, status=200)
        except PermissionDenied as e:
            print(f"Error: {str(e)}")
            return Response({"error": str(e)}, status=403)
        except Exception as e:
            print(f"Error during check-out: {str(e)}")
            return Response({"error": f"Error during check-out: {str(e)}"}, status=500)




    def apply_penalty(self, booking, reason="Late cancellation or no-show"):
        """
        Apply penalty to the user for specific reasons.
        """
        penalty, created = Penalty.objects.get_or_create(
            user=booking.user,
            booking=booking,
            reason=reason,
            defaults={
                "amount": booking.calculate_penalty(),
                "status": "unpaid"
            }
        )
        if created:
            Notification.objects.create(
                user=booking.user,
                message=f"A penalty of ${penalty.amount} has been imposed for {penalty.reason}.",
                notification_type='penalty_reminder'
            )
