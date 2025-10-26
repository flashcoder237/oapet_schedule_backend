# courses/models.py
from django.db import models
from django.contrib.auth.models import User

# Import des modèles de classes
from .models_class import StudentClass, ClassCourse


class Department(models.Model):
    """Modèle pour les départements"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)
    head_of_department = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='headed_departments'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

    class Meta:
        ordering = ['code']


class Teacher(models.Model):
    """Modèle pour les enseignants"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='teachers')
    phone = models.CharField(max_length=20, blank=True)
    office = models.CharField(max_length=50, blank=True)
    specializations = models.JSONField(default=list)  # Liste des spécialisations
    availability = models.JSONField(default=dict)  # Disponibilités par jour/période
    max_hours_per_week = models.IntegerField(default=20)
    preferred_days = models.JSONField(default=list)  # Jours préférés
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.employee_id})"

    class Meta:
        ordering = ['user__last_name', 'user__first_name']


class Course(models.Model):
    """Modèle pour les cours"""
    LEVEL_CHOICES = [
        ('L1', 'Licence 1'),
        ('L2', 'Licence 2'),
        ('L3', 'Licence 3'),
        ('M1', 'Master 1'),
        ('M2', 'Master 2'),
         ('D1', 'Doctorat 1'),
        ('D2', 'Doctorat 2'),
        ('D3', 'Doctorat 3'),
    ]
    
    COURSE_TYPE_CHOICES = [
        ('CM', 'Cours Magistral'),
        ('TD', 'Travaux Dirigés'),
        ('TP', 'Travaux Pratiques'),
        ('TPE', 'Travail Personnel Encadré'),
        ('CONF', 'Conférence'),
        ('EXAM', 'Examen'),
    ]

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='courses')
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='courses')
    course_type = models.CharField(max_length=10, choices=COURSE_TYPE_CHOICES, default='CM')
    level = models.CharField(max_length=5, choices=LEVEL_CHOICES)
    credits = models.IntegerField(default=3)
    hours_per_week = models.IntegerField(default=3)
    total_hours = models.IntegerField(default=30)
    max_students = models.IntegerField(default=50)
    min_room_capacity = models.IntegerField(default=30)
    requires_computer = models.BooleanField(default=False)
    requires_projector = models.BooleanField(default=True)
    requires_laboratory = models.BooleanField(default=False)

    # Préférences de salles
    preferred_rooms = models.JSONField(default=list, help_text="IDs des salles préférées")
    excluded_rooms = models.JSONField(default=list, help_text="IDs des salles à éviter")
    requires_specific_room_type = models.CharField(max_length=50, blank=True, help_text="Type de salle requis (amphithéâtre, laboratoire, etc.)")

    semester = models.CharField(max_length=10, default='S1')  # S1, S2
    academic_year = models.CharField(max_length=10, default='2025-2026')
    min_sessions_per_week = models.IntegerField(default=1)
    max_sessions_per_week = models.IntegerField(default=3)
    preferred_times = models.JSONField(default=list)  # Créneaux préférés
    unavailable_times = models.JSONField(default=list)  # Créneaux indisponibles
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    # ============= CHAMPS ML PRÉDICTIFS =============
    ml_difficulty_score = models.FloatField(
        null=True, blank=True,
        help_text="Score de difficulté de planification ML (0-1)"
    )
    ml_complexity_level = models.CharField(
        max_length=20, blank=True,
        choices=[
            ('Facile', 'Facile'),
            ('Moyenne', 'Moyenne'),
            ('Difficile', 'Difficile')
        ],
        help_text="Niveau de complexité prédit par ML"
    )
    ml_scheduling_priority = models.IntegerField(
        default=2,
        help_text="Priorité de planification ML: 1=haute, 2=moyenne, 3=basse"
    )
    ml_last_updated = models.DateTimeField(
        null=True, blank=True,
        help_text="Dernière mise à jour des prédictions ML"
    )
    ml_prediction_metadata = models.JSONField(
        default=dict, blank=True,
        help_text="Métadonnées supplémentaires des prédictions ML"
    )

    # ============= PRIORITÉ MANUELLE =============
    manual_scheduling_priority = models.IntegerField(
        default=3,
        choices=[
            (1, 'Très Haute (à planifier en premier)'),
            (2, 'Haute'),
            (3, 'Moyenne'),
            (4, 'Basse'),
            (5, 'Très Basse (flexible)')
        ],
        help_text="Priorité de planification définie manuellement par l'admin"
    )
    use_manual_priority = models.BooleanField(
        default=False,
        help_text="Si True, utilise manual_scheduling_priority au lieu de ml_scheduling_priority"
    )

    def __str__(self):
        return f"{self.code} - {self.name}"

    class Meta:
        ordering = ['code']

    @property
    def effective_priority(self):
        """Retourne la priorité effective (manuelle si activée, sinon ML)"""
        if self.use_manual_priority:
            return self.manual_scheduling_priority
        return self.ml_scheduling_priority

    def update_ml_predictions(self, force=False):
        """
        Met à jour les prédictions ML du cours

        Args:
            force (bool): Force la mise à jour même si le cache est valide

        Returns:
            dict: Les prédictions ML mises à jour
        """
        from datetime import timedelta
        from django.utils import timezone
        import logging

        logger = logging.getLogger(__name__)

        # Éviter les recalculs fréquents (cache 24h)
        if not force and self.ml_last_updated:
            age = timezone.now() - self.ml_last_updated
            if age < timedelta(hours=24):
                logger.info(f"ML cache still valid for course {self.code}")
                return {
                    'difficulty_score': self.ml_difficulty_score,
                    'complexity_level': self.ml_complexity_level,
                    'priority': self.ml_scheduling_priority,
                    'cached': True
                }

        try:
            from ml_engine.simple_ml_service import ml_service

            logger.info(f"Updating ML predictions for course {self.code}")
            prediction = ml_service.predict_schedule_difficulty(self)

            # Mise à jour des champs
            self.ml_difficulty_score = prediction['difficulty_score']
            self.ml_complexity_level = prediction['complexity_level']
            self.ml_scheduling_priority = prediction['priority']
            self.ml_last_updated = timezone.now()

            # Stocker les métadonnées additionnelles
            self.ml_prediction_metadata = {
                'factors': prediction.get('factors', []),
                'confidence': prediction.get('confidence', 0),
                'model_used': prediction.get('model_used', 'unknown'),
                'suitable_rooms_count': prediction.get('suitable_rooms_count', 0),
                'student_count': prediction.get('student_count', 0)
            }

            self.save(update_fields=[
                'ml_difficulty_score',
                'ml_complexity_level',
                'ml_scheduling_priority',
                'ml_last_updated',
                'ml_prediction_metadata'
            ])

            logger.info(f"ML predictions updated for {self.code}: {self.ml_complexity_level}")
            return prediction

        except Exception as e:
            logger.error(f"Failed to update ML predictions for course {self.code}: {e}")
            return None

    @property
    def ml_difficulty_badge(self):
        """Retourne un badge visuel pour l'interface"""
        badges = {
            'Facile': {'color': 'green', 'icon': '✓'},
            'Moyenne': {'color': 'orange', 'icon': '○'},
            'Difficile': {'color': 'red', 'icon': '!'}
        }
        return badges.get(self.ml_complexity_level, {'color': 'gray', 'icon': '?'})


