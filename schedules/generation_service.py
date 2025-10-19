# schedules/generation_service.py
from datetime import datetime, timedelta, time
from typing import List, Dict, Tuple
import math
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

        # Vérifie les conflits AVANT la sauvegarde
        self._check_conflicts(occurrences)

        # Compte les conflits critiques
        critical_conflicts = [
            c for c in self.stats['conflicts']
            if c.get('severity') in ['critical', 'high'] and c.get('type') in [
                'room_double_booking', 'teacher_double_booking', 'teacher_overload'
            ]
        ]

        # Si des conflits critiques existent et que allow_conflicts est False, annuler
        if critical_conflicts and not self.config.allow_conflicts and not preview_mode:
            return {
                'success': False,
                'message': f"{len(critical_conflicts)} conflit(s) critique(s) détecté(s). Génération annulée.",
                'occurrences_created': 0,
                'conflicts_detected': len(critical_conflicts),
                'conflicts': critical_conflicts,
                'generation_time': 0
            }

        # Sauvegarde en base si pas en mode preview
        if not preview_mode:
            with transaction.atomic():
                # Supprime les anciennes occurrences si force_regenerate
                if force_regenerate:
                    if preserve_modifications:
                        # Conserve les occurrences modifiées OU annulées
                        SessionOccurrence.objects.filter(
                            session_template__schedule=self.schedule,
                            actual_date__gte=start_date,
                            actual_date__lte=end_date,
                            is_room_modified=False,
                            is_teacher_modified=False,
                            is_time_modified=False
                        ).exclude(
                            is_cancelled=True  # Garde aussi les annulées
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
        course_hours_per_week = session_template.course.hours_per_week or 0

        # Si total_hours est défini, calcule le nombre d'occurrences nécessaires
        if course_total_hours > 0 and session_duration_hours > 0:
            # Calcule le nombre de semaines de cours
            weeks_count = ((end_date - start_date).days // 7) + 1

            # Vérifie la cohérence entre total_hours et hours_per_week
            if course_hours_per_week > 0:
                expected_total_hours = course_hours_per_week * weeks_count
                # Tolère une différence de 10% pour flexibilité
                if abs(expected_total_hours - course_total_hours) > (expected_total_hours * 0.1):
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Incohérence volume horaire pour {session_template.course.code}: "
                        f"total_hours={course_total_hours}h mais hours_per_week={course_hours_per_week}h "
                        f"× {weeks_count} semaines = {expected_total_hours}h attendu"
                    )
                    self.stats['conflicts'].append({
                        'type': 'volume_inconsistency',
                        'severity': 'warning',
                        'course': session_template.course.code,
                        'total_hours': course_total_hours,
                        'expected_hours': expected_total_hours,
                        'message': f'Incohérence volume horaire: {course_total_hours}h défini mais {expected_total_hours}h attendu'
                    })

            # Utilise total_hours comme référence principale
            max_occurrences = math.ceil(course_total_hours / session_duration_hours)
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

                # Sélectionne la meilleure salle disponible si la configuration le permet
                selected_room = self._select_best_room(
                    session_template,
                    current_date,
                    session_start,
                    session_end,
                    occurrences
                )

                # Si un conflit critique a été détecté, ne pas créer l'occurrence
                if selected_room == 'CONFLICT':
                    # Le conflit a déjà été ajouté aux stats par _select_best_room
                    current_date += self._get_recurrence_delta()
                    continue

                # Vérifie aussi les conflits d'enseignant
                teacher_conflict = self._check_teacher_availability(
                    session_template.teacher,
                    current_date,
                    session_start,
                    session_end,
                    occurrences
                )

                if teacher_conflict:
                    self.stats['conflicts'].append(teacher_conflict)
                    self.stats['conflicts_detected'] += 1
                    # Ne pas créer cette occurrence si allow_conflicts est False
                    if not self.config.allow_conflicts:
                        current_date += self._get_recurrence_delta()
                        continue

                # Crée l'occurrence
                occurrence = SessionOccurrence(
                    session_template=session_template,
                    actual_date=current_date,
                    start_time=session_start,
                    end_time=session_end,
                    room=selected_room or session_template.room,
                    teacher=session_template.teacher,
                    status='scheduled',
                    is_room_modified=selected_room is not None and selected_room != session_template.room,
                    is_teacher_modified=False,
                    is_time_modified=False
                )
                occurrences.append(occurrence)
                occurrence_count += 1

            # Passe à la semaine suivante selon le type de récurrence
            current_date += self._get_recurrence_delta()

        return occurrences

    def _get_recurrence_delta(self) -> timedelta:
        """Retourne le delta de temps selon le type de récurrence"""
        from dateutil.relativedelta import relativedelta

        if self.config.recurrence_type == 'weekly':
            return timedelta(days=7)
        elif self.config.recurrence_type == 'biweekly':
            return timedelta(days=14)
        elif self.config.recurrence_type == 'monthly':
            # Utilise relativedelta pour gérer correctement les mois
            # Retourne 28 jours par défaut mais devrait être géré différemment
            # Pour une vraie récurrence mensuelle, utiliser dateutil
            return timedelta(days=30)  # Moyenne plus réaliste que 28
        else:
            return timedelta(days=7)

    def _check_teacher_availability(
        self,
        teacher: Teacher,
        date: datetime,
        start_time: time,
        end_time: time,
        existing_occurrences: List[SessionOccurrence]
    ):
        """Vérifie si l'enseignant est disponible à ce créneau"""
        import logging
        logger = logging.getLogger(__name__)

        # Vérifie les conflits avec les occurrences déjà générées
        for occ in existing_occurrences:
            if (occ.teacher.id == teacher.id and
                occ.actual_date == date and
                self._has_time_overlap(occ.start_time, occ.end_time, start_time, end_time)):

                logger.error(
                    f"CONFLIT ENSEIGNANT: {teacher.user.get_full_name()} "
                    f"déjà occupé le {date.strftime('%Y-%m-%d')} à {start_time}"
                )

                return {
                    'type': 'teacher_double_booking',
                    'severity': 'critical',
                    'date': str(date),
                    'time': f"{start_time} - {end_time}",
                    'teacher': teacher.user.get_full_name(),
                    'conflicting_course': occ.session_template.course.code,
                    'message': f"L'enseignant {teacher.user.get_full_name()} est déjà occupé"
                }

        # Vérifie aussi dans la base de données
        existing_db_occurrences = SessionOccurrence.objects.filter(
            teacher=teacher,
            actual_date=date,
            status='scheduled'
        ).select_related('session_template__course')

        for db_occ in existing_db_occurrences:
            if self._has_time_overlap(db_occ.start_time, db_occ.end_time, start_time, end_time):
                logger.error(
                    f"CONFLIT ENSEIGNANT (BD): {teacher.user.get_full_name()} "
                    f"déjà occupé le {date.strftime('%Y-%m-%d')} à {start_time}"
                )

                return {
                    'type': 'teacher_double_booking',
                    'severity': 'critical',
                    'date': str(date),
                    'time': f"{start_time} - {end_time}",
                    'teacher': teacher.user.get_full_name(),
                    'conflicting_course': db_occ.session_template.course.code,
                    'message': f"L'enseignant {teacher.user.get_full_name()} est déjà occupé (BD)"
                }

        # Vérifie la charge horaire hebdomadaire
        week_start = date - timedelta(days=date.weekday())
        week_end = week_start + timedelta(days=6)

        # Calcul des heures déjà planifiées cette semaine
        weekly_hours = 0
        for occ in existing_occurrences:
            if (occ.teacher.id == teacher.id and
                week_start <= occ.actual_date <= week_end):
                duration = (
                    timezone.datetime.combine(timezone.datetime.today(), occ.end_time) -
                    timezone.datetime.combine(timezone.datetime.today(), occ.start_time)
                ).total_seconds() / 3600
                weekly_hours += duration

        # Ajoute les heures de la BD
        db_weekly_occurrences = SessionOccurrence.objects.filter(
            teacher=teacher,
            actual_date__gte=week_start,
            actual_date__lte=week_end,
            status='scheduled'
        )

        for db_occ in db_weekly_occurrences:
            weekly_hours += db_occ.get_duration_hours()

        # Ajoute la durée de cette nouvelle session
        new_session_duration = (
            timezone.datetime.combine(timezone.datetime.today(), end_time) -
            timezone.datetime.combine(timezone.datetime.today(), start_time)
        ).total_seconds() / 3600

        total_hours = weekly_hours + new_session_duration

        # Vérifie si cela dépasse la limite
        if total_hours > teacher.max_hours_per_week:
            logger.warning(
                f"SURCHARGE ENSEIGNANT: {teacher.user.get_full_name()} "
                f"dépasserait sa limite ({total_hours:.1f}h > {teacher.max_hours_per_week}h)"
            )

            return {
                'type': 'teacher_overload',
                'severity': 'high',
                'date': str(date),
                'week_start': str(week_start),
                'week_end': str(week_end),
                'teacher': teacher.user.get_full_name(),
                'total_hours': round(total_hours, 1),
                'max_hours': teacher.max_hours_per_week,
                'message': f"Surcharge: {total_hours:.1f}h > {teacher.max_hours_per_week}h"
            }

        return None

    def _select_best_room(
        self,
        session_template: ScheduleSession,
        date: datetime,
        start_time: time,
        end_time: time,
        existing_occurrences: List[SessionOccurrence]
    ):
        """Sélectionne la meilleure salle disponible pour une occurrence"""
        import logging
        logger = logging.getLogger(__name__)

        # Si on doit respecter les préférences de salles, vérifier quand même la disponibilité
        if self.config.respect_room_preferences:
            # Vérifie si la salle du template est disponible
            default_room = session_template.room

            # Vérifie les conflits avec les occurrences déjà générées
            for occ in existing_occurrences:
                if (occ.room.id == default_room.id and occ.actual_date == date and
                    self._has_time_overlap(occ.start_time, occ.end_time, start_time, end_time)):

                    logger.error(
                        f"CONFLIT SALLE (respect_room_preferences): {default_room.code} "
                        f"pour {session_template.course.code} le {date.strftime('%Y-%m-%d')} à {start_time} "
                        f"est déjà occupée par {occ.session_template.course.code}"
                    )

                    self.stats['conflicts'].append({
                        'type': 'room_double_booking',
                        'severity': 'critical',
                        'date': str(date),
                        'time': f"{start_time} - {end_time}",
                        'course': session_template.course.code,
                        'room': default_room.code,
                        'conflicting_course': occ.session_template.course.code,
                        'message': f'Salle préférée {default_room.code} déjà occupée (respect_room_preferences=True)'
                    })
                    self.stats['conflicts_detected'] += 1

                    return 'CONFLICT'

            # Vérifie aussi en BD
            existing_db_occurrences = SessionOccurrence.objects.filter(
                room=default_room,
                actual_date=date,
                status='scheduled'
            ).select_related('session_template__course')

            for db_occ in existing_db_occurrences:
                if self._has_time_overlap(db_occ.start_time, db_occ.end_time, start_time, end_time):
                    logger.error(
                        f"CONFLIT SALLE BD (respect_room_preferences): {default_room.code} "
                        f"pour {session_template.course.code} le {date.strftime('%Y-%m-%d')} à {start_time} "
                        f"est déjà occupée par {db_occ.session_template.course.code}"
                    )

                    self.stats['conflicts'].append({
                        'type': 'room_double_booking',
                        'severity': 'critical',
                        'date': str(date),
                        'time': f"{start_time} - {end_time}",
                        'course': session_template.course.code,
                        'room': default_room.code,
                        'conflicting_course': db_occ.session_template.course.code,
                        'message': f'Salle préférée {default_room.code} déjà occupée en BD (respect_room_preferences=True)'
                    })
                    self.stats['conflicts_detected'] += 1

                    return 'CONFLICT'

            # Salle disponible, retourner None pour utiliser la salle du template
            return None

        course = session_template.course

        # Détermine l'effectif réel : priorise classes > expected_students > max_students
        from django.db.models import Count, Sum
        from courses.models_class import ClassCourse

        # Cherche d'abord dans les classes assignées via ClassCourse
        class_total_students = ClassCourse.objects.filter(
            course=course,
            is_active=True
        ).aggregate(
            total=Sum('student_class__student_count')
        )['total'] or 0

        # Si pas de classes assignées, utilise les valeurs par défaut du cours
        if class_total_students == 0:
            actual_students = session_template.expected_students or course.max_students or 30
        else:
            actual_students = class_total_students

        # Cherche les salles disponibles qui correspondent aux besoins du cours
        available_rooms = Room.objects.filter(
            is_active=True,
            capacity__gte=actual_students
        )

        # Filtre selon les équipements requis
        if course.requires_projector:
            available_rooms = available_rooms.filter(has_projector=True)
        if course.requires_computer:
            available_rooms = available_rooms.filter(has_computer=True)
        if course.requires_laboratory:
            available_rooms = available_rooms.filter(is_laboratory=True)

        # Exclut les salles déjà occupées à ce créneau et cette date
        occupied_room_ids = []
        for occ in existing_occurrences:
            if (occ.actual_date == date and
                self._has_time_overlap(occ.start_time, occ.end_time, start_time, end_time)):
                # Il y a chevauchement horaire, exclure cette salle
                occupied_room_ids.append(occ.room.id)

        if occupied_room_ids:
            available_rooms = available_rooms.exclude(id__in=occupied_room_ids)

        # Vérifie aussi les conflits dans la base de données pour cette session template
        # (en cas de régénération partielle)
        existing_db_occurrences = SessionOccurrence.objects.filter(
            actual_date=date,
            status='scheduled'
        ).exclude(
            session_template=session_template
        ).select_related('room')

        for db_occ in existing_db_occurrences:
            if self._has_time_overlap(db_occ.start_time, db_occ.end_time, start_time, end_time):
                available_rooms = available_rooms.exclude(id=db_occ.room.id)

        # Si aucune salle disponible, lever une exception au lieu de créer un conflit
        if not available_rooms.exists():
            # Vérifie si la salle du template est disponible
            default_room = session_template.room
            default_room_conflicts = []

            for occ in existing_occurrences:
                if (occ.room.id == default_room.id and occ.actual_date == date and
                    self._has_time_overlap(occ.start_time, occ.end_time, start_time, end_time)):
                    default_room_conflicts.append(occ)

            # Vérifie aussi en BD
            db_conflicts = existing_db_occurrences.filter(room=default_room)

            if default_room_conflicts or db_conflicts.exists():
                # Ajouter un conflit CRITIQUE dans les stats
                self.stats['conflicts'].append({
                    'type': 'room_double_booking',
                    'severity': 'critical',
                    'date': str(date),
                    'time': f"{start_time} - {end_time}",
                    'course': session_template.course.code,
                    'room': default_room.code,
                    'message': f'Aucune salle disponible et conflit sur salle par défaut {default_room.code}'
                })
                self.stats['conflicts_detected'] += 1

                logger.error(
                    f"CONFLIT CRITIQUE: Aucune salle disponible pour {session_template.course.code} "
                    f"le {date.strftime('%Y-%m-%d')} à {start_time}. "
                    f"La salle par défaut {default_room.code} est déjà occupée."
                )

                # Retourne None pour signaler l'impossibilité (sera géré par l'appelant)
                return 'CONFLICT'
            else:
                # La salle par défaut est libre, on peut l'utiliser
                logger.warning(
                    f"Aucune salle optimale disponible pour {session_template.course.code} "
                    f"le {date.strftime('%Y-%m-%d')} à {start_time}. "
                    f"Utilisation de la salle par défaut {default_room.code}."
                )
                return None

        # Sélectionne la salle la plus adaptée en tenant compte de l'utilisation
        available_rooms_list = list(available_rooms)

        # Compte combien de fois chaque salle a déjà été utilisée
        room_usage_count = {}
        for occ in existing_occurrences:
            room_id = occ.room.id
            room_usage_count[room_id] = room_usage_count.get(room_id, 0) + 1

        # Compte aussi dans la BD
        if existing_db_occurrences.exists():
            from django.db.models import Count
            db_usage = SessionOccurrence.objects.filter(
                status='scheduled'
            ).values('room_id').annotate(count=Count('id'))

            for item in db_usage:
                room_id = item['room_id']
                count = item['count']
                room_usage_count[room_id] = room_usage_count.get(room_id, 0) + count

        # Calcule un score pour chaque salle disponible
        def calculate_room_score(room):
            # Score basé sur la capacité (plus proche de l'effectif réel = mieux)
            capacity_diff = abs(room.capacity - actual_students)
            capacity_score = capacity_diff

            # Score basé sur l'utilisation (moins utilisé = mieux)
            usage_count = room_usage_count.get(room.id, 0)
            usage_score = usage_count * 100  # Pénalise fortement les salles déjà utilisées

            # Score combiné (plus bas = mieux)
            total_score = capacity_score + usage_score

            return total_score

        # Sélectionne la salle avec le meilleur score
        best_room = min(
            available_rooms_list,
            key=calculate_room_score
        )

        return best_room

    def _has_time_overlap(self, start1: time, end1: time, start2: time, end2: time) -> bool:
        """
        Vérifie s'il y a chevauchement entre deux plages horaires
        Gère correctement les bornes en considérant un temps de transition de 5 minutes
        """
        from datetime import datetime, timedelta

        # Convertit les times en datetime pour faciliter les calculs
        today = datetime.today().date()
        dt_start1 = datetime.combine(today, start1)
        dt_end1 = datetime.combine(today, end1)
        dt_start2 = datetime.combine(today, start2)
        dt_end2 = datetime.combine(today, end2)

        # Ajoute un buffer de 5 minutes pour le temps de transition
        transition_buffer = timedelta(minutes=5)
        dt_end1_with_buffer = dt_end1 + transition_buffer
        dt_end2_with_buffer = dt_end2 + transition_buffer

        # Vérifie le chevauchement avec buffer
        return not (dt_end1_with_buffer <= dt_start2 or dt_end2_with_buffer <= dt_start1)

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

        # Vérifie le chevauchement horaire avec la nouvelle méthode améliorée
        if self._has_time_overlap(occ1.start_time, occ1.end_time, occ2.start_time, occ2.end_time):
            # Il y a chevauchement horaire

            # Conflit de salle
            if occ1.room == occ2.room:
                conflicts.append({
                    'type': 'room_double_booking',
                    'severity': 'critical',  # Changé de 'high' à 'critical'
                    'date': str(occ1.actual_date),
                    'time': f"{occ1.start_time} - {occ1.end_time}",
                    'resource': occ1.room.code,
                    'courses': [
                        occ1.session_template.course.code,
                        occ2.session_template.course.code
                    ],
                    'message': f"Conflit de salle {occ1.room.code}"
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
                    ],
                    'message': f"Conflit enseignant {occ1.teacher.user.get_full_name()}"
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
