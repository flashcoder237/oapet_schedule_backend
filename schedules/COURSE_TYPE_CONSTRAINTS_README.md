# Système de Contraintes par Type de Cours

## Vue d'ensemble

Le système de génération d'emploi du temps intègre maintenant des contraintes pédagogiques spécifiques à chaque type de cours (CM, TD, TP, TPE, CONF, EXAM). Ces contraintes assurent que les cours sont programmés selon les meilleures pratiques pédagogiques.

## Règles Pédagogiques

### CM (Cours Magistral)
- **Horaires préférés**: Matin (8h-12h)
- **Jours préférés**: Lundi, Mardi, Mercredi
- **Durée**: 1.5h - 3h
- **Maximum par jour**: 2
- **Prérequis**: Aucun
- **Poids de pénalité**: 0.5 (modéré)

### TD (Travaux Dirigés)
- **Horaires préférés**: Après-midi (13h-18h)
- **Jours préférés**: Tous
- **Durée**: 1.5h - 2h
- **Maximum par jour**: 3
- **Prérequis**: **DOIT suivre le CM correspondant**
- **Poids de pénalité**: 0.8 (élevé)

### TP (Travaux Pratiques)
- **Horaires préférés**: Après-midi (13h-17h)
- **Horaires interdits**: Fin de journée (17h-19h)
- **Jours préférés**: Mardi à Vendredi
- **Durée**: 2h - 4h
- **Maximum par jour**: 1 (sessions fatigantes)
- **Prérequis**: **DOIT suivre le TD correspondant**
- **Poids de pénalité**: 1.0 (très important)

### TPE (Travail Personnel Encadré)
- **Horaires préférés**: Après-midi (14h-18h)
- **Jours préférés**: Jeudi, Vendredi
- **Durée**: 1h - 2h
- **Maximum par jour**: 2
- **Prérequis**: Aucun
- **Poids de pénalité**: 0.3 (faible)

### CONF (Conférence)
- **Horaires préférés**: Mi-journée (10h-12h, 14h-16h)
- **Durée**: 1h - 2h
- **Maximum par jour**: 1
- **Prérequis**: Aucun
- **Poids de pénalité**: 0.4 (modéré-faible)

### EXAM (Examen)
- **Horaires préférés**: Matin (8h-12h)
- **Horaires interdits**: Fin de journée (17h-19h)
- **Jours interdits**: Lundi
- **Durée**: 1h - 4h
- **Maximum par jour**: 1
- **Prérequis**: Aucun
- **Poids de pénalité**: 0.9 (très élevé)

## Architecture du Système

### Fichiers Principaux

1. **`course_type_constraints.py`**
   - Définit les règles pour chaque type de cours
   - Classe `CourseTypeRule`: dataclass pour les règles
   - Classe `CourseTypeConstraintChecker`: vérification des contraintes

2. **`generation_service.py`**
   - Intègre les contraintes dans le processus de génération
   - Vérifie chaque occurrence avant création
   - Collecte les violations et warnings

### Flux de Vérification

Pour chaque occurrence à générer:

1. **Vérification horaire** (`check_time_preference`)
   - Vérifie si l'heure est dans les plages interdites → REJET
   - Vérifie si l'heure est dans les plages préférées → OK
   - Sinon → Pénalité partielle (50% du poids)

2. **Vérification jour** (`check_day_preference`)
   - Vérifie si le jour est interdit → REJET
   - Vérifie si le jour est préféré → OK
   - Sinon → Pénalité partielle (30% du poids)

3. **Vérification prérequis** (`check_prerequisite`)
   - Pour TD: vérifie que CM-XXX a au moins une session programmée
   - Pour TP: vérifie que TD-XXX a au moins une session programmée
   - Si manquant → REJET avec pénalité maximale

4. **Vérification max par jour** (`check_max_per_day`)
   - Compte les sessions du même cours le même jour
   - Si >= max_per_day → REJET avec pénalité

### Types de Violations

#### Violations Critiques (severity: 'high')
- Prérequis manquant (TD sans CM, TP sans TD)
- Génération **bloquée** si `allow_conflicts=False`

#### Violations Moyennes (severity: 'medium')
- Jour interdit
- Horaire interdit
- Dépassement max par jour
- Génération **bloquée** si `allow_conflicts=False`

