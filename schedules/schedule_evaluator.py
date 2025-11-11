"""
Module d'évaluation de la qualité des emplois du temps
Implémente une fonction objective globale pour mesurer la qualité
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import logging

from .models import Schedule, ScheduleSession, SessionOccurrence
from courses.models import Course, Teacher
from rooms.models import Room

logger = logging.getLogger('schedules.evaluator')


class ScheduleEvaluator:
    """
    Évalue la qualité d'un emploi du temps selon plusieurs critères

    Retourne un score global (plus élevé = meilleur)
    Retourne -∞ si contraintes dures violées
    """

    # Poids configurables par critère
    DEFAULT_WEIGHTS = {
        'hard_constraints': 1000,        # Violations critiques
        'pedagogical_quality': 100,      # Qualité pédagogique
        'teacher_satisfaction': 50,      # Satisfaction enseignants
        'room_utilization': 30,          # Utilisation salles
        'student_load_balance': 40,      # Équilibre charge étudiants
        'teacher_load_balance': 45,      # Équilibre charge enseignants
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Args:
            weights: Poids personnalisés pour chaque critère
        """
        self.weights = weights or self.DEFAULT_WEIGHTS

    def evaluate(self, schedule: Schedule) -> float:
        """
        Évalue un emploi du temps complet

        Args:
            schedule: L'emploi du temps à évaluer

        Returns:
            Score global (float). -∞ si solution invalide.
        """
        logger.info(f"Évaluation de l'emploi du temps: {schedule.name}")

        # Phase 1: Vérifier contraintes dures (violations critiques)
        hard_violations = self._check_hard_constraints(schedule)

        if hard_violations['total'] > 0:
            logger.warning(
                f"Contraintes dures violées: {hard_violations['total']} violations"
            )
            return float('-inf')  # Solution invalide

        # Phase 2: Calculer scores des contraintes souples
        score = 0.0

        # 1. Qualité pédagogique
        ped_score = self._evaluate_pedagogical_quality(schedule)
        score += ped_score * self.weights['pedagogical_quality']
        logger.debug(f"Score pédagogique: {ped_score}")

        # 2. Satisfaction enseignants
        teacher_score = self._evaluate_teacher_satisfaction(schedule)
        score += teacher_score * self.weights['teacher_satisfaction']
        logger.debug(f"Score enseignants: {teacher_score}")

        # 3. Utilisation des salles
        room_score = self._evaluate_room_utilization(schedule)
        score += room_score * self.weights['room_utilization']
        logger.debug(f"Score salles: {room_score}")

        # 4. Équilibre charge étudiants
        student_balance_score = self._evaluate_student_load_balance(schedule)
        score += student_balance_score * self.weights['student_load_balance']
        logger.debug(f"Score équilibre étudiants: {student_balance_score}")

        # 5. Équilibre charge enseignants
        teacher_balance_score = self._evaluate_teacher_load_balance(schedule)
        score += teacher_balance_score * self.weights['teacher_load_balance']
        logger.debug(f"Score équilibre enseignants: {teacher_balance_score}")

        logger.info(f"Score global: {score:.2f}")
        return score

    def _check_hard_constraints(self, schedule: Schedule) -> Dict:
        """
        Vérifie les contraintes dures (violations critiques)

        Returns:
            Dict avec compteurs de violations par type
        """
        violations = {
            'room_conflicts': 0,
            'teacher_conflicts': 0,
            'missing_course_hours': 0,
            'total': 0
        }

        sessions = schedule.sessions.select_related('course', 'teacher', 'room').all()

        # 1. Vérifier conflits de salles
        room_conflicts = self._check_room_conflicts(sessions)
        violations['room_conflicts'] = len(room_conflicts)

        # 2. Vérifier conflits d'enseignants
        teacher_conflicts = self._check_teacher_conflicts(sessions)
        violations['teacher_conflicts'] = len(teacher_conflicts)

        # 3. Vérifier que tous les cours ont leurs heures requises
        missing_hours = self._check_missing_course_hours(schedule)
        violations['missing_course_hours'] = len(missing_hours)

        violations['total'] = sum([
            violations['room_conflicts'],
            violations['teacher_conflicts'],
            violations['missing_course_hours']
        ])

        return violations

    def _check_room_conflicts(self, sessions: List[ScheduleSession]) -> List[Tuple]:
        """Détecte les doubles réservations de salles"""
        conflicts = []

        # Grouper par date + créneau
        bookings = defaultdict(list)
        for session in sessions:
            if session.specific_date and session.specific_start_time:
                key = (session.specific_date, session.specific_start_time, session.room_id)
                bookings[key].append(session)

        # Détecter doublons
        for key, sessions_list in bookings.items():
            if len(sessions_list) > 1:
                conflicts.append((key, sessions_list))

        return conflicts

    def _check_teacher_conflicts(self, sessions: List[ScheduleSession]) -> List[Tuple]:
        """Détecte les doubles réservations d'enseignants"""
        conflicts = []

        # Grouper par date + créneau
        assignments = defaultdict(list)
        for session in sessions:
            if session.teacher and session.specific_date and session.specific_start_time:
                key = (session.specific_date, session.specific_start_time, session.teacher_id)
                assignments[key].append(session)

        # Détecter doublons
        for key, sessions_list in assignments.items():
            if len(sessions_list) > 1:
                conflicts.append((key, sessions_list))

        return conflicts

    def _check_missing_course_hours(self, schedule: Schedule) -> List[Dict]:
        """Vérifie que tous les cours ont leurs heures requises"""
        missing = []

        # Récupérer tous les cours de la classe
        if not schedule.student_class:
            return missing

        student_class = schedule.student_class
        # Accéder aux cours via la relation ClassCourse
        class_courses = student_class.class_courses.select_related('course').all()
        courses = [cc.course for cc in class_courses]

        # Calculer heures planifiées par cours
        sessions = schedule.sessions.select_related('course').all()
        hours_scheduled = defaultdict(float)

        for session in sessions:
            if session.specific_start_time and session.specific_end_time:
                duration = (
                    datetime.combine(datetime.today(), session.specific_end_time) -
                    datetime.combine(datetime.today(), session.specific_start_time)
                ).total_seconds() / 3600
                hours_scheduled[session.course_id] += duration

        # Comparer avec heures requises
        for course in courses:
            scheduled = hours_scheduled.get(course.id, 0)
            required = course.total_hours

            if scheduled < required:
                missing.append({
                    'course': course,
                    'required': required,
                    'scheduled': scheduled,
                    'deficit': required - scheduled
                })

        return missing

    def _evaluate_pedagogical_quality(self, schedule: Schedule) -> float:
        """
        Évalue la qualité pédagogique

        Critères:
        - CM le matin (8h-12h)
        - TD milieu de journée (10h-16h)
        - TP après-midi (14h-18h)
        - Respect délais CM → TD → TP
        """
        from .pedagogical_sequencing import PedagogicalSequencer

        score = 0.0
        sessions = schedule.sessions.select_related('course').all()

        if not sessions:
            return 0.0

        for session in sessions:
            if not session.specific_start_time or not session.session_type:
                continue

            # Score horaire
            time_score = PedagogicalSequencer.calculate_time_score(
                session.session_type,
                session.specific_start_time
            )
            score += time_score

            # Score jour de la semaine
            if session.specific_date:
                day_name = session.specific_date.strftime('%A').lower()
                day_score = PedagogicalSequencer.calculate_day_score(
                    session.session_type,
                    day_name
                )
                score += day_score

        # Normaliser par nombre de sessions
        return score / len(sessions) if sessions else 0.0

    def _evaluate_teacher_satisfaction(self, schedule: Schedule) -> float:
        """
        Évalue la satisfaction des enseignants

        Critères:
        - Minimiser les trous dans l'emploi du temps
        - Respecter les préférences horaires
        - Charge équilibrée par semaine
        """
        score = 0.0
        sessions = schedule.sessions.select_related('teacher').all()

        # Grouper par enseignant
        teachers_sessions = defaultdict(list)
        for session in sessions:
            if session.teacher:
                teachers_sessions[session.teacher_id].append(session)

        for teacher_id, teacher_sessions in teachers_sessions.items():
            # Pénaliser les trous dans l'emploi du temps
            gaps_penalty = self._count_schedule_gaps(teacher_sessions)
            score -= gaps_penalty * 10

        return score

    def _count_schedule_gaps(self, sessions: List[ScheduleSession]) -> int:
        """
        Compte les trous (gaps) dans l'emploi du temps

        Un trou = créneau libre entre deux sessions le même jour
        """
        gaps = 0

        # Grouper par date
        by_date = defaultdict(list)
        for session in sessions:
            if session.specific_date:
                by_date[session.specific_date].append(session)

        # Pour chaque jour, trier par heure et compter les trous
        for date, day_sessions in by_date.items():
            sorted_sessions = sorted(
                day_sessions,
                key=lambda s: s.specific_start_time or datetime.min.time()
            )

            for i in range(len(sorted_sessions) - 1):
                current = sorted_sessions[i]
                next_session = sorted_sessions[i + 1]

                if current.specific_end_time and next_session.specific_start_time:
                    # Calculer l'écart
                    gap = (
                        datetime.combine(date, next_session.specific_start_time) -
                        datetime.combine(date, current.specific_end_time)
                    )

                    # Si l'écart > 1h, c'est un trou
                    if gap.total_seconds() > 3600:
                        gaps += 1

        return gaps

    def _evaluate_room_utilization(self, schedule: Schedule) -> float:
        """
        Évalue l'utilisation des salles

        Objectif: salles utilisées ~70% du temps (ni trop, ni trop peu)
        """
        score = 0.0
        sessions = schedule.sessions.select_related('room').all()

        # Calculer taux d'utilisation par salle
        room_usage = defaultdict(int)
        total_slots = 0

        for session in sessions:
            if session.room:
                room_usage[session.room_id] += 1
                total_slots += 1

        # Pénaliser écarts à 70% d'utilisation
        target_usage = 0.7
        for room_id, usage_count in room_usage.items():
            usage_rate = usage_count / total_slots if total_slots > 0 else 0
            deviation = abs(usage_rate - target_usage)
            score -= deviation * 100

        return score

    def _evaluate_student_load_balance(self, schedule: Schedule) -> float:
        """
        Évalue l'équilibre de la charge étudiants

        Objectif: journées équilibrées (4-6h par jour idéal)
        """
        score = 0.0
        sessions = schedule.sessions.all()

        # Grouper par date
        by_date = defaultdict(list)
        for session in sessions:
            if session.specific_date:
                by_date[session.specific_date].append(session)

        # Évaluer chaque jour
        for date, day_sessions in by_date.items():
            # Calculer heures totales du jour
            daily_hours = 0.0
            for session in day_sessions:
                if session.specific_start_time and session.specific_end_time:
                    duration = (
                        datetime.combine(date, session.specific_end_time) -
                        datetime.combine(date, session.specific_start_time)
                    ).total_seconds() / 3600
                    daily_hours += duration

            # Pénaliser écarts à 4-6h
            if daily_hours > 6:
                score -= (daily_hours - 6) * 50  # Journée trop chargée
            elif daily_hours < 4:
                score -= (4 - daily_hours) * 30  # Journée trop légère
            else:
                score += 50  # Journée équilibrée

        return score

    def _evaluate_teacher_load_balance(self, schedule: Schedule) -> float:
        """
        Évalue l'équilibre de la charge enseignants

        Objectif: charge équilibrée par semaine (pas de surcharge)
        """
        score = 0.0
        sessions = schedule.sessions.select_related('teacher').all()

        # Grouper par enseignant et par semaine
        teacher_weekly_hours = defaultdict(lambda: defaultdict(float))

        for session in sessions:
            if session.teacher and session.specific_date:
                # Identifier la semaine
                week_key = session.specific_date.isocalendar()[:2]  # (année, semaine)

                # Calculer durée
                if session.specific_start_time and session.specific_end_time:
                    duration = (
                        datetime.combine(datetime.today(), session.specific_end_time) -
                        datetime.combine(datetime.today(), session.specific_start_time)
                    ).total_seconds() / 3600

                    teacher_weekly_hours[session.teacher_id][week_key] += duration

        # Évaluer chaque enseignant
        for teacher_id, weeks in teacher_weekly_hours.items():
            for week, hours in weeks.items():
                # Pénaliser surcharge (>20h/semaine)
                if hours > 20:
                    score -= (hours - 20) * 100
                # Bonus pour charge normale (12-18h)
                elif 12 <= hours <= 18:
                    score += 50

        return score

    def get_detailed_report(self, schedule: Schedule) -> Dict:
        """
        Génère un rapport détaillé de l'évaluation

        Returns:
            Dict avec scores détaillés par critère
        """
        # Évaluer et convertir -inf en 0 pour JSON
        global_score = self.evaluate(schedule)
        global_score_safe = 0 if global_score == float('-inf') else global_score

        report = {
            'schedule_id': schedule.id,
            'schedule_name': schedule.name,
            'global_score': global_score_safe,
            'hard_constraints': self._check_hard_constraints(schedule),
            'soft_scores': {
                'pedagogical_quality': self._evaluate_pedagogical_quality(schedule),
                'teacher_satisfaction': self._evaluate_teacher_satisfaction(schedule),
                'room_utilization': self._evaluate_room_utilization(schedule),
                'student_load_balance': self._evaluate_student_load_balance(schedule),
                'teacher_load_balance': self._evaluate_teacher_load_balance(schedule),
            },
            'weights': self.weights,
        }

        return report
