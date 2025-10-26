"""
Optimiseur pédagogique pour la génération d'emplois du temps
Basé sur les bonnes pratiques universitaires et recherches sur la concentration étudiante
"""

from datetime import time as dt_time


def get_session_priority_score(session_type, time_slot):
    """
    Calculer un score de priorité selon le type de cours et l'heure.
    Score élevé = meilleure adéquation pédagogique.

    Basé sur les recherches:
    - Concentration maximale le matin (8h-12h)
    - Diminution de 30% l'après-midi
    - Pensée critique optimale 14h-17h
    - Attention soutenue: 10-18 minutes

    Args:
        session_type (str): Type de session ('CM', 'TD', 'TP', 'TPE', 'EXAM')
        time_slot: TimeSlot object avec start_time

    Returns:
        int: Score de priorité (0-100)
    """
    hour = time_slot.start_time.hour

    scores = {
        'CM': {
            # CM (Cours Magistral) - Contenu théorique nouveau
            # Optimal le matin: concentration maximale, cerveau frais
            (8, 12): 100,   # Excellent (matin)
            (12, 14): 40,   # Mauvais (pause déjeuner)
            (14, 16): 50,   # Moyen (début après-midi)
            (16, 18): 20,   # Mauvais (fin après-midi, fatigue)
            (18, 20): 10,   # Très mauvais (soir)
        },
        'TD': {
            # TD (Travaux Dirigés) - Approfondissement et connexions
            # Optimal après-midi: intégration des connaissances
            (8, 12): 60,    # Moyen (matin - préférer CM)
            (12, 14): 30,   # Mauvais (pause déjeuner)
            (14, 17): 100,  # Excellent (après-midi - pensée critique)
            (17, 18): 70,   # Bon (fin après-midi)
            (18, 20): 40,   # Moyen (soir)
        },
        'TP': {
            # TP (Travaux Pratiques) - Mise en pratique
            # Optimal après-midi: disponibilité labos et pratique
            (8, 12): 40,    # Faible (matin - labos occupés/préparation)
            (12, 14): 20,   # Mauvais (pause déjeuner)
            (14, 18): 100,  # Excellent (après-midi - disponibilité optimale)
            (18, 20): 60,   # Moyen (soir - acceptable pour TP)
        },
        'TPE': {
            # TPE (Travaux Personnels Encadrés) - Autonomie
            # Optimal fin après-midi: travail collaboratif
            (8, 12): 30,    # Faible (matin - préférer cours formels)
            (12, 14): 20,   # Mauvais (pause déjeuner)
            (14, 16): 60,   # Moyen (après-midi)
            (16, 18): 100,  # Excellent (fin après-midi - collaboration)
            (18, 20): 80,   # Bon (soir - acceptable)
        },
        'EXAM': {
            # Examens - Concentration maximale requise
            # Optimal le matin: attention optimale
            (8, 12): 100,   # Excellent (matin)
            (12, 14): 20,   # Très mauvais (pause déjeuner)
            (14, 17): 70,   # Bon (après-midi)
            (17, 18): 40,   # Moyen (fin après-midi)
            (18, 20): 10,   # Très mauvais (soir)
        }
    }

    # Récupérer les scores pour le type de session
    session_scores = scores.get(session_type, {})

    # Trouver le score correspondant à l'heure
    for (start, end), score in session_scores.items():
        if start <= hour < end:
            return score

    # Score par défaut si hors plages définies
    return 50


def get_optimal_day_priority(session_type):
    """
    Retourner la priorité des jours de la semaine selon le type de cours.

    Basé sur:
    - Lundi matin: meilleur pour CM importants (concentration après week-end)
    - Vendredi après-midi: éviter CM, privilégier TD/TP/TPE
    - Mardi-Jeudi: plage optimale pour tous types

    Args:
        session_type (str): Type de session

    Returns:
        dict: {jour: score_priorité}
    """
    priorities = {
        'CM': {
            'monday': 100,      # Excellent (concentration après repos)
            'tuesday': 90,      # Très bon
            'wednesday': 85,    # Bon
            'thursday': 80,     # Bon
            'friday': 40,       # Éviter (fatigue semaine)
        },
        'TD': {
            'monday': 70,       # Moyen (laisser place aux CM)
            'tuesday': 100,     # Excellent
            'wednesday': 95,    # Très bon
            'thursday': 90,     # Très bon
            'friday': 85,       # Bon (acceptable pour TD)
        },
        'TP': {
            'monday': 60,       # Moyen (équipements peut-être pas prêts)
            'tuesday': 100,     # Excellent
            'wednesday': 95,    # Très bon
            'thursday': 95,     # Très bon
            'friday': 90,       # Bon (fin de semaine acceptable pour pratique)
        },
        'TPE': {
            'monday': 50,       # Faible (début semaine, focus sur cours)
            'tuesday': 70,      # Moyen
            'wednesday': 100,   # Excellent (milieu de semaine)
            'thursday': 95,     # Très bon
            'friday': 90,       # Bon (fin de semaine idéale pour projets)
        },
        'EXAM': {
            'monday': 80,       # Bon
            'tuesday': 100,     # Excellent
            'wednesday': 95,    # Très bon
            'thursday': 90,     # Bon
            'friday': 30,       # Éviter (fatigue)
        }
    }

    return priorities.get(session_type, {
        'monday': 70,
        'tuesday': 80,
        'wednesday': 80,
        'thursday': 80,
        'friday': 70
    })


