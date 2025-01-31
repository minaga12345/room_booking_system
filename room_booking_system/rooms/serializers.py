#rooms/serializers.py
from rest_framework import serializers
from django.utils import timezone  # Import timezone
from .models import Room, UsageLog
from bookings.serializers import BookingSerializer  # Import BookingSerializer

class RoomSerializer(serializers.ModelSerializer):
    bookings = serializers.SerializerMethodField()

    def get_bookings(self, obj):
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timezone.timedelta(days=1)
        bookings = obj.bookings.filter(
            start_time__gte=today_start,
            start_time__lt=today_end
        )
        return BookingSerializer(bookings, many=True).data

    class Meta:
        model = Room
        fields = '__all__'

class UsageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsageLog
        fields = "__all__"

