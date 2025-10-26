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

TD (Travaux Dirigés) - 30% du volume:
- ✅ Programmer 2-3 jours APRÈS le CM correspondant
- ✅ TD peut être le même jour que le CM si programmé l'après-midi
- ❌ ÉVITER plus de 2h consécutives
- Privilégier l'après-midi (13h-18h)
- Durée: généralement 1h30 à 2h
- Salle moyenne nécessaire
- Maximum 2-3 TD par jour pour un même groupe

TP (Travaux Pratiques) - 20% du volume:
- ✅ Programmer APRÈS CM et TD (ordre obligatoire)
- ✅ Créneaux longs (2-4h pour manipulations)
- ✅ Jeudi/Vendredi idéal pour les TP
- ✅ Bloquer plusieurs créneaux la même semaine pour rotations de groupes
- ✅ Système de rotation équitable entre groupes
- ❌ ÉVITER lundi matin (besoin de préparation)
- Nécessite un laboratoire/salle informatique
- Maximum 1 TP par jour par groupe (fatiguant)

TPE (Travail Personnel Encadré) - 10% du volume:
- ✅ Programmer en milieu/fin de semestre (après acquisitions de base)
- ✅ Créneaux de 1h30 à 2h
- ✅ Vendredi après-midi acceptable (travail autonome)
- ❌ ÉVITER séances trop espacées (perte de fil conducteur)
- Privilégier fin de semaine (jeudi/vendredi)
- Petits groupes
- Peut être en fin de journée

SEMESTRES:
- Semestre 1 (S1): Fin septembre → Fin février
- Semestre 2 (S2): Début mars → Août
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
                preferred_days=[],  # Tous les jours OK si 2-3 jours après CM
                forbidden_days=[],
                min_duration_hours=1.5,
                max_duration_hours=2.0,  # Max 2h consécutives
                requires_predecessor=True,
                predecessor_type='CM',
                max_per_day=3,  # Maximum 2-3 TD par jour
                penalty_weight=0.8
            ),
            'TP': CourseTypeRule(
                course_type='TP',
                preferred_time_ranges=[
                    (time(8, 0), time(17, 0)),  # Toute la journée sauf soir
                ],
                forbidden_time_ranges=[
                    (time(8, 0), time(10, 0)),  # Éviter lundi matin (géré séparément)
                ],
                preferred_days=[3, 4],  # Jeudi/Vendredi idéal pour TP
                forbidden_days=[],
                min_duration_hours=2.0,  # Créneaux longs
                max_duration_hours=4.0,  # Jusqu'à 4h pour manipulations
                requires_predecessor=True,
                predecessor_type='TD',  # APRÈS CM et TD
                max_per_day=1,  # Maximum 1 TP par jour (fatiguant)
                penalty_weight=1.0  # Très important
            ),
            'TPE': CourseTypeRule(
                course_type='TPE',
                preferred_time_ranges=[
                    (time(14, 0), time(18, 0)),  # Vendredi après-midi OK
                ],
                forbidden_time_ranges=[],
                preferred_days=[3, 4],  # Jeudi, Vendredi (travail autonome)
                forbidden_days=[],
                min_duration_hours=1.5,  # Créneaux 1h30 à 2h
                max_duration_hours=2.0,
                requires_predecessor=False,  # Mais programmé en milieu/fin semestre
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
        scheduled_sessions: Dict[str, List[datetime]],
        proposed_date: Optional[datetime] = None
    ) -> Tuple[bool, float]:
        """
        Vérifie si le cours prérequis a été programmé avant
        Pour les TD: vérifie aussi le délai de 2-3 jours après le CM

        Args:
            course_type: Type du cours à planifier
            course_code: Code du cours (ex: "ANAT101")
            scheduled_sessions: Dictionnaire {course_code: [dates_programmées]}
            proposed_date: Date proposée pour ce cours

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

        # Règle spéciale pour TD: 2-3 jours après le CM
        if course_type == 'TD' and proposed_date and scheduled_sessions[predecessor_code]:
            from datetime import timedelta

            # Prendre la date du dernier CM programmé
            last_cm_date = max(scheduled_sessions[predecessor_code])
            days_diff = (proposed_date.date() - last_cm_date.date()).days

            # Optimal: 2-3 jours après
            if 2 <= days_diff <= 3:
                return True, 0.0  # Parfait
            elif 1 <= days_diff <= 5:
                return True, 0.2  # Acceptable avec petite pénalité
            elif days_diff == 0:
                # Même jour acceptable si TD l'après-midi et CM le matin
                if proposed_date.hour >= 13:  # TD l'après-midi
                    return True, 0.1
                return True, 0.5  # Pénalité plus forte
            else:
                return True, 0.6  # Trop tôt ou trop tard

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


# Fonctions utilitaires pour les semestres

def get_semester_from_date(date: datetime) -> str:
    """
    Détermine le semestre en fonction de la date

    Semestre 1 (S1): Fin septembre → Fin février (mois 9, 10, 11, 12, 1, 2)
    Semestre 2 (S2): Début mars → Août (mois 3, 4, 5, 6, 7, 8)

    Args:
        date: Date à vérifier

    Returns:
        'S1' ou 'S2'
    """
    month = date.month

    # S1: Septembre (9) à Février (2)
    if month >= 9 or month <= 2:
        return 'S1'
    # S2: Mars (3) à Août (8)
    else:
        return 'S2'


def is_date_in_semester(date: datetime, semester: str) -> bool:
    """
    Vérifie si une date appartient au semestre spécifié

    Args:
        date: Date à vérifier
        semester: 'S1' ou 'S2'

    Returns:
        True si la date est dans le semestre
    """
    return get_semester_from_date(date) == semester


def get_semester_weeks(date: datetime, semester: str) -> int:
    """
    Calcule la semaine dans le semestre (1-16 environ)
    Utile pour programmer les TPE en milieu/fin de semestre

    Args:
        date: Date à vérifier
        semester: 'S1' ou 'S2'

    Returns:
        Numéro de semaine (1-16)
    """
    from datetime import timedelta

    # Définir les dates de début approximatives
    year = date.year

    if semester == 'S1':
        # S1 commence fin septembre
        if date.month >= 9:
            start_date = datetime(year, 9, 20)
        else:
            start_date = datetime(year - 1, 9, 20)
    else:  # S2
        # S2 commence début mars
        start_date = datetime(year, 3, 1)

    # Calculer la différence en semaines
    week_num = ((date - start_date).days // 7) + 1

    # Limiter entre 1 et 16
    return max(1, min(week_num, 16))


def should_schedule_tpe(date: datetime, semester: str) -> bool:
    """
    Détermine si c'est le bon moment pour programmer un TPE
    TPE doit être programmé en milieu/fin de semestre (semaine 6+)

    Args:
        date: Date proposée
        semester: Semestre du cours

    Returns:
        True si c'est le bon moment pour un TPE
    """
    week = get_semester_weeks(date, semester)

    # TPE à partir de la semaine 6 (milieu de semestre)
    return week >= 6
