# schedules/models.py
from django.db import models
from django.contrib.auth.models import User
from courses.models import Course, Teacher, Student, Curriculum
from rooms.models import Room


class AcademicPeriod(models.Model):
    """Modèle pour les périodes académiques (semestres, années)"""
    name = models.CharField(max_length=50, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    academic_year = models.CharField(max_length=10)
    semester = models.CharField(max_length=5)  # S1, S2
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-start_date']


class TimeSlot(models.Model):
    """Modèle pour les créneaux horaires"""
    DAYS_OF_WEEK = [
        ('monday', 'Lundi'),
        ('tuesday', 'Mardi'),
        ('wednesday', 'Mercredi'),
        ('thursday', 'Jeudi'),
        ('friday', 'Vendredi'),
        ('saturday', 'Samedi'),
        ('sunday', 'Dimanche'),
    ]

    day_of_week = models.CharField(max_length=10, choices=DAYS_OF_WEEK)
    start_time = models.TimeField()
    end_time = models.TimeField()
    name = models.CharField(max_length=50, blank=True)  # Ex: "Créneau 1", "Matin"
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.get_day_of_week_display()} {self.start_time}-{self.end_time}"

    class Meta:
        unique_together = ['day_of_week', 'start_time', 'end_time']
        ordering = ['day_of_week', 'start_time']


class Schedule(models.Model):
    """Modèle principal pour les emplois du temps"""
    name = models.CharField(max_length=200)
    academic_period = models.ForeignKey(AcademicPeriod, on_delete=models.CASCADE)
    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE, blank=True, null=True)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, blank=True, null=True)
    level = models.CharField(max_length=5, choices=[
        ('L1', 'Licence 1'),
        ('L2', 'Licence 2'),
        ('L3', 'Licence 3'),
        ('M1', 'Master 1'),
        ('M2', 'Master 2'),
    ], blank=True)
    description = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(blank=True, null=True)
    version = models.IntegerField(default=1)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.academic_period}"

    class Meta:
        ordering = ['-created_at']


class ScheduleSession(models.Model):
    """Modèle pour les sessions individuelles d'un emploi du temps"""
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='sessions')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    
    # Dates spécifiques si différent du time_slot standard
    specific_date = models.DateField(blank=True, null=True)
    specific_start_time = models.TimeField(blank=True, null=True)
    specific_end_time = models.TimeField(blank=True, null=True)
    
    # Informations additionnelles
    session_type = models.CharField(max_length=10, choices=[
        ('CM', 'Cours Magistral'),
        ('TD', 'Travaux Dirigés'),
        ('TP', 'Travaux Pratiques'),
        ('CONF', 'Conférence'),
        ('EXAM', 'Examen'),
    ], default='CM')
    
    expected_students = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    is_cancelled = models.BooleanField(default=False)
    cancellation_reason = models.TextField(blank=True)
    
    # Métadonnées ML
    difficulty_score = models.FloatField(blank=True, null=True)
    complexity_level = models.CharField(max_length=20, blank=True)
    scheduling_priority = models.IntegerField(default=1)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.course.code} - {self.time_slot} - {self.room.code}"

    class Meta:
        unique_together = ['schedule', 'time_slot', 'room']
        ordering = ['time_slot__day_of_week', 'time_slot__start_time']