def get_room_requirements_by_type(session_type, student_count):
    """
    Déterminer les exigences de salle selon le type de cours.

    Args:
        session_type (str): Type de session
        student_count (int): Nombre d'étudiants dans la classe

    Returns:
        dict: Exigences de salle
    """
    requirements = {
        'CM': {
            'room_type': 'amphitheater',
            'min_capacity': student_count,  # Tous les étudiants
            'preferred_equipment': ['projector', 'sound_system', 'microphone'],
            'required_equipment': ['projector'],
            'group_division': 1,  # Pas de division
        },
        'TD': {
            'room_type': 'classroom',
            'min_capacity': student_count // 2,  # Demi-groupes (20-40 étudiants)
            'preferred_equipment': ['projector', 'board', 'tables'],
            'required_equipment': ['board'],
            'group_division': 2,  # Division en 2 groupes
        },
        'TP': {
            'room_type': 'laboratory',
            'min_capacity': student_count // 3,  # Petits groupes (10-20 étudiants)
            'preferred_equipment': ['computers', 'laboratory_equipment', 'safety_gear'],
            'required_equipment': ['laboratory_equipment'],
            'group_division': 3,  # Division en 3-4 groupes
        },
        'TPE': {
            'room_type': 'flexible_space',
            'min_capacity': 6,  # Très petits groupes (3-6 étudiants)
            'preferred_equipment': ['tables', 'wifi', 'power_outlets'],
            'required_equipment': ['tables'],
            'group_division': 6,  # Très petits groupes
        },
        'EXAM': {
            'room_type': 'exam_room',
            'min_capacity': student_count,  # Tous les étudiants
            'preferred_equipment': ['individual_desks', 'clock', 'silence'],
            'required_equipment': ['individual_desks'],
            'group_division': 1,  # Pas de division
        }
    }

    return requirements.get(session_type, {
        'room_type': 'classroom',
        'min_capacity': student_count,
        'preferred_equipment': [],
        'required_equipment': [],
        'group_division': 1
    })


def calculate_pedagogical_sequence_delay(from_type, to_type):
    """
    Calculer le délai minimum en jours entre deux types de cours.

    Séquence pédagogique optimale:
    CM (semaine N) → TD (semaine N+1) → TP (semaine N+1 ou N+2)

    Permet consolidation et assimilation entre théorie et pratique.

    Args:
        from_type (str): Type de cours source
        to_type (str): Type de cours cible

    Returns:
        int: Délai minimum en jours
    """
    # Matrice de délais pédagogiques (en jours)
    delays = {
        ('CM', 'TD'): 7,    # 1 semaine entre CM et TD (consolidation)
        ('CM', 'TP'): 7,    # 1 semaine entre CM et TP (minimum)
        ('TD', 'TP'): 0,    # TD et TP peuvent être la même semaine
        ('CM', 'TPE'): 14,  # 2 semaines entre CM et TPE (autonomie)
        ('TD', 'TPE'): 7,   # 1 semaine entre TD et TPE
        ('TP', 'TPE'): 0,   # TP et TPE peuvent être la même semaine
    }

    return delays.get((from_type, to_type), 0)


def should_schedule_before(session_type_a, session_type_b):
    """
    Déterminer si le type A doit être planifié avant le type B.

    Ordre pédagogique: CM → TD → TP → TPE

    Args:
        session_type_a (str): Premier type
        session_type_b (str): Second type

    Returns:
        bool: True si A doit être avant B
    """
    # Ordre pédagogique croissant
    pedagogical_order = {
        'CM': 1,    # Théorie en premier
        'TD': 2,    # Approfondissement
        'TP': 3,    # Pratique
        'TPE': 4,   # Autonomie
        'EXAM': 5   # Évaluation en dernier
    }

    order_a = pedagogical_order.get(session_type_a, 99)
    order_b = pedagogical_order.get(session_type_b, 99)

    return order_a < order_b