class Curriculum(models.Model):
    """Modèle pour les cursus/programmes"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='curricula')
    level = models.CharField(max_length=5, choices=Course.LEVEL_CHOICES)
    courses = models.ManyToManyField(Course, through='CurriculumCourse')
    total_credits = models.IntegerField(default=60)
    description = models.TextField(blank=True)
    academic_year = models.CharField(max_length=10, default='2025-2026')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

    class Meta:
        ordering = ['code']


class CurriculumCourse(models.Model):
    """Modèle de liaison entre curriculum et cours"""
    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    is_mandatory = models.BooleanField(default=True)
    semester = models.CharField(max_length=10, default='S1')
    order = models.IntegerField(default=0)  # Ordre dans le semestre

    class Meta:
        unique_together = ['curriculum', 'course']
        ordering = ['semester', 'order']


class Student(models.Model):
    """Modèle pour les étudiants"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    student_id = models.CharField(max_length=20, unique=True)
    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE, related_name='students')
    current_level = models.CharField(max_length=5, choices=Course.LEVEL_CHOICES)
    entry_year = models.IntegerField()
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    emergency_contact = models.CharField(max_length=100, blank=True)
    emergency_phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.student_id})"

    class Meta:
        ordering = ['user__last_name', 'user__first_name']


class CourseEnrollment(models.Model):
    """Modèle pour les inscriptions aux cours"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    academic_year = models.CharField(max_length=10, default='2025-2026')
    semester = models.CharField(max_length=10, default='S1')
    enrollment_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.student} - {self.course}"

    class Meta:
        unique_together = ['student', 'course', 'academic_year']
        ordering = ['-enrollment_date']


class CoursePrerequisite(models.Model):
    """Modèle pour les prérequis de cours"""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='prerequisites')
    prerequisite_course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='prerequisite_for')
    is_mandatory = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.course} nécessite {self.prerequisite_course}"

    class Meta:
        unique_together = ['course', 'prerequisite_course']


class TeacherPreference(models.Model):
    """Modèle pour les préférences et désirs des enseignants"""
    PREFERENCE_TYPE_CHOICES = [
        ('time_slot', 'Créneau horaire préféré'),
        ('day', 'Jour préféré'),
        ('max_hours_per_day', 'Heures maximales par jour'),
        ('consecutive_days', 'Jours consécutifs'),
        ('break_time', 'Temps de pause'),
        ('room', 'Salle préférée'),
        ('avoid_time', 'Créneaux à éviter'),
        ('teaching_load', 'Charge d\'enseignement'),
    ]

    PRIORITY_CHOICES = [
        ('required', 'Obligatoire'),
        ('high', 'Élevée'),
        ('medium', 'Moyenne'),
        ('low', 'Faible'),
    ]

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='preferences')
    preference_type = models.CharField(max_length=20, choices=PREFERENCE_TYPE_CHOICES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    preference_data = models.JSONField(default=dict, help_text="Données de préférence en format JSON")

    # Métadonnées
    is_active = models.BooleanField(default=True)
    reason = models.TextField(blank=True, help_text="Raison de la préférence")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['teacher', 'priority', 'preference_type']
        indexes = [
            models.Index(fields=['teacher', 'preference_type']),
            models.Index(fields=['priority', 'is_active']),
        ]

    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.get_preference_type_display()} ({self.priority})"


class TeacherUnavailability(models.Model):
    """Modèle pour les indisponibilités des enseignants"""
    UNAVAILABILITY_TYPE_CHOICES = [
        ('permanent', 'Permanente'),
        ('temporary', 'Temporaire'),
        ('recurring', 'Récurrente'),
    ]

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='unavailabilities')
    unavailability_type = models.CharField(max_length=15, choices=UNAVAILABILITY_TYPE_CHOICES)

    # Pour les indisponibilités temporaires
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    # Pour les indisponibilités récurrentes (ex: chaque lundi matin)
    day_of_week = models.CharField(max_length=10, blank=True, help_text="Jour de la semaine")
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    reason = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_unavailabilities'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Teacher unavailabilities'

    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.get_unavailability_type_display()}"


class TeacherScheduleRequest(models.Model):
    """Modèle pour les demandes de modification d'emploi du temps par les enseignants"""
    REQUEST_TYPE_CHOICES = [
        ('schedule_change', 'Changement de créneau'),
        ('room_change', 'Changement de salle'),
        ('session_cancellation', 'Annulation de session'),
        ('additional_session', 'Session supplémentaire'),
        ('time_swap', 'Échange de créneaux'),
        ('other', 'Autre'),
    ]

    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('under_review', 'En cours d\'examen'),
        ('approved', 'Approuvée'),
        ('rejected', 'Rejetée'),
        ('completed', 'Complétée'),
    ]

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='schedule_requests')
    request_type = models.CharField(max_length=25, choices=REQUEST_TYPE_CHOICES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')

    # Informations sur la session concernée
    session = models.ForeignKey(
        'schedules.ScheduleSession',
        on_delete=models.CASCADE,
        related_name='modification_requests',
        null=True,
        blank=True
    )

    # Détails de la demande
    current_situation = models.TextField(help_text="Description de la situation actuelle")
    requested_change = models.TextField(help_text="Description du changement demandé")
    reason = models.TextField(help_text="Raison de la demande")

    # Données structurées pour les changements spécifiques
    change_data = models.JSONField(
        default=dict,
        help_text="Données structurées du changement (nouveau créneau, nouvelle salle, etc.)"
    )

    # Priorité
    priority = models.CharField(max_length=10, choices=[
        ('low', 'Basse'),
        ('medium', 'Moyenne'),
        ('high', 'Haute'),
        ('urgent', 'Urgente'),
    ], default='medium')

    # Approbation
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_schedule_requests'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-priority']
        indexes = [
            models.Index(fields=['teacher', 'status']),
            models.Index(fields=['status', 'priority']),
        ]

    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.get_request_type_display()} ({self.get_status_display()})"