class Conflict(models.Model):
    """Modèle pour détecter et gérer les conflits d'emploi du temps"""
    CONFLICT_TYPES = [
        ('teacher_double_booking', 'Enseignant déjà occupé'),
        ('room_double_booking', 'Salle déjà occupée'),
        ('student_overlap', 'Conflit étudiant'),
        ('resource_unavailable', 'Ressource indisponible'),
        ('constraint_violation', 'Violation de contrainte'),
    ]

    schedule_session = models.ForeignKey(ScheduleSession, on_delete=models.CASCADE)
    conflict_type = models.CharField(max_length=30, choices=CONFLICT_TYPES)
    conflicting_session = models.ForeignKey(
        ScheduleSession, 
        on_delete=models.CASCADE, 
        related_name='conflicts_as_conflicting',
        blank=True, 
        null=True
    )
    description = models.TextField()
    severity = models.CharField(max_length=10, choices=[
        ('low', 'Faible'),
        ('medium', 'Moyenne'),
        ('high', 'Élevée'),
        ('critical', 'Critique'),
    ], default='medium')
    is_resolved = models.BooleanField(default=False)
    resolution_notes = models.TextField(blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Conflit {self.get_conflict_type_display()} - {self.schedule_session}"

    class Meta:
        ordering = ['-detected_at']


class ScheduleOptimization(models.Model):
    """Modèle pour stocker les résultats d'optimisation d'emploi du temps"""
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='optimizations')
    optimization_type = models.CharField(max_length=20, choices=[
        ('manual', 'Manuel'),
        ('automatic', 'Automatique'),
        ('ml_assisted', 'Assisté par ML'),
    ], default='automatic')
    
    # Paramètres d'optimisation
    optimization_parameters = models.JSONField(default=dict)
    
    # Résultats
    conflicts_before = models.IntegerField(default=0)
    conflicts_after = models.IntegerField(default=0)
    optimization_score = models.FloatField(default=0.0)
    efficiency_metrics = models.JSONField(default=dict)
    
    # Détails du processus
    algorithm_used = models.CharField(max_length=50, blank=True)
    execution_time = models.FloatField(default=0.0)  # En secondes
    iterations = models.IntegerField(default=0)
    convergence_achieved = models.BooleanField(default=False)
    
    # Métadonnées
    started_by = models.ForeignKey(User, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    logs = models.TextField(blank=True)

    def __str__(self):
        return f"Optimisation {self.schedule.name} - {self.started_at}"

    class Meta:
        ordering = ['-started_at']


class ScheduleTemplate(models.Model):
    """Modèle pour les modèles d'emploi du temps réutilisables"""
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE)
    level = models.CharField(max_length=5, choices=[
        ('L1', 'Licence 1'),
        ('L2', 'Licence 2'),
        ('L3', 'Licence 3'),
        ('M1', 'Master 1'),
        ('M2', 'Master 2'),
    ])
    
    # Configuration du template
    template_data = models.JSONField(default=dict)  # Structure du template
    default_constraints = models.JSONField(default=dict)  # Contraintes par défaut
    
    # Statistiques d'utilisation
    usage_count = models.IntegerField(default=0)
    success_rate = models.FloatField(default=0.0)  # Taux de succès des emplois du temps générés
    
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.level}"

    class Meta:
        ordering = ['name']


class ScheduleConstraint(models.Model):
    """Modèle pour les contraintes spécifiques des emplois du temps"""
    CONSTRAINT_TYPES = [
        ('teacher_availability', 'Disponibilité enseignant'),
        ('room_availability', 'Disponibilité salle'),
        ('course_timing', 'Horaires de cours'),
        ('student_workload', 'Charge de travail étudiant'),
        ('resource_requirement', 'Exigence de ressource'),
        ('curriculum_rule', 'Règle de curriculum'),
        ('custom', 'Personnalisée'),
    ]

    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='constraints')
    constraint_type = models.CharField(max_length=25, choices=CONSTRAINT_TYPES)
    name = models.CharField(max_length=200)
    description = models.TextField()
    
    # Configuration de la contrainte
    constraint_data = models.JSONField(default=dict)
    priority = models.IntegerField(default=1)  # 1=haute, 5=basse
    is_hard_constraint = models.BooleanField(default=True)  # True=dure, False=souple
    
    # Métadonnées
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.schedule.name} - {self.name}"

    class Meta:
        ordering = ['priority', 'name']


class ScheduleExport(models.Model):
    """Modèle pour l'historique des exports d'emploi du temps"""
    EXPORT_FORMATS = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('ical', 'iCalendar'),
        ('json', 'JSON'),
        ('csv', 'CSV'),
    ]

    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='exports')
    export_format = models.CharField(max_length=10, choices=EXPORT_FORMATS)
    file_path = models.FileField(upload_to='schedule_exports/')
    export_parameters = models.JSONField(default=dict)
    file_size = models.IntegerField(default=0)  # En bytes
    exported_by = models.ForeignKey(User, on_delete=models.CASCADE)
    exported_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Export {self.schedule.name} - {self.export_format}"

    class Meta:
        ordering = ['-exported_at']
