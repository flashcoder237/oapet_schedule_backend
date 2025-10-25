# schedules/course_type_constraints.py
"""
Contraintes spécifiques par type de cours pour la génération d'emploi du temps

Règles pédagogiques par type de cours:
=======================================

CM (Cours Magistral):
- Peut être programmé n'importe quel jour
- Privilégier le matin (8h-12h)
- Durée: généralement 1h30 à 3h
- Grande salle nécessaire (amphithéâtre)
- Peut être programmé en début de semaine

TD (Travaux Dirigés):
- DOIT suivre le CM correspondant (dans la même semaine ou la semaine suivante)
- Privilégier l'après-midi
- Durée: généralement 1h30 à 2h
- Salle moyenne nécessaire
- Maximum 2-3 TD par jour pour un même groupe

TP (Travaux Pratiques):
- DOIT suivre le TD correspondant (obligatoire)
- Nécessite une préparation donc pas le lundi matin
- Durée: minimum 2h, souvent 3h
- Nécessite un laboratoire/salle informatique
- Maximum 1 TP par jour par groupe (fatiguant)
- Éviter vendredi après-midi si possible

TPE (Travail Personnel Encadré):
- Peut être programmé à tout moment
- Privilégier fin de semaine (jeudi/vendredi)
- Durée: généralement 1h à 2h
- Petits groupes
- Peut être en fin de journée
"""

from datetime import datetime, time
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class CourseTypeRule:
    """Définit les règles pour un type de cours"""
    course_type: str
    preferred_time_ranges: List[Tuple[time, time]]  # Plages horaires préférées
    forbidden_time_ranges: List[Tuple[time, time]]  # Plages interdites
    preferred_days: List[int]  # 0=Lundi, 6=Dimanche
    forbidden_days: List[int]
    min_duration_hours: float
    max_duration_hours: float
    requires_predecessor: bool  # Nécessite un cours précédent
    predecessor_type: Optional[str]  # Type de cours qui doit précéder
    max_per_day: int  # Maximum d'occurrences par jour pour un groupe
    penalty_weight: float  # Poids de pénalité si règle non respectée


