from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import Booking
from notifications.models import Notification
from .serializers import BookingSerializer
from django.http import JsonResponse

class NotificationInline(admin.TabularInline):
    model = Notification
    fields = ('message', 'notification_type', 'is_read', 'created_at')
    readonly_fields = ('message', 'notification_type', 'is_read', 'created_at')
    extra = 0
    can_delete = False


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('room', 'user', 'start_time', 'end_time', 'status', 'is_approved')
    list_filter = ('status', 'is_approved', 'created_at')
    search_fields = ('user__username', 'room__name')
    inlines = [NotificationInline]  # Include related notifications inline

    actions = ['approve_bookings', 'cancel_bookings']

    def save_model(self, request, obj, form, change):
        """
        Override save_model to validate the booking before saving.
        """
        try:
            obj.clean()  # Call validation before saving
            super().save_model(request, obj, form, change)
        except ValidationError as e:
            self.message_user(request, f"Error: {e.message}", level="error")

    def approve_bookings(self, request, queryset):
        """
        Action to approve selected bookings.
        """
        for booking in queryset:
            try:
                booking.status = 'approved'
                booking.is_approved = True
                booking.save()
                self.message_user(request, f"Booking for {booking.room.name} approved successfully.")
            except ValidationError as e:
                self.message_user(request, f"Error approving booking for {booking.room.name}: {e.message}", level="error")

    approve_bookings.short_description = "Approve selected bookings"

    def cancel_bookings(self, request, queryset):
        """
        Action to cancel selected bookings.
        """
        for booking in queryset:
            try:
                booking.status = 'canceled'
                booking.is_approved = False
                booking.save()
                self.message_user(request, f"Booking for {booking.room.name} canceled successfully.")
            except ValidationError as e:
                self.message_user(request, f"Error canceling booking for {booking.room.name}: {e.message}", level="error")

    cancel_bookings.short_description = "Cancel selected bookings"

def admin_bookings(request):
    """
    Handle admin bookings. This is a placeholder for demonstration.
    """
    bookings = Booking.objects.all()
    serializer = BookingSerializer(bookings, many=True)
    return JsonResponse(serializer.data, safe=False)