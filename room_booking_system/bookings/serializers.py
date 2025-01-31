from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Booking, Room

User = get_user_model()

class BookingSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)  # Display username in responses
    room = serializers.StringRelatedField(read_only=True)  # Display room name in responses
    user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), write_only=True)  # Accept user ID
    room_id = serializers.PrimaryKeyRelatedField(queryset=Room.objects.all(), write_only=True)  # Accept room ID
    room_name = serializers.CharField(source='room.name', read_only=True)  # Explicitly add room name

    class Meta:
        model = Booking
        fields = '__all__'

    def create(self, validated_data):
        """
        Handle the creation of a booking.
        """
        user = validated_data.pop('user_id')
        room = validated_data.pop('room_id')
        # Pass validation before saving
        booking = Booking(user=user, room=room, **validated_data)
        booking.clean()  # Call validation logic
        booking.save()
        return booking

    def validate(self, data):
        """
        Validate booking data to prevent overlaps and ensure logical times.
        """
        room = data.get('room_id')
        start_time = data.get('start_time')
        end_time = data.get('end_time')

        print(f"Validating booking: room={room}, start_time={start_time}, end_time={end_time}")

        # Check for overlapping bookings
        overlapping = Booking.objects.filter(
            room=room,
            start_time__lt=end_time,
            end_time__gt=start_time,
        ).exists()

        if overlapping:
            print(f"Overlapping booking detected for room={room}, start_time={start_time}, end_time={end_time}")
            raise serializers.ValidationError({"non_field_errors": ["Room is already booked for this time slot."]})

        # Validate start and end times
        if start_time >= end_time:
            print(f"Invalid time range: start_time={start_time}, end_time={end_time}")
            raise serializers.ValidationError({"non_field_errors": ["Start time must be earlier than end time."]})

        return data