class CourseTypeConstraintChecker:
    """Vérifie les contraintes spécifiques aux types de cours"""

    def __init__(self):
        self.rules = self._initialize_rules()

    def _initialize_rules(self) -> Dict[str, CourseTypeRule]:
        """Initialise les règles pour chaque type de cours"""
        return {
            'CM': CourseTypeRule(
                course_type='CM',
                preferred_time_ranges=[
                    (time(8, 0), time(12, 0)),  # Matin privilégié
                ],
                forbidden_time_ranges=[],
                preferred_days=[0, 1, 2],  # Lundi, Mardi, Mercredi
                forbidden_days=[],
                min_duration_hours=1.5,
                max_duration_hours=3.0,
                requires_predecessor=False,
                predecessor_type=None,
                max_per_day=2,
                penalty_weight=0.5
            ),
            'TD': CourseTypeRule(
                course_type='TD',
                preferred_time_ranges=[
                    (time(13, 0), time(18, 0)),  # Après-midi privilégié
                ],
                forbidden_time_ranges=[],
                preferred_days=[],
                forbidden_days=[],
                min_duration_hours=1.5,
                max_duration_hours=2.0,
                requires_predecessor=True,
                predecessor_type='CM',
                max_per_day=3,
                penalty_weight=0.8
            ),
            'TP': CourseTypeRule(
                course_type='TP',
                preferred_time_ranges=[
                    (time(13, 0), time(17, 0)),  # Après-midi préféré
                ],
                forbidden_time_ranges=[
                    (time(17, 0), time(19, 0)),  # Éviter fin de journée
                ],
                preferred_days=[1, 2, 3, 4],  # Mardi à Vendredi préférés
                forbidden_days=[],  # Lundi autorisé mais pas optimal (préférence gérée par preferred_days)
                min_duration_hours=2.0,
                max_duration_hours=4.0,
                requires_predecessor=True,
                predecessor_type='TD',
                max_per_day=1,  # Maximum 1 TP par jour
                penalty_weight=1.0  # Très important
            ),
            'TPE': CourseTypeRule(
                course_type='TPE',
                preferred_time_ranges=[
                    (time(14, 0), time(18, 0)),
                ],
                forbidden_time_ranges=[],
                preferred_days=[3, 4],  # Jeudi, Vendredi
                forbidden_days=[],
                min_duration_hours=1.0,
                max_duration_hours=2.0,
                requires_predecessor=False,
                predecessor_type=None,
                max_per_day=2,
                penalty_weight=0.3
            ),
            'CONF': CourseTypeRule(
                course_type='CONF',
                preferred_time_ranges=[
                    (time(10, 0), time(12, 0)),
                    (time(14, 0), time(16, 0)),
                ],
                forbidden_time_ranges=[],
                preferred_days=[],
                forbidden_days=[],
                min_duration_hours=1.0,
                max_duration_hours=2.0,
                requires_predecessor=False,
                predecessor_type=None,
                max_per_day=1,
                penalty_weight=0.4
            ),
            'EXAM': CourseTypeRule(
                course_type='EXAM',
                preferred_time_ranges=[
                    (time(8, 0), time(12, 0)),  # Matin pour les examens
                ],
                forbidden_time_ranges=[
                    (time(17, 0), time(19, 0)),
                ],
                preferred_days=[],
                forbidden_days=[0],  # Pas d'examen le lundi
                min_duration_hours=1.0,
                max_duration_hours=4.0,
                requires_predecessor=False,
                predecessor_type=None,
                max_per_day=1,
                penalty_weight=0.9
            ),
        }

    def check_time_preference(
        self,
        course_type: str,
        scheduled_time: time
    ) -> Tuple[bool, float]:
        """
        Vérifie si l'horaire respecte les préférences du type de cours

        Returns:
            (is_valid, penalty): True si valide, pénalité entre 0 et 1
        """
        if course_type not in self.rules:
            return True, 0.0

        rule = self.rules[course_type]

        # Vérifie les plages interdites
        for start, end in rule.forbidden_time_ranges:
            if start <= scheduled_time <= end:
                return False, rule.penalty_weight

        # Vérifie les plages préférées
        is_preferred = False
        for start, end in rule.preferred_time_ranges:
            if start <= scheduled_time <= end:
                is_preferred = True
                break

        if not is_preferred and rule.preferred_time_ranges:
            # Pénalité partielle si hors plage préférée
            return True, rule.penalty_weight * 0.5

        return True, 0.0

    def check_day_preference(
        self,
        course_type: str,
        weekday: int
    ) -> Tuple[bool, float]:
        """
        Vérifie si le jour respecte les préférences du type de cours

        Args:
            weekday: 0=Lundi, 6=Dimanche

        Returns:
            (is_valid, penalty)
        """
        if course_type not in self.rules:
            return True, 0.0

        rule = self.rules[course_type]

        # Vérifie les jours interdits
        if weekday in rule.forbidden_days:
            return False, rule.penalty_weight

        # Vérifie les jours préférés
        if rule.preferred_days and weekday not in rule.preferred_days:
            return True, rule.penalty_weight * 0.3

        return True, 0.0

    def check_prerequisite(
        self,
        course_type: str,
        course_code: str,
        scheduled_sessions: Dict[str, List[datetime]]
    ) -> Tuple[bool, float]:
        """
        Vérifie si le cours prérequis a été programmé avant

        Args:
            course_type: Type du cours à planifier
            course_code: Code du cours (ex: "ANAT101")
            scheduled_sessions: Dictionnaire {course_code: [dates_programmées]}

        Returns:
            (is_valid, penalty)
        """
        if course_type not in self.rules:
            return True, 0.0

        rule = self.rules[course_type]

        if not rule.requires_predecessor:
            return True, 0.0

        # Extrait le code de base (sans le suffixe -TD, -TP, etc.)
        base_code = course_code.split('-')[0]
        predecessor_code = f"{base_code}-{rule.predecessor_type}"

        # Vérifie si le cours prérequis existe et a été programmé
        if predecessor_code not in scheduled_sessions:
            return False, rule.penalty_weight

        # Le prérequis doit avoir au moins une session programmée
        if not scheduled_sessions[predecessor_code]:
            return False, rule.penalty_weight

        return True, 0.0

    def check_max_per_day(
        self,
        course_type: str,
        date: datetime.date,
        course_code: str,
        scheduled_sessions: Dict[str, List[datetime]]
    ) -> Tuple[bool, float]:
        """
        Vérifie le nombre maximum de sessions du même type par jour

        Returns:
            (is_valid, penalty)
        """
        if course_type not in self.rules:
            return True, 0.0

        rule = self.rules[course_type]

        # Compte les sessions du même cours le même jour
        if course_code not in scheduled_sessions:
            return True, 0.0

        sessions_on_date = [
            s for s in scheduled_sessions[course_code]
            if s.date() == date
        ]

        if len(sessions_on_date) >= rule.max_per_day:
            return False, rule.penalty_weight * 0.7

        return True, 0.0

    def calculate_penalty(
        self,
        course_type: str,
        scheduled_time: time,
        weekday: int,
        date: datetime.date,
        course_code: str,
        scheduled_sessions: Dict[str, List[datetime]]
    ) -> float:
        """
        Calcule la pénalité totale pour une session programmée

        Returns:
            Pénalité totale (0 = parfait, plus élevé = pire)
        """
        total_penalty = 0.0

        # Vérifie chaque contrainte
        _, time_penalty = self.check_time_preference(course_type, scheduled_time)
        total_penalty += time_penalty

        _, day_penalty = self.check_day_preference(course_type, weekday)
        total_penalty += day_penalty

        _, prereq_penalty = self.check_prerequisite(course_type, course_code, scheduled_sessions)
        total_penalty += prereq_penalty

        _, max_per_day_penalty = self.check_max_per_day(course_type, date, course_code, scheduled_sessions)
        total_penalty += max_per_day_penalty

        return total_penalty

    def get_recommendations(self, course_type: str) -> Dict[str, any]:
        """
        Retourne les recommandations pour un type de cours

        Returns:
            Dictionnaire avec les recommandations
        """
        if course_type not in self.rules:
            return {}

        rule = self.rules[course_type]

        return {
            'preferred_times': rule.preferred_time_ranges,
            'forbidden_times': rule.forbidden_time_ranges,
            'preferred_days': rule.preferred_days,
            'forbidden_days': rule.forbidden_days,
            'duration_range': (rule.min_duration_hours, rule.max_duration_hours),
            'requires_predecessor': rule.requires_predecessor,
            'predecessor_type': rule.predecessor_type,
            'max_per_day': rule.max_per_day
        }