def get_max_duration_hours(session_type):
    """
    Obtenir la durée maximale recommandée selon le type de cours.

    Basé sur:
    - Attention soutenue: 10-18 minutes
    - Recommandation: varier activités toutes les 20-25 minutes
    - CM: max 2h (concentration limitée)
    - TP: peuvent être plus longs (activités variées)

    Args:
        session_type (str): Type de session

    Returns:
        float: Durée maximale en heures
    """
    max_durations = {
        'CM': 2.0,   # Max 2h pour maintenir concentration
        'TD': 2.0,   # Max 2h pour sessions interactives
        'TP': 3.0,   # Max 3h (activités pratiques variées)
        'TPE': 2.0,  # Max 2h pour encadrement autonomie
        'EXAM': 4.0  # Max 4h pour examens longs
    }

    return max_durations.get(session_type, 2.0)


def optimize_course_distribution(courses):
    """
    Optimiser la distribution des cours selon les bonnes pratiques.

    Trier les cours par:
    1. Type pédagogique (CM d'abord)
    2. Importance/difficulté (cours complexes le matin)
    3. Heures totales (distribuer équitablement)

    Args:
        courses (list): Liste de cours

    Returns:
        dict: Cours triés par priorité
    """
    cm_courses = []
    td_courses = []
    tp_courses = []
    tpe_courses = []
    exam_courses = []

    for course in courses:
        session_type = getattr(course, 'default_session_type', 'CM')

        if session_type == 'CM':
            cm_courses.append(course)
        elif session_type == 'TD':
            td_courses.append(course)
        elif session_type == 'TP':
            tp_courses.append(course)
        elif session_type == 'TPE':
            tpe_courses.append(course)
        elif session_type == 'EXAM':
            exam_courses.append(course)
        else:
            cm_courses.append(course)  # Par défaut: CM

    # Trier chaque catégorie par total_hours (décroissant)
    # Cours avec plus d'heures en premier pour meilleure distribution
    cm_courses.sort(key=lambda c: getattr(c, 'total_hours', 0), reverse=True)
    td_courses.sort(key=lambda c: getattr(c, 'total_hours', 0), reverse=True)
    tp_courses.sort(key=lambda c: getattr(c, 'total_hours', 0), reverse=True)
    tpe_courses.sort(key=lambda c: getattr(c, 'total_hours', 0), reverse=True)

    return {
        'morning_priority': cm_courses + exam_courses,  # 8h-12h
        'afternoon_priority': td_courses + tp_courses,  # 14h-17h
        'evening_priority': tpe_courses  # 16h-18h
    }


def get_pedagogical_insights(session_type):
    """
    Obtenir des informations pédagogiques sur un type de cours.

    Returns:
        dict: Informations et recommandations
    """
    insights = {
        'CM': {
            'name': 'Cours Magistral',
            'description': 'Enseignement théorique en grand groupe',
            'best_time': 'Matin (8h-12h)',
            'max_students': 300,
            'typical_duration': '1h30-2h',
            'attention_strategy': 'Varier toutes les 20min, utiliser supports visuels',
            'room_type': 'Amphithéâtre'
        },
        'TD': {
            'name': 'Travaux Dirigés',
            'description': 'Approfondissement en groupes moyens',
            'best_time': 'Après-midi (14h-17h)',
            'max_students': 40,
            'typical_duration': '1h30-2h',
            'attention_strategy': 'Exercices interactifs, discussions',
            'room_type': 'Salle de classe',
            'prerequisite': 'CM donné 1 semaine avant'
        },
        'TP': {
            'name': 'Travaux Pratiques',
            'description': 'Mise en pratique en petits groupes',
            'best_time': 'Après-midi (14h-18h)',
            'max_students': 20,
            'typical_duration': '2h-3h',
            'attention_strategy': 'Manipulation, expérimentation active',
            'room_type': 'Laboratoire',
            'prerequisite': 'CM donné 1 semaine avant'
        },
        'TPE': {
            'name': 'Travaux Personnels Encadrés',
            'description': 'Travail autonome en très petits groupes',
            'best_time': 'Fin après-midi (16h-18h)',
            'max_students': 6,
            'typical_duration': '2h',
            'attention_strategy': 'Encadrement léger, autonomie',
            'room_type': 'Espace flexible'
        }
    }

    return insights.get(session_type, {
        'name': 'Cours',
        'description': 'Type de cours non spécifié',
        'best_time': 'Variable',
        'max_students': 30,
        'typical_duration': '2h',
        'attention_strategy': 'Standard',
        'room_type': 'Salle de classe'
    })