class SessionFeedback(models.Model):
    """Modèle pour les retours des enseignants sur leurs sessions"""
    FEEDBACK_TYPE_CHOICES = [
        ('confirmation', 'Confirmation'),
        ('issue', 'Problème'),
        ('suggestion', 'Suggestion'),
    ]

    ISSUE_TYPE_CHOICES = [
        ('room_problem', 'Problème de salle'),
        ('equipment_issue', 'Problème d\'équipement'),
        ('timing_issue', 'Problème de timing'),
        ('student_attendance', 'Problème de présence étudiants'),
        ('other', 'Autre'),
    ]

    session = models.ForeignKey(
        'schedules.ScheduleSession',
        on_delete=models.CASCADE,
        related_name='teacher_feedbacks'
    )
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='session_feedbacks')
    feedback_type = models.CharField(max_length=15, choices=FEEDBACK_TYPE_CHOICES)
    issue_type = models.CharField(max_length=20, choices=ISSUE_TYPE_CHOICES, blank=True)

    # Détails du retour
    description = models.TextField()
    severity = models.CharField(max_length=10, choices=[
        ('low', 'Faible'),
        ('medium', 'Moyenne'),
        ('high', 'Élevée'),
        ('critical', 'Critique'),
    ], default='medium', blank=True)

    # Traitement
    is_resolved = models.BooleanField(default=False)
    resolution_notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_session_feedbacks'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['teacher', 'feedback_type']),
            models.Index(fields=['session', 'is_resolved']),
        ]

    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.get_feedback_type_display()} - Session {self.session.id}"
