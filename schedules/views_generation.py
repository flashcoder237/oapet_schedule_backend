# schedules/views_generation.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import datetime

from .models import (
    Schedule, ScheduleGenerationConfig, SessionOccurrence,
    ScheduleSession, Room, Teacher
)
from .serializers import (
    ScheduleGenerationConfigSerializer,
    ScheduleGenerationConfigCreateSerializer,
    SessionOccurrenceSerializer,
    SessionOccurrenceListSerializer,
    SessionOccurrenceCreateSerializer,
    SessionOccurrenceCancelSerializer,
    SessionOccurrenceRescheduleSerializer,
    SessionOccurrenceModifySerializer,
    ScheduleGenerationRequestSerializer,
    ScheduleGenerationResponseSerializer,
    DailyScheduleSerializer,
    WeeklyOccurrencesSerializer
)
from .generation_service import ScheduleGenerationService


class ScheduleGenerationConfigViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des configurations de génération"""
    queryset = ScheduleGenerationConfig.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create' or self.action == 'update':
            return ScheduleGenerationConfigCreateSerializer
        return ScheduleGenerationConfigSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        """Génère les occurrences pour la configuration"""
        config = self.get_object()
        serializer = ScheduleGenerationRequestSerializer(data=request.data)

        if serializer.is_valid():
            service = ScheduleGenerationService(config.schedule)

            result = service.generate_occurrences(
                preview_mode=serializer.validated_data.get('preview_mode', False),
                force_regenerate=serializer.validated_data.get('force_regenerate', False),
                preserve_modifications=serializer.validated_data.get('preserve_modifications', True),
                date_from=serializer.validated_data.get('date_from'),
                date_to=serializer.validated_data.get('date_to')
            )

            response_serializer = ScheduleGenerationResponseSerializer(data=result)
            if response_serializer.is_valid():
                return Response(response_serializer.data)

            return Response(result)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SessionOccurrenceViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des occurrences de sessions"""
    queryset = SessionOccurrence.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return SessionOccurrenceListSerializer
        elif self.action == 'create':
            return SessionOccurrenceCreateSerializer
        return SessionOccurrenceSerializer

    def perform_update(self, serializer):
        """Marque automatiquement les champs modifiés lors d'un UPDATE/PATCH"""
        from rest_framework.exceptions import ValidationError
        from django.db import transaction

        instance = self.get_object()

        # Récupère les données validées
        validated_data = serializer.validated_data

        # Utilise une transaction atomique pour éviter les race conditions
        with transaction.atomic():
            # Verrouille l'instance pour éviter les modifications concurrentes
            instance = SessionOccurrence.objects.select_for_update().get(pk=instance.pk)

            # Vérifie les conflits AVANT de sauvegarder si des champs critiques sont modifiés
            if any(field in validated_data for field in ['actual_date', 'start_time', 'end_time', 'room', 'teacher']):
                # Créer une copie temporaire de l'instance avec les nouvelles valeurs
                temp_occurrence = SessionOccurrence(
                    id=instance.id,
                    session_template=instance.session_template,
                    actual_date=validated_data.get('actual_date', instance.actual_date),
                    start_time=validated_data.get('start_time', instance.start_time),
                    end_time=validated_data.get('end_time', instance.end_time),
                    room=validated_data.get('room', instance.room),
                    teacher=validated_data.get('teacher', instance.teacher),
                    status='scheduled'
                )

                # Vérifie les conflits avec les autres occurrences
                conflicts = temp_occurrence.check_conflicts()
                if conflicts:
                    raise ValidationError({
                        'conflicts': conflicts,
                        'message': 'Cette modification crée des conflits avec d\'autres séances'
                    })

            # Vérifie si la date a été modifiée
            if 'actual_date' in validated_data and validated_data['actual_date'] != instance.actual_date:
                serializer.validated_data['is_time_modified'] = True

            # Vérifie si les horaires ont été modifiés
            if 'start_time' in validated_data and validated_data['start_time'] != instance.start_time:
                serializer.validated_data['is_time_modified'] = True

            if 'end_time' in validated_data and validated_data['end_time'] != instance.end_time:
                serializer.validated_data['is_time_modified'] = True

            # Vérifie si la salle a été modifiée
            if 'room' in validated_data and validated_data['room'] != instance.room:
                serializer.validated_data['is_room_modified'] = True

            # Vérifie si l'enseignant a été modifié
            if 'teacher' in validated_data and validated_data['teacher'] != instance.teacher:
                serializer.validated_data['is_teacher_modified'] = True

            # Sauvegarde les modifications
            serializer.save()

    def get_queryset(self):
        """Filtre les occurrences selon les paramètres de requête"""
        queryset = SessionOccurrence.objects.select_related(
            'session_template__course',
            'room',
            'teacher__user'
        ).order_by('actual_date', 'start_time')

        # Filtre par date
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')

        if date_from:
            queryset = queryset.filter(actual_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(actual_date__lte=date_to)

        # Filtre par emploi du temps
        schedule_id = self.request.query_params.get('schedule')
        if schedule_id:
            queryset = queryset.filter(session_template__schedule_id=schedule_id)

        # Filtre par enseignant
        teacher_id = self.request.query_params.get('teacher')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        # Filtre par salle
        room_id = self.request.query_params.get('room')
        if room_id:
            queryset = queryset.filter(room_id=room_id)

        # Filtre par statut
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        return queryset

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Annule une occurrence de session"""
        occurrence = self.get_object()
        serializer = SessionOccurrenceCancelSerializer(data=request.data)

        if serializer.is_valid():
            occurrence.cancel(
                reason=serializer.validated_data['reason'],
                cancelled_by=request.user
            )

            # TODO: Envoyer des notifications si demandé
            # if serializer.validated_data.get('notify_students'):
            #     notify_students(occurrence)
            # if serializer.validated_data.get('notify_teacher'):
            #     notify_teacher(occurrence)

            return Response({
                'success': True,
                'message': 'Occurrence annulée avec succès',
                'occurrence': SessionOccurrenceSerializer(occurrence).data
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def reschedule(self, request, pk=None):
        """Reprogramme une occurrence de session"""
        occurrence = self.get_object()
        serializer = SessionOccurrenceRescheduleSerializer(data=request.data)

        if serializer.is_valid():
            data = serializer.validated_data

            # Récupère la nouvelle salle et le nouvel enseignant si spécifiés
            new_room = None
            new_teacher = None

            if data.get('new_room'):
                new_room = get_object_or_404(Room, pk=data['new_room'])

            if data.get('new_teacher'):
                new_teacher = get_object_or_404(Teacher, pk=data['new_teacher'])

            # Reprogramme l'occurrence
            new_occurrence = occurrence.reschedule(
                new_date=data['new_date'],
                new_start_time=data['new_start_time'],
                new_end_time=data['new_end_time'],
                new_room=new_room,
                new_teacher=new_teacher
            )

            # Vérifie les conflits
            conflicts = new_occurrence.check_conflicts()

            # TODO: Envoyer des notifications si demandé
            # if serializer.validated_data.get('notify_students'):
            #     notify_students(new_occurrence)
            # if serializer.validated_data.get('notify_teacher'):
            #     notify_teacher(new_occurrence)

            return Response({
                'success': True,
                'message': 'Occurrence reprogrammée avec succès',
                'old_occurrence': SessionOccurrenceSerializer(occurrence).data,
                'new_occurrence': SessionOccurrenceSerializer(new_occurrence).data,
                'conflicts': conflicts
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def modify(self, request, pk=None):
        """Modifie une occurrence de session"""
        occurrence = self.get_object()
        serializer = SessionOccurrenceModifySerializer(data=request.data)

        if serializer.is_valid():
            data = serializer.validated_data

            # Modifie la salle
            if 'room' in data and data['room']:
                new_room = get_object_or_404(Room, pk=data['room'])
                if new_room != occurrence.room:
                    occurrence.room = new_room
                    occurrence.is_room_modified = True

            # Modifie l'enseignant
            if 'teacher' in data and data['teacher']:
                new_teacher = get_object_or_404(Teacher, pk=data['teacher'])
                if new_teacher != occurrence.teacher:
                    occurrence.teacher = new_teacher
                    occurrence.is_teacher_modified = True

            # Modifie les horaires
            if 'start_time' in data:
                occurrence.start_time = data['start_time']
                occurrence.is_time_modified = True

            if 'end_time' in data:
                occurrence.end_time = data['end_time']
                occurrence.is_time_modified = True

            # Modifie les notes
            if 'notes' in data:
                occurrence.notes = data['notes']

            occurrence.save()

            # Vérifie les conflits
            conflicts = occurrence.check_conflicts()

            # TODO: Envoyer des notifications si demandé
            # if serializer.validated_data.get('notify_students'):
            #     notify_students(occurrence)
            # if serializer.validated_data.get('notify_teacher'):
            #     notify_teacher(occurrence)

            return Response({
                'success': True,
                'message': 'Occurrence modifiée avec succès',
                'occurrence': SessionOccurrenceSerializer(occurrence).data,
                'conflicts': conflicts
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def conflicts(self, request, pk=None):
        """Retourne les conflits pour une occurrence"""
        occurrence = self.get_object()
        conflicts = occurrence.check_conflicts()

        return Response({
            'occurrence_id': occurrence.id,
            'date': occurrence.actual_date,
            'conflicts': conflicts
        })

    @action(detail=False, methods=['get'])
    def daily(self, request):
        """Retourne les occurrences pour une journée"""
        date_param = request.query_params.get('date')

        if not date_param:
            return Response(
                {'error': 'Le paramètre date est requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Format de date invalide (YYYY-MM-DD attendu)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Récupère les occurrences pour cette date
        occurrences = self.get_queryset().filter(actual_date=date)

        # Calcule les statistiques
        total_sessions = occurrences.count()
        cancelled_sessions = occurrences.filter(is_cancelled=True).count()

        # Compte les conflits
        conflicts_count = 0
        for occurrence in occurrences:
            conflicts_count += len(occurrence.check_conflicts())

        data = {
            'date': date,
            'occurrences': SessionOccurrenceListSerializer(occurrences, many=True).data,
            'total_sessions': total_sessions,
            'cancelled_sessions': cancelled_sessions,
            'conflicts_count': conflicts_count
        }

        return Response(data)

    @action(detail=False, methods=['get'])
    def weekly(self, request):
        """Retourne les occurrences pour une semaine"""
        date_param = request.query_params.get('date')

        if not date_param:
            return Response(
                {'error': 'Le paramètre date est requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Format de date invalide (YYYY-MM-DD attendu)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Calcule le début et la fin de la semaine
        from datetime import timedelta
        week_start = date - timedelta(days=date.weekday())
        week_end = week_start + timedelta(days=6)

        # Récupère les occurrences pour cette semaine
        occurrences = self.get_queryset().filter(
            actual_date__gte=week_start,
            actual_date__lte=week_end
        )

        # Groupe par jour de la semaine avec noms anglais
        occurrences_by_day = {
            'monday': [],
            'tuesday': [],
            'wednesday': [],
            'thursday': [],
            'friday': [],
            'saturday': [],
            'sunday': []
        }

        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

        for occurrence in occurrences:
            # 0 = lundi, 1 = mardi, etc.
            day_index = occurrence.actual_date.weekday()
            day_name = day_names[day_index]
            occurrences_by_day[day_name].append(occurrence)

        # Sérialiser les occurrences par jour
        serialized_occurrences = {}
        for day_name, day_occurrences in occurrences_by_day.items():
            serialized_occurrences[day_name] = SessionOccurrenceListSerializer(day_occurrences, many=True).data

        # Calcule les statistiques
        total_sessions = occurrences.count()
        total_hours = sum(occ.get_duration_hours() for occ in occurrences)

        data = {
            'week_start': week_start,
            'week_end': week_end,
            'occurrences_by_day': serialized_occurrences,  # Format attendu par le frontend
            'total': total_sessions,
            'total_hours': total_hours
        }

        return Response(data)


class ScheduleGenerationViewSet(viewsets.ViewSet):
    """ViewSet pour les actions de génération d'emploi du temps"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """Génère les occurrences pour un emploi du temps"""
        serializer = ScheduleGenerationRequestSerializer(data=request.data)

        if serializer.is_valid():
            schedule_id = serializer.validated_data['schedule_id']
            schedule = get_object_or_404(Schedule, pk=schedule_id)

            service = ScheduleGenerationService(schedule)

            result = service.generate_occurrences(
                preview_mode=serializer.validated_data.get('preview_mode', False),
                force_regenerate=serializer.validated_data.get('force_regenerate', False),
                preserve_modifications=serializer.validated_data.get('preserve_modifications', True),
                date_from=serializer.validated_data.get('date_from'),
                date_to=serializer.validated_data.get('date_to')
            )

            response_serializer = ScheduleGenerationResponseSerializer(data=result)
            if response_serializer.is_valid():
                return Response(response_serializer.data)

            return Response(result)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
