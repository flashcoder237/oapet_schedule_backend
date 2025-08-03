# rooms/serializers.py
from rest_framework import serializers
from .models import (
    Building, RoomType, Room, RoomEquipment, RoomAvailability,
    RoomBooking, MaintenanceRecord
)


class BuildingSerializer(serializers.ModelSerializer):
    rooms_count = serializers.IntegerField(source='rooms.count', read_only=True)
    active_rooms_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Building
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')
    
    def get_active_rooms_count(self, obj):
        return obj.rooms.filter(is_active=True).count()


class RoomTypeSerializer(serializers.ModelSerializer):
    rooms_count = serializers.IntegerField(source='rooms.count', read_only=True)
    
    class Meta:
        model = RoomType
        fields = '__all__'


class RoomEquipmentSerializer(serializers.ModelSerializer):
    room_code = serializers.CharField(source='room.code', read_only=True)
    
    class Meta:
        model = RoomEquipment
        fields = '__all__'


class RoomSerializer(serializers.ModelSerializer):
    building_name = serializers.CharField(source='building.name', read_only=True)
    building_code = serializers.CharField(source='building.code', read_only=True)
    room_type_name = serializers.CharField(source='room_type.name', read_only=True)
    equipment_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = Room
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')
    
    def get_equipment_summary(self, obj):
        """Résumé des équipements de la salle"""
        equipment = []
        if obj.has_projector:
            equipment.append('Projecteur')
        if obj.has_computer:
            equipment.append('Ordinateur')
        if obj.has_whiteboard:
            equipment.append('Tableau blanc')
        if obj.has_blackboard:
            equipment.append('Tableau noir')
        if obj.has_air_conditioning:
            equipment.append('Climatisation')
        if obj.has_audio_system:
            equipment.append('Système audio')
        if obj.is_laboratory:
            equipment.append(f'Laboratoire {obj.laboratory_type}')
        
        return equipment


class RoomDetailSerializer(RoomSerializer):
    """Serializer détaillé pour les salles avec équipements et disponibilités"""
    additional_equipment = RoomEquipmentSerializer(many=True, read_only=True)
    availability_summary = serializers.SerializerMethodField()
    upcoming_bookings = serializers.SerializerMethodField()
    
    def get_availability_summary(self, obj):
        """Résumé de la disponibilité de la salle"""
        availability = obj.availability.filter(is_available=True)
        return {
            'total_available_slots': availability.count(),
            'available_days': list(availability.values_list('day_of_week', flat=True).distinct())
        }
    
    def get_upcoming_bookings(self, obj):
        """Prochaines réservations de la salle"""
        from datetime import date
        bookings = obj.bookings.filter(
            date__gte=date.today(),
            is_approved=True
        ).order_by('date', 'start_time')[:5]
        
        return [{
            'title': booking.title,
            'date': booking.date,
            'start_time': booking.start_time,
            'end_time': booking.end_time,
            'organizer': booking.organizer_name
        } for booking in bookings]


class RoomAvailabilitySerializer(serializers.ModelSerializer):
    room_code = serializers.CharField(source='room.code', read_only=True)
    room_name = serializers.CharField(source='room.name', read_only=True)
    day_display = serializers.CharField(source='get_day_of_week_display', read_only=True)
    
    class Meta:
        model = RoomAvailability
        fields = '__all__'


class RoomBookingSerializer(serializers.ModelSerializer):
    room_code = serializers.CharField(source='room.code', read_only=True)
    room_name = serializers.CharField(source='room.name', read_only=True)
    booking_type_display = serializers.CharField(source='get_booking_type_display', read_only=True)
    duration = serializers.SerializerMethodField()
    
    class Meta:
        model = RoomBooking
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')
    
    def get_duration(self, obj):
        """Calcule la durée de la réservation en minutes"""
        if obj.start_time and obj.end_time:
            start = obj.start_time
            end = obj.end_time
            duration = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)
            return duration
        return None


class MaintenanceRecordSerializer(serializers.ModelSerializer):
    room_code = serializers.CharField(source='room.code', read_only=True)
    room_name = serializers.CharField(source='room.name', read_only=True)
    maintenance_type_display = serializers.CharField(source='get_maintenance_type_display', read_only=True)
    duration = serializers.SerializerMethodField()
    
    class Meta:
        model = MaintenanceRecord
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')
    
    def get_duration(self, obj):
        """Calcule la durée de la maintenance en jours"""
        if obj.date_scheduled and obj.date_completed:
            duration = obj.date_completed - obj.date_scheduled
            return duration.days
        return None


class RoomSearchSerializer(serializers.Serializer):
    """Serializer pour la recherche de salles"""
    min_capacity = serializers.IntegerField(required=False)
    max_capacity = serializers.IntegerField(required=False)
    building = serializers.CharField(required=False)
    room_type = serializers.CharField(required=False)
    floor = serializers.CharField(required=False)
    has_projector = serializers.BooleanField(required=False)
    has_computer = serializers.BooleanField(required=False)
    has_air_conditioning = serializers.BooleanField(required=False)
    is_laboratory = serializers.BooleanField(required=False)
    is_accessible = serializers.BooleanField(required=False)
    is_available = serializers.BooleanField(required=False)
    day_of_week = serializers.CharField(required=False)
    period = serializers.CharField(required=False)


class RoomStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques des salles"""
    total_rooms = serializers.IntegerField()
    rooms_by_building = serializers.DictField()
    rooms_by_type = serializers.DictField()
    rooms_by_floor = serializers.DictField()
    average_capacity = serializers.FloatField()
    total_capacity = serializers.IntegerField()
    equipment_stats = serializers.DictField()
    utilization_rate = serializers.FloatField()


class BuildingStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques des bâtiments"""
    total_buildings = serializers.IntegerField()
    total_floors = serializers.IntegerField()
    rooms_distribution = serializers.DictField()
    capacity_distribution = serializers.DictField()


class AvailabilityStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques de disponibilité"""
    availability_by_day = serializers.DictField()
    availability_by_period = serializers.DictField()
    most_busy_rooms = serializers.ListField()
    least_busy_rooms = serializers.ListField()