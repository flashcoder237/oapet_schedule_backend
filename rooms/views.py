# rooms/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Avg, Count, Min, Max
from django.db import models

from core.mixins import ImportExportMixin
from .models import (
    Building, RoomType, Room, RoomEquipment, RoomAvailability,
    RoomBooking, MaintenanceRecord
)
from .serializers import (
    BuildingSerializer, RoomTypeSerializer, RoomSerializer, RoomEquipmentSerializer,
    RoomAvailabilitySerializer, RoomBookingSerializer, MaintenanceRecordSerializer,
    RoomDetailSerializer, RoomSearchSerializer
)


class BuildingViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des bâtiments"""
    queryset = Building.objects.all()
    serializer_class = BuildingSerializer
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'name', 'code', 'address', 'floors', 'description', 'is_active']
    import_fields = ['name', 'code', 'address', 'floors', 'description']

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class RoomTypeViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des types de salles"""
    queryset = RoomType.objects.all()
    serializer_class = RoomTypeSerializer
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'name', 'description']
    import_fields = ['name', 'description']


class RoomViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des salles"""
    queryset = Room.objects.all()
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'code', 'name', 'building', 'room_type', 'floor', 'capacity', 'has_projector', 'has_computer', 'is_laboratory', 'is_active']
    import_fields = ['code', 'name', 'building', 'room_type', 'floor', 'capacity', 'has_projector', 'has_computer', 'is_laboratory']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return RoomDetailSerializer
        return RoomSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset().filter(is_active=True)
        
        # Filtres de recherche
        building_id = self.request.query_params.get('building')
        if building_id:
            queryset = queryset.filter(building_id=building_id)
        
        room_type_id = self.request.query_params.get('room_type')
        if room_type_id:
            queryset = queryset.filter(room_type_id=room_type_id)
        
        min_capacity = self.request.query_params.get('min_capacity')
        if min_capacity:
            queryset = queryset.filter(capacity__gte=min_capacity)
        
        max_capacity = self.request.query_params.get('max_capacity')
        if max_capacity:
            queryset = queryset.filter(capacity__lte=max_capacity)
        
        # Filtres d'équipements
        if self.request.query_params.get('has_projector') == 'true':
            queryset = queryset.filter(has_projector=True)
        
        if self.request.query_params.get('has_computer') == 'true':
            queryset = queryset.filter(has_computer=True)
        
        if self.request.query_params.get('is_laboratory') == 'true':
            queryset = queryset.filter(is_laboratory=True)
        
        return queryset
    
    @action(detail=False, methods=['post'])
    def search_available(self, request):
        """Recherche de salles disponibles pour un créneau donné"""
        serializer = RoomSearchSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        queryset = self.get_queryset()
        
        # Appliquer les filtres de capacité et équipements
        if 'min_capacity' in data:
            queryset = queryset.filter(capacity__gte=data['min_capacity'])
        
        if 'has_projector' in data:
            queryset = queryset.filter(has_projector=data['has_projector'])
        
        if 'has_computer' in data:
            queryset = queryset.filter(has_computer=data['has_computer'])
        
        # Filtrer par disponibilité si spécifié
        if 'day_of_week' in data and 'period' in data:
            available_rooms = []
            for room in queryset:
                availability = RoomAvailability.objects.filter(
                    room=room,
                    day_of_week=data['day_of_week'],
                    period=data['period'],
                    is_available=True
                ).exists()
                
                if availability:
                    available_rooms.append(room)
            
            queryset = available_rooms
        
        serializer = RoomSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques des salles"""
        total_rooms = Room.objects.filter(is_active=True).count()
        
        # Par type de salle
        by_type = Room.objects.filter(is_active=True).values(
            'room_type__name'
        ).annotate(count=Count('id'))
        
        # Par bâtiment
        by_building = Room.objects.filter(is_active=True).values(
            'building__name', 'building__code'
        ).annotate(count=Count('id'))
        
        # Capacités
        capacity_stats = Room.objects.filter(is_active=True).aggregate(
            avg_capacity=Avg('capacity'),
            min_capacity=Min('capacity'),
            max_capacity=Max('capacity')
        )
        
        # Équipements
        equipment_stats = {
            'with_projector': Room.objects.filter(is_active=True, has_projector=True).count(),
            'with_computer': Room.objects.filter(is_active=True, has_computer=True).count(),
            'laboratories': Room.objects.filter(is_active=True, is_laboratory=True).count(),
            'with_audio_system': Room.objects.filter(is_active=True, has_audio_system=True).count()
        }
        
        return Response({
            'total_rooms': total_rooms,
            'by_type': list(by_type),
            'by_building': list(by_building),
            'capacity_stats': capacity_stats,
            'equipment_stats': equipment_stats
        })
    
    @action(detail=True, methods=['get'])
    def occupancy(self, request, pk=None):
        """Taux d'occupation d'une salle"""
        from schedules.models import ScheduleSession
        room = self.get_object()
        
        # Sessions programmées pour cette salle
        sessions = ScheduleSession.objects.filter(
            room=room,
            is_cancelled=False
        ).count()
        
        # Créneaux disponibles dans la semaine (estimation)
        available_slots = 50  # 5 jours * 10 créneaux par jour
        occupancy_rate = (sessions / available_slots) * 100 if available_slots > 0 else 0
        
        return Response({
            'room': room.code,
            'total_sessions': sessions,
            'available_slots': available_slots,
            'occupancy_rate': round(occupancy_rate, 2)
        })


class RoomEquipmentViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des équipements"""
    queryset = RoomEquipment.objects.all()
    serializer_class = RoomEquipmentSerializer
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'room', 'equipment_type', 'quantity', 'condition', 'notes']
    import_fields = ['room', 'equipment_type', 'quantity', 'condition', 'notes']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        room_id = self.request.query_params.get('room')
        if room_id:
            queryset = queryset.filter(room_id=room_id)
        return queryset


class RoomAvailabilityViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des disponibilités"""
    queryset = RoomAvailability.objects.all()
    serializer_class = RoomAvailabilitySerializer
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'room', 'day_of_week', 'period', 'is_available', 'notes']
    import_fields = ['room', 'day_of_week', 'period', 'is_available', 'notes']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        room_id = self.request.query_params.get('room')
        if room_id:
            queryset = queryset.filter(room_id=room_id)
        
        day_of_week = self.request.query_params.get('day')
        if day_of_week:
            queryset = queryset.filter(day_of_week=day_of_week)
        
        return queryset


class RoomBookingViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des réservations"""
    queryset = RoomBooking.objects.all()
    serializer_class = RoomBookingSerializer
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'room', 'date', 'start_time', 'end_time', 'booking_type', 'purpose', 'is_approved']
    import_fields = ['room', 'date', 'start_time', 'end_time', 'booking_type', 'purpose']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        room_id = self.request.query_params.get('room')
        if room_id:
            queryset = queryset.filter(room_id=room_id)
        
        booking_type = self.request.query_params.get('type')
        if booking_type:
            queryset = queryset.filter(booking_type=booking_type)
        
        approved_only = self.request.query_params.get('approved_only')
        if approved_only == 'true':
            queryset = queryset.filter(is_approved=True)
        
        return queryset.order_by('-date', '-start_time')
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approuve une réservation"""
        booking = self.get_object()
        booking.is_approved = True
        booking.approved_by = request.user.username
        booking.save()
        
        return Response({
            'message': 'Réservation approuvée avec succès'
        }, status=status.HTTP_200_OK)


class MaintenanceRecordViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion de la maintenance"""
    queryset = MaintenanceRecord.objects.all()
    serializer_class = MaintenanceRecordSerializer
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'room', 'maintenance_type', 'date_scheduled', 'date_completed', 'is_completed', 'notes']
    import_fields = ['room', 'maintenance_type', 'date_scheduled', 'notes']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        room_id = self.request.query_params.get('room')
        if room_id:
            queryset = queryset.filter(room_id=room_id)
        
        maintenance_type = self.request.query_params.get('type')
        if maintenance_type:
            queryset = queryset.filter(maintenance_type=maintenance_type)
        
        completed_only = self.request.query_params.get('completed_only')
        if completed_only == 'true':
            queryset = queryset.filter(is_completed=True)
        
        return queryset.order_by('-date_scheduled')
    
    @action(detail=True, methods=['post'])
    def mark_completed(self, request, pk=None):
        """Marque une maintenance comme terminée"""
        maintenance = self.get_object()
        
        from datetime import date
        maintenance.is_completed = True
        maintenance.date_completed = date.today()
        maintenance.notes = request.data.get('notes', maintenance.notes)
        maintenance.save()
        
        return Response({
            'message': 'Maintenance marquée comme terminée'
        }, status=status.HTTP_200_OK)
