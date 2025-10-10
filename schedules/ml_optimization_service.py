# schedules/ml_optimization_service.py
"""
Service ML pour optimiser la génération d'occurrences de sessions
Utilise le modèle ML entraîné pour prédire les meilleurs créneaux
"""
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import numpy as np
from django.db.models import Count, Q

from .models import (
    Schedule, ScheduleSession, SessionOccurrence,
    ScheduleGenerationConfig, TimeSlot, Room, Teacher
)
from courses.models import Course
from ml_engine.services import TimetablePredictor
from ml_engine.models import MLModel


class MLOptimizedScheduleGenerator:
    """Générateur d'emploi du temps optimisé par ML"""

    def __init__(self, schedule: Schedule, config: ScheduleGenerationConfig):
        self.schedule = schedule
        self.config = config
        self.ml_model = None
        self.predictor = None

        # Initialise le prédicteur ML si disponible
        try:
            self.ml_model = MLModel.objects.filter(is_active=True).first()
            if self.ml_model:
                self.predictor = TimetablePredictor(self.ml_model)
        except:
            pass  # Pas de modèle ML disponible, utilisation de la génération standard

    def generate_optimized_occurrences(
        self,
        session_templates: List[ScheduleSession],
        start_date: datetime.date,
        end_date: datetime.date
    ) -> List[SessionOccurrence]:
        """Génère les occurrences de manière optimisée avec ML"""

        # Si pas de ML, utiliser la génération standard
        if not self.predictor:
            return self._generate_standard(session_templates, start_date, end_date)

        # Prioriser les sessions par difficulté (ML)
        prioritized_sessions = self._prioritize_sessions_ml(session_templates)

        # Générer les occurrences en respectant la priorité
        occurrences = []
        for session_template, priority_data in prioritized_sessions:
            session_occurrences = self._generate_session_occurrences_ml(
                session_template,
                priority_data,
                start_date,
                end_date,
                existing_occurrences=occurrences
            )
            occurrences.extend(session_occurrences)

        return occurrences

    def _prioritize_sessions_ml(
        self,
        session_templates: List[ScheduleSession]
    ) -> List[Tuple[ScheduleSession, Dict]]:
        """Priorise les sessions selon la difficulté prédite par ML"""
        prioritized = []

        for session in session_templates:
            # Prépare les données pour la prédiction ML
            course_data = self._prepare_course_data(session)

            # Prédit la difficulté
            prediction = self.predictor.predict_difficulty(course_data)

            prioritized.append((session, prediction))

        # Trie par priorité (1 = haute, 3 = basse)
        prioritized.sort(key=lambda x: x[1]['priority'])

        return prioritized

    def _prepare_course_data(self, session: ScheduleSession) -> Dict:
        """Prépare les données du cours pour la prédiction ML"""
        course = session.course

        # Compte les cours dans le même cursus
        curriculum_courses = Course.objects.filter(
            department=course.department,
            level=course.level,
            semester=course.semester
        ).count()

        # Compte les salles disponibles avec les bonnes capacités
        suitable_rooms = Room.objects.filter(
            capacity__gte=session.expected_students,
            is_active=True
        ).count()

        # Contraintes d'indisponibilité de l'enseignant
        teacher_availability = session.teacher.availability or {}
        unavailable_slots = len(teacher_availability.get('unavailable_times', []))

        return {
            'course_name': course.name,
            'lectures': course.total_hours // 2 if course.total_hours else 15,  # Approximation
            'min_days': course.min_sessions_per_week or 1,
            'students': course.enrollments_count or session.expected_students or course.max_students,
            'teacher': session.teacher.user.username,
            'total_courses': curriculum_courses,
            'total_rooms': suitable_rooms,
            'total_days': 5,  # Par défaut
            'periods_per_day': 6,  # Par défaut
            'total_curricula': 1,
            'total_lectures': course.total_hours or 30,
            'avg_room_capacity': 50,  # Moyenne approximative
            'lecture_density': (course.total_hours or 30) / (5 * 6 * 15),  # Approx
            'student_lecture_ratio': (course.max_students or 40) / max(course.hours_per_week or 1, 1),
            'course_room_ratio': curriculum_courses / max(suitable_rooms, 1),
            'utilization_pressure': 0.6,  # Valeur par défaut
            'min_days_constraint_tightness': course.hours_per_week / max(course.min_sessions_per_week or 1, 1) if course.hours_per_week else 1.5,
            'conflict_degree': 2,  # Valeur par défaut
            'conflict_density': 0.1,  # Valeur par défaut
            'clustering_coefficient': 0.3,  # Valeur par défaut
            'betweenness_centrality': 0.2,  # Valeur par défaut
            'unavailability_count': unavailable_slots,
            'unavailability_ratio': unavailable_slots / (5 * 6) if unavailable_slots else 0,
            'room_constraint_count': 1 if course.requires_laboratory else 0,
        }

    def _generate_session_occurrences_ml(
        self,
        session_template: ScheduleSession,
        priority_data: Dict,
        start_date: datetime.date,
        end_date: datetime.date,
        existing_occurrences: List[SessionOccurrence]
    ) -> List[SessionOccurrence]:
        """Génère les occurrences pour une session en utilisant l'optimisation ML"""
        occurrences = []

        # Récupère le créneau horaire
        time_slot = session_template.time_slot

        # Map des jours
        day_mapping = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }

        target_weekday = day_mapping.get(time_slot.day_of_week)
        if target_weekday is None:
            return occurrences

        # Calcule les meilleures dates selon les recommandations ML
        recommended_dates = self._get_recommended_dates(
            session_template,
            priority_data,
            start_date,
            end_date,
            target_weekday,
            existing_occurrences
        )

        # Crée les occurrences
        for date in recommended_dates:
            # Vérifie si la date est exclue
            if self.config.is_date_excluded(date):
                continue

            # Vérifie semaine spéciale
            special_week = self.config.get_special_week(date)
            if special_week and special_week.get('suspend_regular_classes', False):
                continue

            # Sélectionne la meilleure salle (si flexible)
            best_room = self._select_best_room(
                session_template,
                date,
                time_slot,
                existing_occurrences
            )

            # Crée l'occurrence
            occurrence = SessionOccurrence(
                session_template=session_template,
                actual_date=date,
                start_time=session_template.specific_start_time or time_slot.start_time,
                end_time=session_template.specific_end_time or time_slot.end_time,
                room=best_room or session_template.room,
                teacher=session_template.teacher,
                status='scheduled',
                is_room_modified=best_room is not None and best_room != session_template.room,
                is_teacher_modified=False,
                is_time_modified=False
            )
            occurrences.append(occurrence)

        return occurrences

    def _get_recommended_dates(
        self,
        session_template: ScheduleSession,
        priority_data: Dict,
        start_date: datetime.date,
        end_date: datetime.date,
        target_weekday: int,
        existing_occurrences: List[SessionOccurrence]
    ) -> List[datetime.date]:
        """Calcule les meilleures dates selon les recommandations ML et les contraintes"""
        dates = []

        # Trouve le premier jour correspondant
        current_date = start_date
        while current_date.weekday() != target_weekday:
            current_date += timedelta(days=1)
            if current_date > end_date:
                return dates

        # Génère les dates selon la récurrence et les recommandations ML
        while current_date <= end_date:
            # Vérifie si la date est optimale selon ML
            if self._is_date_optimal(
                session_template,
                current_date,
                priority_data,
                existing_occurrences
            ):
                dates.append(current_date)

            # Passe à la semaine suivante selon récurrence
            if self.config.recurrence_type == 'weekly':
                current_date += timedelta(days=7)
            elif self.config.recurrence_type == 'biweekly':
                current_date += timedelta(days=14)
            else:
                current_date += timedelta(days=7)

        return dates

    def _is_date_optimal(
        self,
        session_template: ScheduleSession,
        date: datetime.date,
        priority_data: Dict,
        existing_occurrences: List[SessionOccurrence]
    ) -> bool:
        """Vérifie si une date est optimale selon les critères ML"""

        # Si niveau de flexibilité est rigide, accepter toutes les dates
        if self.config.flexibility_level == 'rigid':
            return True

        # Compte le nombre de sessions ce jour-là
        sessions_on_day = sum(1 for occ in existing_occurrences if occ.actual_date == date)

        # Si niveau flexible et trop de sessions ce jour, peut-être reporter
        if self.config.flexibility_level == 'flexible':
            if sessions_on_day >= self.config.max_sessions_per_day:
                return False

        # Vérifie la charge de l'enseignant
        teacher_sessions = sum(
            1 for occ in existing_occurrences
            if occ.teacher == session_template.teacher and occ.actual_date == date
        )

        # Si l'enseignant a déjà beaucoup de sessions ce jour
        if teacher_sessions >= (session_template.teacher.max_hours_per_week or 15) // 5:
            return False

        # Si priorité élevée (1), toujours accepter
        if priority_data['priority'] == 1:
            return True

        # Si priorité basse (3) et déjà beaucoup de sessions, refuser
        if priority_data['priority'] == 3 and sessions_on_day >= self.config.max_sessions_per_day - 1:
            return False

        return True

    def _select_best_room(
        self,
        session_template: ScheduleSession,
        date: datetime.date,
        time_slot: TimeSlot,
        existing_occurrences: List[SessionOccurrence]
    ) -> Optional[Room]:
        """Sélectionne la meilleure salle disponible si flexibilité activée"""

        # Si pas de flexibilité pour les salles, garder la salle originale
        if not self.config.respect_room_preferences:
            return None

        course = session_template.course

        # Cherche les salles disponibles qui correspondent aux besoins
        available_rooms = Room.objects.filter(
            is_active=True,
            capacity__gte=session_template.expected_students,
            has_projector=course.requires_projector if course.requires_projector else True,
            has_computer=course.requires_computer if course.requires_computer else True,
            is_laboratory=course.requires_laboratory if course.requires_laboratory else False
        )

        # Exclut les salles déjà occupées à ce créneau et date
        for occ in existing_occurrences:
            if (occ.actual_date == date and
                occ.start_time == time_slot.start_time and
                occ.end_time == time_slot.end_time):
                available_rooms = available_rooms.exclude(id=occ.room.id)

        # Si aucune salle disponible, retourner la salle originale
        if not available_rooms.exists():
            return None

        # Sélectionne la salle la plus adaptée (capacité proche du besoin)
        best_room = min(
            available_rooms,
            key=lambda r: abs(r.capacity - session_template.expected_students)
        )

        return best_room

    def _generate_standard(
        self,
        session_templates: List[ScheduleSession],
        start_date: datetime.date,
        end_date: datetime.date
    ) -> List[SessionOccurrence]:
        """Génération standard sans ML (fallback)"""
        from .generation_service import ScheduleGenerationService

        service = ScheduleGenerationService(self.schedule)
        service.config = self.config

        occurrences = []
        for session_template in session_templates:
            session_occurrences = service._generate_session_occurrences(
                session_template,
                start_date,
                end_date
            )
            occurrences.extend(session_occurrences)

        return occurrences

    def get_generation_stats(self, occurrences: List[SessionOccurrence]) -> Dict:
        """Génère des statistiques sur la génération optimisée"""
        total = len(occurrences)
        if total == 0:
            return {}

        # Compte les modifications
        room_modified = sum(1 for occ in occurrences if occ.is_room_modified)
        teacher_modified = sum(1 for occ in occurrences if occ.is_teacher_modified)
        time_modified = sum(1 for occ in occurrences if occ.is_time_modified)

        # Distribution par jour
        dates = [occ.actual_date for occ in occurrences]
        unique_dates = set(dates)

        sessions_per_day = {
            date: dates.count(date)
            for date in unique_dates
        }

        return {
            'total_occurrences': total,
            'room_optimizations': room_modified,
            'teacher_optimizations': teacher_modified,
            'time_optimizations': time_modified,
            'unique_days': len(unique_dates),
            'avg_sessions_per_day': sum(sessions_per_day.values()) / len(sessions_per_day) if sessions_per_day else 0,
            'max_sessions_per_day': max(sessions_per_day.values()) if sessions_per_day else 0,
            'min_sessions_per_day': min(sessions_per_day.values()) if sessions_per_day else 0,
            'ml_optimized': self.predictor is not None
        }
