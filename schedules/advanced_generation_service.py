# schedules/advanced_generation_service.py
"""
Service de génération avancée d'emploi du temps avec:
- Gestion des priorités (courses programmées par ordre de priorité)
- Préférences de salle pour les classes
- Détection de blocage et suggestions de solutions
- Validation complète avant génération
"""

from datetime import datetime, timedelta, time
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import logging

from django.db import transaction
from django.utils import timezone

from .models import (
    Schedule, ScheduleSession, SessionOccurrence,
    ScheduleGenerationConfig, TimeSlot, Room, Teacher
)
from .course_type_constraints import CourseTypeConstraintChecker
from courses.models import Course
from courses.models_class import StudentClass, ClassCourse, ClassRoomPreference

logger = logging.getLogger(__name__)


@dataclass
class SchedulingAttempt:
    """Représente une tentative de planification"""
    course_code: str
    date: datetime
    time_slot: TimeSlot
    room: Room
    success: bool
    failure_reason: Optional[str] = None
    penalty: float = 0.0


@dataclass
class BlockageInfo:
    """Information sur un blocage de génération"""
    course_code: str
    reasons: List[str]
    suggestions: List[str]
    severity: str  # 'critical', 'high', 'medium'


class AdvancedScheduleGenerator:
    """Générateur avancé d'emploi du temps avec gestion intelligente des contraintes"""

    def __init__(self, schedule: Schedule):
        self.schedule = schedule
        self.config = None
        self.constraint_checker = CourseTypeConstraintChecker()
        self.scheduled_sessions = {}  # {course_code: [dates]}
        self.room_usage = defaultdict(list)  # {(date, room_id): [time_slots]}
        self.teacher_usage = defaultdict(list)  # {(date, teacher_id): [time_slots]}
        self.blockages = []
        self.attempts = []

        self.stats = {
            'occurrences_created': 0,
            'conflicts_detected': 0,
            'course_type_violations': 0,
            'blockages_detected': 0,
            'conflicts': [],
            'generation_time': 0
        }

    def generate_with_validation(
        self,
        preview_mode: bool = False,
        force_regenerate: bool = False,
        date_from: datetime = None,
        date_to: datetime = None
    ) -> Dict:
        """
        Génère l'emploi du temps avec validation complète et gestion des blocages

        Returns:
            Dict avec résultats incluant suggestions si échec
        """
        start_time = timezone.now()

        try:
            self.config = ScheduleGenerationConfig.objects.get(schedule=self.schedule)
        except ScheduleGenerationConfig.DoesNotExist:
            return self._error_response('Aucune configuration de génération trouvée')

        start_date = date_from or self.config.start_date
        end_date = date_to or self.config.end_date

        # Étape 1: Récupérer et trier les sessions par priorité
        session_templates = self._get_prioritized_sessions()

        if not session_templates:
            return self._error_response('Aucune session à planifier')

        # Étape 2: Pré-validation
        validation_result = self._pre_validate(session_templates, start_date, end_date)
        if not validation_result['valid']:
            return {
                'success': False,
                'message': 'Validation échouée avant génération',
                'validation_errors': validation_result['errors'],
                'suggestions': validation_result['suggestions'],
                'blockages': validation_result['blockages']
            }

        # Étape 3: Génération avec backtracking si nécessaire
        occurrences = []
        for session_template in session_templates:
            session_result = self._generate_session_smart(
                session_template,
                start_date,
                end_date,
                existing_occurrences=occurrences
            )

            if session_result['success']:
                occurrences.extend(session_result['occurrences'])
            else:
                # Échec de planification pour ce cours
                self.blockages.append(BlockageInfo(
                    course_code=session_template.course.code,
                    reasons=session_result['reasons'],
                    suggestions=session_result['suggestions'],
                    severity='critical'
                ))

                if not self.config.allow_conflicts:
                    # Arrêter la génération et renvoyer suggestions
                    return self._blockage_response()

        # Étape 4: Vérification finale
        final_validation = self._final_validation(occurrences)

        if not final_validation['valid'] and not self.config.allow_conflicts:
            return {
                'success': False,
                'message': 'Validation finale échouée',
                'conflicts': final_validation['conflicts'],
                'suggestions': final_validation['suggestions']
            }

        # Étape 5: Sauvegarde
        if not preview_mode:
            with transaction.atomic():
                if force_regenerate:
                    SessionOccurrence.objects.filter(
                        session_template__schedule=self.schedule,
                        actual_date__gte=start_date,
                        actual_date__lte=end_date
                    ).delete()

                SessionOccurrence.objects.bulk_create(occurrences)
                self.stats['occurrences_created'] = len(occurrences)

        end_time = timezone.now()
        self.stats['generation_time'] = (end_time - start_time).total_seconds()

        return {
            'success': True,
            'message': f"{len(occurrences)} occurrence(s) générée(s) avec succès",
            'occurrences_created': len(occurrences),
            'conflicts_detected': self.stats['conflicts_detected'],
            'course_type_violations': self.stats['course_type_violations'],
            'blockages_detected': len(self.blockages),
            'conflicts': self.stats['conflicts'],
            'blockages': [self._blockage_to_dict(b) for b in self.blockages],
            'generation_time': self.stats['generation_time'],
            'warnings': self._generate_warnings()
        }

    def _get_prioritized_sessions(self) -> List[ScheduleSession]:
        """Récupère les sessions triées par priorité (haute → basse)"""
        sessions = ScheduleSession.objects.filter(
            schedule=self.schedule,
            is_cancelled=False
        ).select_related('course', 'teacher', 'room', 'time_slot')

        # Trier par priorité effective du cours (1 = haute, 5 = basse)
        return sorted(sessions, key=lambda s: s.course.effective_priority)

    def _pre_validate(
        self,
        sessions: List[ScheduleSession],
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Pré-validation avant génération"""
        errors = []
        suggestions = []
        blockages = []

        # Vérifier les ressources
        all_rooms = Room.objects.filter(is_active=True)
        all_teachers = Teacher.objects.filter(is_active=True)

        if not all_rooms.exists():
            errors.append("Aucune salle active disponible")
            suggestions.append("Activer au moins une salle dans le système")
            blockages.append({
                'type': 'no_rooms',
                'severity': 'critical',
                'message': 'Aucune salle disponible'
            })

        # Vérifier que chaque cours a les ressources nécessaires
        for session in sessions:
            course = session.course

            # Vérifier disponibilité enseignant
            if not session.teacher or not session.teacher.is_active:
                errors.append(f"Cours {course.code}: enseignant non disponible")
                suggestions.append(f"Assigner un enseignant actif au cours {course.code}")
                blockages.append({
                    'course': course.code,
                    'type': 'no_teacher',
                    'severity': 'critical'
                })

            # Vérifier qu'il existe des salles compatibles
            compatible_rooms = self._find_compatible_rooms(course, session)
            if not compatible_rooms:
                errors.append(f"Cours {course.code}: aucune salle compatible")
                suggestions.append(
                    f"Créer/activer des salles avec: capacité ≥ {course.max_students}, "
                    f"ordinateur={course.requires_computer}, "
                    f"labo={course.requires_laboratory}"
                )
                blockages.append({
                    'course': course.code,
                    'type': 'no_compatible_room',
                    'severity': 'critical',
                    'requirements': {
                        'capacity': course.max_students,
                        'computer': course.requires_computer,
                        'laboratory': course.requires_laboratory
                    }
                })

        # Vérifier prérequis de cours
        for session in sessions:
            course_type = session.course.course_type
            course_code = session.course.code

            if course_type in ['TD', 'TP']:
                rule = self.constraint_checker.rules.get(course_type)
                if rule and rule.requires_predecessor:
                    base_code = course_code.split('-')[0]
                    predecessor_code = f"{base_code}-{rule.predecessor_type}"

                    # Vérifier que le prérequis existe
                    has_predecessor = sessions.__class__.objects.filter(
                        schedule=self.schedule,
                        course__code=predecessor_code,
                        is_cancelled=False
                    ).exists()

                    if not has_predecessor:
                        errors.append(
                            f"Cours {course_code}: prérequis {predecessor_code} manquant"
                        )
                        suggestions.append(
                            f"Créer le cours {predecessor_code} avant de planifier {course_code}"
                        )
                        blockages.append({
                            'course': course_code,
                            'type': 'missing_prerequisite',
                            'severity': 'high',
                            'prerequisite': predecessor_code
                        })

        valid = len([b for b in blockages if b.get('severity') == 'critical']) == 0

        return {
            'valid': valid,
            'errors': errors,
            'suggestions': suggestions,
            'blockages': blockages
        }

    def _generate_session_smart(
        self,
        session_template: ScheduleSession,
        start_date: datetime,
        end_date: datetime,
        existing_occurrences: List[SessionOccurrence]
    ) -> Dict:
        """Génère les occurrences pour une session avec gestion intelligente"""
        occurrences = []
        reasons = []
        suggestions = []

        course = session_template.course
        time_slot = session_template.time_slot

        # Calculer nombre d'occurrences nécessaires
        session_start = session_template.specific_start_time or time_slot.start_time
        session_end = session_template.specific_end_time or time_slot.end_time
        session_duration_hours = (
            timezone.datetime.combine(timezone.datetime.today(), session_end) -
            timezone.datetime.combine(timezone.datetime.today(), session_start)
        ).total_seconds() / 3600

        if course.total_hours > 0:
            max_occurrences = int(course.total_hours / session_duration_hours)
        else:
            max_occurrences = None

        # Trouver les dates possibles
        day_mapping = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }
        target_weekday = day_mapping.get(time_slot.day_of_week)

        if target_weekday is None:
            return {
                'success': False,
                'occurrences': [],
                'reasons': [f"Jour invalide: {time_slot.day_of_week}"],
                'suggestions': ["Vérifier la configuration du créneau horaire"]
            }

        # Générer les occurrences
        current_date = start_date
        while current_date.weekday() != target_weekday:
            current_date += timedelta(days=1)

        occurrence_count = 0
        failed_attempts = 0
        max_failures = 10  # Limite de tentatives échouées

        while current_date <= end_date:
            if max_occurrences and occurrence_count >= max_occurrences:
                break

            if failed_attempts >= max_failures:
                reasons.append(f"Trop de tentatives échouées ({failed_attempts})")
                suggestions.append("Augmenter le nombre de salles disponibles ou ajuster les créneaux")
                break

            if self.config.is_date_excluded(current_date):
                current_date += timedelta(days=7)
                continue

            # Tenter de planifier cette occurrence
            attempt_result = self._attempt_scheduling(
                session_template,
                current_date,
                session_start,
                session_end,
                existing_occurrences + occurrences
            )

            if attempt_result.success:
                occurrence = SessionOccurrence(
                    session_template=session_template,
                    actual_date=current_date,
                    start_time=session_start,
                    end_time=session_end,
                    room=attempt_result.room,
                    teacher=session_template.teacher,
                    status='scheduled',
                    is_room_modified=attempt_result.room != session_template.room,
                    is_teacher_modified=False,
                    is_time_modified=False
                )
                occurrences.append(occurrence)
                occurrence_count += 1

                # Track pour prérequis
                if course.code not in self.scheduled_sessions:
                    self.scheduled_sessions[course.code] = []
                self.scheduled_sessions[course.code].append(current_date)

                failed_attempts = 0  # Reset compteur
            else:
                failed_attempts += 1
                if attempt_result.failure_reason:
                    reasons.append(f"{current_date.strftime('%Y-%m-%d')}: {attempt_result.failure_reason}")

            current_date += timedelta(days=7)

        # Vérifier si on a réussi à créer suffisamment d'occurrences
        if max_occurrences and occurrence_count < max_occurrences * 0.8:  # 80% minimum
            return {
                'success': False,
                'occurrences': occurrences,  # Retourner quand même ce qu'on a
                'reasons': reasons + [f"Seulement {occurrence_count}/{max_occurrences} occurrences créées"],
                'suggestions': suggestions + [
                    "Augmenter la période de génération",
                    "Ajouter plus de salles compatibles",
                    "Vérifier les conflits avec d'autres cours"
                ]
            }

        return {
            'success': True,
            'occurrences': occurrences,
            'reasons': [],
            'suggestions': []
        }

    def _attempt_scheduling(
        self,
        session_template: ScheduleSession,
        date: datetime,
        start_time: time,
        end_time: time,
        existing_occurrences: List[SessionOccurrence]
    ) -> SchedulingAttempt:
        """Tente de planifier une occurrence à une date donnée"""
        course = session_template.course
        course_type = course.course_type
        course_code = course.code

        # Vérifie contraintes de type de cours
        is_valid_time, time_penalty = self.constraint_checker.check_time_preference(course_type, start_time)
        is_valid_day, day_penalty = self.constraint_checker.check_day_preference(course_type, date.weekday())
        is_valid_prereq, prereq_penalty = self.constraint_checker.check_prerequisite(
            course_type, course_code, self.scheduled_sessions
        )
        is_valid_max, max_penalty = self.constraint_checker.check_max_per_day(
            course_type, date.date(), course_code, self.scheduled_sessions
        )

        # Rejeter si contraintes critiques violées
        if not is_valid_time:
            return SchedulingAttempt(
                course_code=course_code,
                date=date,
                time_slot=session_template.time_slot,
                room=None,
                success=False,
                failure_reason="Horaire interdit pour ce type de cours",
                penalty=time_penalty
            )

        if not is_valid_prereq and not self.config.allow_conflicts:
            rule = self.constraint_checker.rules.get(course_type)
            return SchedulingAttempt(
                course_code=course_code,
                date=date,
                time_slot=session_template.time_slot,
                room=None,
                success=False,
                failure_reason=f"Prérequis {rule.predecessor_type} non programmé",
                penalty=prereq_penalty
            )

        # Trouver salle compatible
        room = self._find_best_room(session_template, date, start_time, end_time, existing_occurrences)

        if not room:
            return SchedulingAttempt(
                course_code=course_code,
                date=date,
                time_slot=session_template.time_slot,
                room=None,
                success=False,
                failure_reason="Aucune salle compatible disponible"
            )

        # Vérifier enseignant
        teacher_available = self._check_teacher_available(
            session_template.teacher, date, start_time, end_time, existing_occurrences
        )

        if not teacher_available:
            return SchedulingAttempt(
                course_code=course_code,
                date=date,
                time_slot=session_template.time_slot,
                room=room,
                success=False,
                failure_reason="Enseignant non disponible"
            )

        # Succès!
        total_penalty = time_penalty + day_penalty + prereq_penalty + max_penalty
        return SchedulingAttempt(
            course_code=course_code,
            date=date,
            time_slot=session_template.time_slot,
            room=room,
            success=True,
            penalty=total_penalty
        )

    def _find_best_room(
        self,
        session_template: ScheduleSession,
        date: datetime,
        start_time: time,
        end_time: time,
        existing_occurrences: List[SessionOccurrence]
    ) -> Optional[Room]:
        """Trouve la meilleure salle en tenant compte des préférences de classe"""
        course = session_template.course

        # Récupérer les classes assignées
        class_courses = ClassCourse.objects.filter(
            course=course,
            is_active=True
        ).select_related('student_class')

        # Récupérer préférences de salle des classes
        class_room_prefs = {}
        for cc in class_courses:
            prefs = ClassRoomPreference.objects.filter(
                student_class=cc.student_class,
                is_active=True
            ).select_related('room')
            class_room_prefs[cc.student_class.id] = list(prefs)

        # Trouver salles compatibles
        compatible_rooms = self._find_compatible_rooms(course, session_template)

        # Exclure salles occupées
        occupied_room_ids = set()
        for occ in existing_occurrences:
            if occ.actual_date == date and self._has_time_overlap(
                occ.start_time, occ.end_time, start_time, end_time
            ):
                occupied_room_ids.add(occ.room.id)

        available_rooms = [r for r in compatible_rooms if r.id not in occupied_room_ids]

        if not available_rooms:
            return None

        # Scorer les salles selon préférences
        def score_room(room):
            score = 0

            # Préférences de classe (priorité haute)
            for student_class_id, prefs in class_room_prefs.items():
                for pref in prefs:
                    if pref.room.id == room.id:
                        if pref.priority == 1:  # Obligatoire
                            score += 1000
                        elif pref.priority == 2:  # Préférée
                            score += 100
                        elif pref.priority == 3:  # Acceptable
                            score += 10

            # Capacité (plus proche = mieux)
            capacity_diff = abs(room.capacity - course.max_students)
            score -= capacity_diff

            # Utilisation (moins utilisé = mieux)
            usage_key = (date, room.id)
            usage_count = len(self.room_usage.get(usage_key, []))
            score -= usage_count * 50

            return score

        # Retourner salle avec meilleur score
        best_room = max(available_rooms, key=score_room)
        return best_room

    def _find_compatible_rooms(self, course: Course, session: ScheduleSession) -> List[Room]:
        """Trouve les salles compatibles avec le cours"""
        rooms = Room.objects.filter(is_active=True, capacity__gte=course.max_students)

        if course.requires_computer:
            rooms = rooms.filter(has_computer=True)
        if course.requires_projector:
            rooms = rooms.filter(has_projector=True)
        if course.requires_laboratory:
            rooms = rooms.filter(is_laboratory=True)

        return list(rooms)

    def _check_teacher_available(
        self,
        teacher: Teacher,
        date: datetime,
        start_time: time,
        end_time: time,
        existing_occurrences: List[SessionOccurrence]
    ) -> bool:
        """Vérifie si l'enseignant est disponible"""
        for occ in existing_occurrences:
            if (occ.teacher.id == teacher.id and
                occ.actual_date == date and
                self._has_time_overlap(occ.start_time, occ.end_time, start_time, end_time)):
                return False
        return True

    def _has_time_overlap(self, start1: time, end1: time, start2: time, end2: time) -> bool:
        """Vérifie chevauchement horaire"""
        from datetime import datetime, timedelta
        today = datetime.today().date()
        dt_start1 = datetime.combine(today, start1)
        dt_end1 = datetime.combine(today, end1)
        dt_start2 = datetime.combine(today, start2)
        dt_end2 = datetime.combine(today, end2)

        buffer = timedelta(minutes=5)
        return not (dt_end1 + buffer <= dt_start2 or dt_end2 + buffer <= dt_start1)

    def _final_validation(self, occurrences: List[SessionOccurrence]) -> Dict:
        """Validation finale avant sauvegarde"""
        conflicts = []
        suggestions = []

        # Vérifier doublons
        occurrence_keys = set()
        for occ in occurrences:
            key = (occ.actual_date, occ.start_time, occ.room.id)
            if key in occurrence_keys:
                conflicts.append({
                    'type': 'duplicate',
                    'date': str(occ.actual_date),
                    'time': str(occ.start_time),
                    'room': occ.room.code
                })
            occurrence_keys.add(key)

        valid = len(conflicts) == 0

        return {
            'valid': valid,
            'conflicts': conflicts,
            'suggestions': suggestions
        }

    def _blockage_response(self) -> Dict:
        """Génère une réponse avec informations de blocage et suggestions"""
        return {
            'success': False,
            'message': f"{len(self.blockages)} cours ne peuvent pas être programmés",
            'blockages': [self._blockage_to_dict(b) for b in self.blockages],
            'suggestions': self._generate_suggestions(),
            'occurrences_created': 0
        }

    def _blockage_to_dict(self, blockage: BlockageInfo) -> Dict:
        """Convertit BlockageInfo en dictionnaire"""
        return {
            'course': blockage.course_code,
            'reasons': blockage.reasons,
            'suggestions': blockage.suggestions,
            'severity': blockage.severity
        }

    def _generate_suggestions(self) -> List[str]:
        """Génère des suggestions globales basées sur les blocages"""
        suggestions = set()

        for blockage in self.blockages:
            suggestions.update(blockage.suggestions)

        # Suggestions générales
        if len(self.blockages) > 3:
            suggestions.add("Envisager d'ajouter plus de salles au système")
            suggestions.add("Augmenter la période de génération (plus de semaines)")

        return list(suggestions)

    def _generate_warnings(self) -> List[Dict]:
        """Génère des warnings sur la qualité de l'emploi du temps"""
        warnings = []

        # Analyser les pénalités
        high_penalty_count = sum(1 for a in self.attempts if a.penalty > 0.5)
        if high_penalty_count > 0:
            warnings.append({
                'type': 'quality',
                'message': f"{high_penalty_count} créneaux sous-optimaux",
                'suggestion': "Réviser les créneaux horaires pour respecter les préférences"
            })

        return warnings

    def _error_response(self, message: str) -> Dict:
        """Génère une réponse d'erreur standard"""
        return {
            'success': False,
            'message': message,
            'occurrences_created': 0,
            'conflicts_detected': 0,
            'generation_time': 0
        }
