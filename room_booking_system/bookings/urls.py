from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BookingViewSet
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .admin import admin_bookings

router = DefaultRouter()
router.register(r'', BookingViewSet, basename="booking")  # Removed the 'bookings' prefix

urlpatterns = [
    path('', include(router.urls)),
    path('api/users/', include('users.urls')),  # Users app
    path('api/rooms/', include('rooms.urls')),  # Rooms app
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('admin/bookings/', admin_bookings, name='admin-bookings'),
]
