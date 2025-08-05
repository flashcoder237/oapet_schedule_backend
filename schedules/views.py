# schedules/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction, models
from django.utils import timezone
from django.db.models import Count, Avg

from .models import (
    AcademicPeriod, TimeSlot, Schedule, ScheduleSession, Conflict,
    ScheduleOptimization, ScheduleTemplate, ScheduleConstraint, ScheduleExport
)
from .serializers import (
    AcademicPeriodSerializer, TimeSlotSerializer, ScheduleSerializer, ScheduleSessionSerializer,
    ConflictSerializer, ScheduleOptimizationSerializer, ScheduleTemplateSerializer,
    ScheduleConstraintSerializer, ScheduleExportSerializer, ScheduleDetailSerializer,
    ScheduleCreateSerializer, WeeklyScheduleSerializer
)


class AcademicPeriodViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des périodes académiques"""
    queryset = AcademicPeriod.objects.all()
    serializer_class = AcademicPeriodSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def set_current(self, request, pk=None):
        """Définit une période comme courante"""
        period = self.get_object()
        
        with transaction.atomic():
            # Désactiver toutes les autres périodes
            AcademicPeriod.objects.filter(is_current=True).update(is_current=False)
            # Activer la période sélectionnée
            period.is_current = True
            period.save()
        
        return Response({
            'message': f'Période {period.name} définie comme courante'
        }, status=status.HTTP_200_OK)


class TimeSlotViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des créneaux horaires"""
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().filter(is_active=True)
        
        day_of_week = self.request.query_params.get('day')
        if day_of_week:
            queryset = queryset.filter(day_of_week=day_of_week)
        
        return queryset.order_by('day_of_week', 'start_time')


class ScheduleViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des emplois du temps"""
    queryset = Schedule.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ScheduleDetailSerializer
        elif self.action == 'create':
            return ScheduleCreateSerializer
        return ScheduleSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtrer par période académique
        academic_period_id = self.request.query_params.get('academic_period')
        if academic_period_id:
            queryset = queryset.filter(academic_period_id=academic_period_id)
        
        # Filtrer par curriculum
        curriculum_id = self.request.query_params.get('curriculum')
        if curriculum_id:
            queryset = queryset.filter(curriculum_id=curriculum_id)
        
        # Filtrer par statut de publication
        published_only = self.request.query_params.get('published_only')
        if published_only == 'true':
            queryset = queryset.filter(is_published=True)
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Publie un emploi du temps"""
        schedule = self.get_object()
        
        # Vérifier qu'il n'y a pas de conflits critiques
        critical_conflicts = Conflict.objects.filter(
            schedule_session__schedule=schedule,
            severity='critical',
            is_resolved=False
        ).count()
        
        if critical_conflicts > 0:
            return Response({
                'error': f'Impossible de publier: {critical_conflicts} conflits critiques non résolus'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        schedule.is_published = True
        schedule.published_at = timezone.now()
        schedule.save()
        
        return Response({
            'message': 'Emploi du temps publié avec succès'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def unpublish(self, request, pk=None):
        """Dépublie un emploi du temps"""
        schedule = self.get_object()
        schedule.is_published = False
        schedule.save()
        
        return Response({
            'message': 'Emploi du temps dépublié avec succès'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def weekly_view(self, request, pk=None):
        """Vue hebdomadaire de l'emploi du temps"""
        schedule = self.get_object()
        sessions = schedule.sessions.all().select_related(
            'course', 'teacher', 'room', 'time_slot'
        )
        
        # Organiser par jour de la semaine
        weekly_data = {
            'monday': [],
            'tuesday': [],
            'wednesday': [],
            'thursday': [],
            'friday': [],
            'saturday': [],
            'sunday': []
        }
        
        day_mapping = {
            'monday': 'monday',
            'tuesday': 'tuesday', 
            'wednesday': 'wednesday',
            'thursday': 'thursday',
            'friday': 'friday',
            'saturday': 'saturday',
            'sunday': 'sunday'
        }
        
        for session in sessions:
            day = session.time_slot.day_of_week
            if day in day_mapping:
                weekly_data[day_mapping[day]].append(
                    ScheduleSessionSerializer(session).data
                )
        
        serializer = WeeklyScheduleSerializer(weekly_data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def detect_conflicts(self, request, pk=None):
        """Détecte les conflits dans un emploi du temps"""
        schedule = self.get_object()
        conflicts_found = []
        
        sessions = schedule.sessions.all()
        
        for session in sessions:
            # Vérifier les conflits d'enseignant
            teacher_conflicts = ScheduleSession.objects.filter(
                teacher=session.teacher,
                time_slot=session.time_slot,
                schedule__academic_period=schedule.academic_period
            ).exclude(id=session.id)
            
            for conflict_session in teacher_conflicts:
                conflict, created = Conflict.objects.get_or_create(
                    schedule_session=session,
                    conflict_type='teacher_double_booking',
                    conflicting_session=conflict_session,
                    defaults={
                        'description': f'Enseignant {session.teacher} déjà occupé',
                        'severity': 'high'
                    }
                )
                if created:
                    conflicts_found.append(conflict)
            
            # Vérifier les conflits de salle
            room_conflicts = ScheduleSession.objects.filter(
                room=session.room,
                time_slot=session.time_slot,
                schedule__academic_period=schedule.academic_period
            ).exclude(id=session.id)
            
            for conflict_session in room_conflicts:
                conflict, created = Conflict.objects.get_or_create(
                    schedule_session=session,
                    conflict_type='room_double_booking',
                    conflicting_session=conflict_session,
                    defaults={
                        'description': f'Salle {session.room} déjà occupée',
                        'severity': 'critical'
                    }
                )
                if created:
                    conflicts_found.append(conflict)
        
        return Response({
            'conflicts_detected': len(conflicts_found),
            'conflicts': ConflictSerializer(conflicts_found, many=True).data
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques générales des emplois du temps"""
        total_schedules = Schedule.objects.count()
        published_schedules = Schedule.objects.filter(is_published=True).count()
        
        # Sessions par type
        session_types = ScheduleSession.objects.values('session_type').annotate(
            count=Count('id')
        )
        
        # Conflits par sévérité
        conflicts_by_severity = Conflict.objects.filter(is_resolved=False).values('severity').annotate(
            count=Count('id')
        )
        
        # Emplois du temps par période académique
        by_period = Schedule.objects.values(
            'academic_period__name'
        ).annotate(count=Count('id'))
        
        return Response({
            'total_schedules': total_schedules,
            'published_schedules': published_schedules,
            'draft_schedules': total_schedules - published_schedules,
            'session_types': list(session_types),
            'unresolved_conflicts': list(conflicts_by_severity),
            'by_academic_period': list(by_period)
        })


class ScheduleSessionViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des sessions d'emploi du temps"""
    queryset = ScheduleSession.objects.all()
    serializer_class = ScheduleSessionSerializer
    permission_classes = []  # Temporairement désactivé pour les tests
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        schedule_id = self.request.query_params.get('schedule')
        if schedule_id:
            queryset = queryset.filter(schedule_id=schedule_id)
        
        course_id = self.request.query_params.get('course')
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        
        teacher_id = self.request.query_params.get('teacher')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)
        
        room_id = self.request.query_params.get('room')
        if room_id:
            queryset = queryset.filter(room_id=room_id)
        
        # Filtrage par curriculum
        curriculum = self.request.query_params.get('curriculum')
        if curriculum:
            queryset = queryset.filter(schedule__curriculum__code=curriculum)
        
        # Filtrage par date spécifique
        date_param = self.request.query_params.get('date')
        if date_param:
            try:
                from datetime import datetime
                target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
                # Filtrer par specific_date ou par day_of_week si pas de date spécifique
                queryset = queryset.filter(
                    models.Q(specific_date=target_date) |
                    models.Q(
                        specific_date__isnull=True,
                        time_slot__day_of_week=target_date.strftime('%A').lower()
                    )
                )
            except ValueError:
                pass  # Ignorer les dates mal formatées
        
        return queryset.order_by('time_slot__day_of_week', 'time_slot__start_time')


class ConflictViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des conflits"""
    queryset = Conflict.objects.all()
    serializer_class = ConflictSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        schedule_id = self.request.query_params.get('schedule')
        if schedule_id:
            queryset = queryset.filter(schedule_session__schedule_id=schedule_id)
        
        severity = self.request.query_params.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        
        unresolved_only = self.request.query_params.get('unresolved_only')
        if unresolved_only == 'true':
            queryset = queryset.filter(is_resolved=False)
        
        return queryset.order_by('-detected_at')
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Marque un conflit comme résolu"""
        conflict = self.get_object()
        
        conflict.is_resolved = True
        conflict.resolved_at = timezone.now()
        conflict.resolution_notes = request.data.get('resolution_notes', '')
        conflict.save()
        
        return Response({
            'message': 'Conflit marqué comme résolu'
        }, status=status.HTTP_200_OK)


class ScheduleOptimizationViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des optimisations"""
    queryset = ScheduleOptimization.objects.all()
    serializer_class = ScheduleOptimizationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        schedule_id = self.request.query_params.get('schedule')
        if schedule_id:
            queryset = queryset.filter(schedule_id=schedule_id)
        
        return queryset.order_by('-started_at')
    
    def perform_create(self, serializer):
        serializer.save(started_by=self.request.user)


class ScheduleTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des templates"""
    queryset = ScheduleTemplate.objects.all()
    serializer_class = ScheduleTemplateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().filter(is_active=True)
        
        curriculum_id = self.request.query_params.get('curriculum')
        if curriculum_id:
            queryset = queryset.filter(curriculum_id=curriculum_id)
        
        level = self.request.query_params.get('level')
        if level:
            queryset = queryset.filter(level=level)
        
        return queryset.order_by('name')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ScheduleConstraintViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des contraintes"""
    queryset = ScheduleConstraint.objects.all()
    serializer_class = ScheduleConstraintSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().filter(is_active=True)
        
        schedule_id = self.request.query_params.get('schedule')
        if schedule_id:
            queryset = queryset.filter(schedule_id=schedule_id)
        
        constraint_type = self.request.query_params.get('type')
        if constraint_type:
            queryset = queryset.filter(constraint_type=constraint_type)
        
        return queryset.order_by('priority', 'name')


class ScheduleExportViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des exports"""
    queryset = ScheduleExport.objects.all()
    serializer_class = ScheduleExportSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        schedule_id = self.request.query_params.get('schedule')
        if schedule_id:
            queryset = queryset.filter(schedule_id=schedule_id)
        
        export_format = self.request.query_params.get('format')
        if export_format:
            queryset = queryset.filter(export_format=export_format)
        
        return queryset.order_by('-exported_at')
    
    def perform_create(self, serializer):
        serializer.save(exported_by=self.request.user)
