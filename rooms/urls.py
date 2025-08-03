# rooms/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BuildingViewSet, RoomTypeViewSet, RoomViewSet, RoomEquipmentViewSet,
    RoomAvailabilityViewSet, RoomBookingViewSet, MaintenanceRecordViewSet
)

router = DefaultRouter()
router.register(r'buildings', BuildingViewSet)
router.register(r'room-types', RoomTypeViewSet)
router.register(r'rooms', RoomViewSet)
router.register(r'equipment', RoomEquipmentViewSet)
router.register(r'availability', RoomAvailabilityViewSet)
router.register(r'bookings', RoomBookingViewSet)
router.register(r'maintenance', MaintenanceRecordViewSet)

urlpatterns = [
    path('', include(router.urls)),
]