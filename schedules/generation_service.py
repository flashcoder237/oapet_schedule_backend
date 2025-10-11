# schedules/generation_service.py
from datetime import datetime, timedelta, time
from typing import List, Dict, Tuple
from django.db import transaction
from django.utils import timezone
from .models import (
    Schedule, ScheduleSession, SessionOccurrence,
    ScheduleGenerationConfig, TimeSlot, Room, Teacher
)


class ScheduleGenerationService:
    """Service pour générer les occurrences d'emploi du temps"""

    def __init__(self, schedule: Schedule):
        self.schedule = schedule
        self.config = None
        self.stats = {
            'occurrences_created': 0,
            'conflicts_detected': 0,
            'conflicts': [],
            'generation_time': 0
        }

    def generate_occurrences(
        self,
        preview_mode: bool = False,
        force_regenerate: bool = False,
        preserve_modifications: bool = True,
        date_from: datetime = None,
        date_to: datetime = None,
        use_ml_optimization: bool = True
    ) -> Dict:
        """
        Génère les occurrences de sessions pour l'emploi du temps

        Args:
            preview_mode: Si True, ne sauvegarde pas en base
            force_regenerate: Si True, régénère même si des occurrences existent
            preserve_modifications: Si True, conserve les modifications manuelles
            date_from: Date de début de génération (optionnel)
            date_to: Date de fin de génération (optionnel)
            use_ml_optimization: Si True, utilise l'optimisation ML

        Returns:
            Dict avec les résultats de la génération
        """
        start_time = timezone.now()

        try:
            # Récupère la configuration de génération
            self.config = ScheduleGenerationConfig.objects.get(schedule=self.schedule)
        except ScheduleGenerationConfig.DoesNotExist:
            return {
                'success': False,
                'message': 'Aucune configuration de génération trouvée pour cet emploi du temps',
                'occurrences_created': 0,
                'conflicts_detected': 0,
                'generation_time': 0
            }

        # Détermine la période de génération
        start_date = date_from or self.config.start_date
        end_date = date_to or self.config.end_date

        # Si pas en mode force, vérifie si des occurrences existent déjà
        if not force_regenerate:
            existing_occurrences = SessionOccurrence.objects.filter(
                session_template__schedule=self.schedule,
                actual_date__gte=start_date,
                actual_date__lte=end_date
            ).exists()

            if existing_occurrences:
                return {
                    'success': False,
                    'message': 'Des occurrences existent déjà. Utilisez force_regenerate=True pour régénérer.',
                    'occurrences_created': 0,
                    'conflicts_detected': 0,
                    'generation_time': 0
                }

        # Récupère toutes les sessions du template
        session_templates = ScheduleSession.objects.filter(
            schedule=self.schedule,
            is_cancelled=False
        ).select_related('course', 'teacher', 'room', 'time_slot')

        # Génère les occurrences (avec ou sans ML)
        if use_ml_optimization:
            occurrences = self._generate_with_ml(session_templates, start_date, end_date)
        else:
            occurrences = []
            for session_template in session_templates:
                session_occurrences = self._generate_session_occurrences(
                    session_template,
                    start_date,
                    end_date
                )
                occurrences.extend(session_occurrences)

        # Vérifie les conflits
        self._check_conflicts(occurrences)

        # Sauvegarde en base si pas en mode preview
        if not preview_mode:
            with transaction.atomic():
                # Supprime les anciennes occurrences si force_regenerate
                if force_regenerate:
                    if preserve_modifications:
                        # Conserve les occurrences modifiées
                        SessionOccurrence.objects.filter(
                            session_template__schedule=self.schedule,
                            actual_date__gte=start_date,
                            actual_date__lte=end_date,
                            is_room_modified=False,
                            is_teacher_modified=False,
                            is_time_modified=False,
                            is_cancelled=False
                        ).delete()
                    else:
                        # Supprime toutes les occurrences
                        SessionOccurrence.objects.filter(
                            session_template__schedule=self.schedule,
                            actual_date__gte=start_date,
                            actual_date__lte=end_date
                        ).delete()

                # Crée les nouvelles occurrences
                SessionOccurrence.objects.bulk_create(occurrences)
                self.stats['occurrences_created'] = len(occurrences)

        end_time = timezone.now()
        self.stats['generation_time'] = (end_time - start_time).total_seconds()

        return {
            'success': True,
            'message': f"{len(occurrences)} occurrence(s) générée(s) avec succès",
            'occurrences_created': len(occurrences),
            'conflicts_detected': self.stats['conflicts_detected'],
            'conflicts': self.stats['conflicts'],
            'preview_data': self._get_preview_data(occurrences) if preview_mode else None,
            'generation_time': self.stats['generation_time']
        }

    def _generate_with_ml(
        self,
        session_templates: List[ScheduleSession],
        start_date: datetime,
        end_date: datetime
    ) -> List[SessionOccurrence]:
        """Génère les occurrences avec optimisation ML"""
        from .ml_optimization_service import MLOptimizedScheduleGenerator

        ml_generator = MLOptimizedScheduleGenerator(self.schedule, self.config)
        return ml_generator.generate_optimized_occurrences(
            session_templates,
            start_date,
            end_date
        )

    def _generate_session_occurrences(
        self,
        session_template: ScheduleSession,
        start_date: datetime,
        end_date: datetime
    ) -> List[SessionOccurrence]:
        """Génère les occurrences pour une session template en tenant compte du volume horaire"""
        occurrences = []

        # Récupère le créneau horaire
        time_slot = session_template.time_slot

        # Calcule la durée de chaque session en heures
        session_start = session_template.specific_start_time or time_slot.start_time
        session_end = session_template.specific_end_time or time_slot.end_time
        session_duration_hours = (
            timezone.datetime.combine(timezone.datetime.today(), session_end) -
            timezone.datetime.combine(timezone.datetime.today(), session_start)
        ).total_seconds() / 3600

        # Détermine le nombre total d'occurrences nécessaires basé sur total_hours du cours
        course_total_hours = session_template.course.total_hours or 0

        # Si total_hours est défini, calcule le nombre d'occurrences nécessaires
        if course_total_hours > 0 and session_duration_hours > 0:
            max_occurrences = int(course_total_hours / session_duration_hours)
        else:
            # Sinon, génère sur toute la période (comportement par défaut)
            max_occurrences = None

        # Mappe les jours de la semaine
        day_mapping = {
            'monday': 0,
            'tuesday': 1,
            'wednesday': 2,
            'thursday': 3,
            'friday': 4,
            'saturday': 5,
            'sunday': 6
        }

        target_weekday = day_mapping.get(time_slot.day_of_week)
        if target_weekday is None:
            return occurrences

        # Trouve le premier jour correspondant
        current_date = start_date
        while current_date.weekday() != target_weekday:
            current_date += timedelta(days=1)
            if current_date > end_date:
                return occurrences

        # Génère les occurrences selon la récurrence
        occurrence_count = 0
        while current_date <= end_date:
            # Si max_occurrences est défini, vérifie qu'on ne dépasse pas
            if max_occurrences is not None and occurrence_count >= max_occurrences:
                break

            # Vérifie si la date est exclue
            if not self.config.is_date_excluded(current_date):
                # Vérifie s'il y a une semaine spéciale
                special_week = self.config.get_special_week(current_date)

                # Si semaine spéciale et suspension des cours, skip
                if special_week and special_week.get('suspend_regular_classes', False):
                    current_date += timedelta(days=7)
                    continue

                # Crée l'occurrence
                occurrence = SessionOccurrence(
                    session_template=session_template,
                    actual_date=current_date,
                    start_time=session_start,
                    end_time=session_end,
                    room=session_template.room,
                    teacher=session_template.teacher,
                    status='scheduled',
                    is_room_modified=False,
                    is_teacher_modified=False,
                    is_time_modified=False
                )
                occurrences.append(occurrence)
                occurrence_count += 1

            # Passe à la semaine suivante selon le type de récurrence
            if self.config.recurrence_type == 'weekly':
                current_date += timedelta(days=7)
            elif self.config.recurrence_type == 'biweekly':
                current_date += timedelta(days=14)
            elif self.config.recurrence_type == 'monthly':
                # Approximation mensuelle (4 semaines)
                current_date += timedelta(days=28)
            else:
                current_date += timedelta(days=7)

        return occurrences

    def _check_conflicts(self, occurrences: List[SessionOccurrence]):
        """Vérifie les conflits entre les occurrences"""
        # Groupe les occurrences par date
        occurrences_by_date = {}
        for occurrence in occurrences:
            date_key = occurrence.actual_date
            if date_key not in occurrences_by_date:
                occurrences_by_date[date_key] = []
            occurrences_by_date[date_key].append(occurrence)

        # Vérifie les conflits pour chaque jour
        for date, day_occurrences in occurrences_by_date.items():
            for i, occ1 in enumerate(day_occurrences):
                for occ2 in day_occurrences[i+1:]:
                    conflicts = self._check_occurrence_conflict(occ1, occ2)
                    if conflicts:
                        self.stats['conflicts'].extend(conflicts)
                        self.stats['conflicts_detected'] += len(conflicts)

    def _check_occurrence_conflict(
        self,
        occ1: SessionOccurrence,
        occ2: SessionOccurrence
    ) -> List[Dict]:
        """Vérifie les conflits entre deux occurrences"""
        conflicts = []

        # Vérifie le chevauchement horaire
        if not (occ1.end_time <= occ2.start_time or occ1.start_time >= occ2.end_time):
            # Il y a chevauchement horaire

            # Conflit de salle
            if occ1.room == occ2.room:
                conflicts.append({
                    'type': 'room_double_booking',
                    'severity': 'high',
                    'date': str(occ1.actual_date),
                    'time': f"{occ1.start_time} - {occ1.end_time}",
                    'resource': occ1.room.code,
                    'courses': [
                        occ1.session_template.course.code,
                        occ2.session_template.course.code
                    ]
                })

            # Conflit d'enseignant
            if occ1.teacher == occ2.teacher:
                conflicts.append({
                    'type': 'teacher_double_booking',
                    'severity': 'critical',
                    'date': str(occ1.actual_date),
                    'time': f"{occ1.start_time} - {occ1.end_time}",
                    'resource': occ1.teacher.user.get_full_name(),
                    'courses': [
                        occ1.session_template.course.code,
                        occ2.session_template.course.code
                    ]
                })

        return conflicts

    def _get_preview_data(self, occurrences: List[SessionOccurrence]) -> Dict:
        """Génère les données de prévisualisation"""
        # Compte les occurrences par semaine
        weeks = {}
        for occurrence in occurrences:
            week_start = occurrence.actual_date - timedelta(days=occurrence.actual_date.weekday())
            week_key = week_start.strftime('%Y-%m-%d')
            if week_key not in weeks:
                weeks[week_key] = 0
            weeks[week_key] += 1

        return {
            'total_occurrences': len(occurrences),
            'weeks': weeks,
            'conflicts': self.stats['conflicts']
        }