#### Warnings (severity: 'low')
- Créneau hors plage préférée mais pas interdite
- Jour non optimal mais pas interdit
- Génération **autorisée** même si `allow_conflicts=False`

## Utilisation

### Dans le Code de Génération

```python
# Initialisation automatique dans ScheduleGenerationService.__init__()
self.constraint_checker = CourseTypeConstraintChecker()
self.scheduled_sessions = {}  # Track pour prérequis

# Vérification automatique dans _generate_session_occurrences()
course_type = session_template.course.course_type
course_code = session_template.course.code

# Vérifie toutes les contraintes
is_valid_time, time_penalty = self.constraint_checker.check_time_preference(
    course_type, session_start
)
is_valid_day, day_penalty = self.constraint_checker.check_day_preference(
    course_type, current_date.weekday()
)
is_valid_prereq, prereq_penalty = self.constraint_checker.check_prerequisite(
    course_type, course_code, self.scheduled_sessions
)
is_valid_max, max_penalty = self.constraint_checker.check_max_per_day(
    course_type, current_date.date(), course_code, self.scheduled_sessions
)

# Décision basée sur les violations
if not is_valid_prereq and not self.config.allow_conflicts:
    # Skip cette occurrence
    continue
```

### Obtenir les Recommandations

```python
checker = CourseTypeConstraintChecker()
recommendations = checker.get_recommendations('TP')

# Retourne:
{
    'preferred_times': [(time(13, 0), time(17, 0))],
    'forbidden_times': [(time(17, 0), time(19, 0))],
    'preferred_days': [1, 2, 3, 4],  # Mardi-Vendredi
    'forbidden_days': [],
    'duration_range': (2.0, 4.0),
    'requires_predecessor': True,
    'predecessor_type': 'TD',
    'max_per_day': 1
}
```

## Résultats de Génération

Le dictionnaire retourné par `generate_occurrences()` inclut maintenant:

```python
{
    'success': True,
    'occurrences_created': 150,
    'conflicts_detected': 5,
    'course_type_violations': 3,  # Nouveau
    'conflicts': [
        {
            'type': 'course_type_constraint_violation',
            'severity': 'high',
            'course': 'MATH101-TP',
            'course_type': 'TP',
            'date': '2025-01-15',
            'time': '08:00 - 10:00',
            'penalty': 1.0,
            'violations': [
                'Prérequis manquant: TD doit être programmé avant'
            ],
            'message': 'Prérequis manquant: TD doit être programmé avant'
        },
        {
            'type': 'course_type_preference_warning',
            'severity': 'low',
            'course': 'PHYS101-CM',
            'course_type': 'CM',
            'date': '2025-01-15',
            'time': '14:00 - 16:00',
            'penalty': 0.25,
            'message': 'Créneau sous-optimal pour ce type de cours'
        }
    ],
    'generation_time': 2.5
}
```

## Nomenclature des Cours

Le système suppose que les cours suivent cette nomenclature:
- Cours de base: `CODE` (ex: `MATH101`)
- CM: `CODE-CM` (ex: `MATH101-CM`)
- TD: `CODE-TD` (ex: `MATH101-TD`)
- TP: `CODE-TP` (ex: `MATH101-TP`)
- TPE: `CODE-TPE` (ex: `MATH101-TPE`)

Les prérequis sont vérifiés en extrayant le code de base et en cherchant le type prérequis.

## Configuration

Pour modifier les règles, éditez `course_type_constraints.py` et ajustez les paramètres de `CourseTypeRule` dans `_initialize_rules()`.

## Limitations Actuelles

1. **ML Optimization**: Les contraintes de type de cours ne sont pas encore intégrées dans `ml_optimization_service.py`
2. **Prérequis temporels**: Le système vérifie seulement que le prérequis existe, pas qu'il est programmé AVANT dans le temps
3. **Types personnalisés**: Seuls les types prédéfinis sont supportés (ajout nécessaire dans les deux fichiers)

## Prochaines Améliorations

1. Intégrer les contraintes dans le ML optimizer
2. Ajouter vérification temporelle stricte des prérequis (TD après CM dans la même semaine)
3. Permettre configuration des règles via l'interface admin
4. Ajouter score de qualité globale de l'emploi du temps basé sur les pénalités
5. Interface de visualisation des violations dans le frontend
