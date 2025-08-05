# schedules/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
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
    SCHEDULE_STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('review', 'En révision'),
        ('approved', 'Approuvé'),
        ('published', 'Publié'),
        ('archived', 'Archivé'),
    ]
    
    SCHEDULE_TYPE_CHOICES = [
        ('curriculum', 'Par cursus'),
        ('teacher', 'Par enseignant'),
        ('room', 'Par salle'),
        ('global', 'Global'),
    ]
    
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
    schedule_type = models.CharField(max_length=15, choices=SCHEDULE_TYPE_CHOICES, default='curriculum')
    status = models.CharField(max_length=15, choices=SCHEDULE_STATUS_CHOICES, default='draft')
    description = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(blank=True, null=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_schedules')
    approved_at = models.DateTimeField(blank=True, null=True)
    version = models.IntegerField(default=1)
    total_hours = models.IntegerField(default=0)
    utilization_rate = models.FloatField(default=0.0)
    conflict_score = models.FloatField(default=0.0)
    quality_score = models.FloatField(default=0.0)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.academic_period}"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['academic_period', 'status']),
            models.Index(fields=['curriculum', 'level']),
            models.Index(fields=['schedule_type', 'is_published']),
        ]
    
    def calculate_metrics(self):
        """Calcule les métriques de l'emploi du temps"""
        sessions = self.sessions.all()
        total_sessions = sessions.count()
        
        if total_sessions == 0:
            return
            
        # Heures totales
        self.total_hours = sum(session.get_duration_hours() for session in sessions)
        
        # Taux d'utilisation des salles
        unique_rooms = sessions.values_list('room', flat=True).distinct().count()
        if unique_rooms > 0:
            self.utilization_rate = total_sessions / (unique_rooms * 30)  # 30 créneaux par semaine
        
        # Score de conflit
        conflicts = Conflict.objects.filter(schedule_session__schedule=self, is_resolved=False)
        self.conflict_score = min(conflicts.count() / max(total_sessions, 1), 1.0)
        
        # Score de qualité global
        self.quality_score = max(0, 1.0 - self.conflict_score + (self.utilization_rate * 0.3))
        
        self.save(update_fields=['total_hours', 'utilization_rate', 'conflict_score', 'quality_score'])
    
    def publish(self, approved_by=None):
        """Publie l'emploi du temps"""
        self.status = 'published'
        self.is_published = True
        self.published_at = timezone.now()
        if approved_by:
            self.approved_by = approved_by
            self.approved_at = timezone.now()
        self.save()
    
    def archive(self):
        """Archive l'emploi du temps"""
        self.status = 'archived'
        self.is_published = False
        self.save()


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
        indexes = [
            models.Index(fields=['schedule', 'time_slot']),
            models.Index(fields=['teacher', 'time_slot']),
            models.Index(fields=['room', 'time_slot']),
            models.Index(fields=['course', 'session_type']),
        ]
    
    def get_duration_hours(self):
        """Retourne la durée en heures de la session"""
        if self.specific_start_time and self.specific_end_time:
            start = self.specific_start_time
            end = self.specific_end_time
        else:
            start = self.time_slot.start_time
            end = self.time_slot.end_time
        
        duration = timezone.datetime.combine(timezone.datetime.today(), end) - \
                  timezone.datetime.combine(timezone.datetime.today(), start)
        return duration.total_seconds() / 3600
    
    def get_conflicts(self):
        """Retourne les conflits liés à cette session"""
        return Conflict.objects.filter(
            models.Q(schedule_session=self) | 
            models.Q(conflicting_session=self)
        ).filter(is_resolved=False)
    
    def has_conflicts(self):
        """Vérifie si la session a des conflits non résolus"""
        return self.get_conflicts().exists()
    
    def get_full_schedule_info(self):
        """Retourne les informations complètes de planification"""
        return {
            'course': {
                'code': self.course.code,
                'name': self.course.name,
                'type': self.session_type,
                'level': self.course.level,
            },
            'teacher': {
                'name': self.teacher.user.get_full_name(),
                'id': self.teacher.employee_id,
            },
            'room': {
                'code': self.room.code,
                'name': self.room.name,
                'capacity': self.room.capacity,
                'building': self.room.building.name,
            },
            'time': {
                'day': self.time_slot.get_day_of_week_display(),
                'start': self.time_slot.start_time.strftime('%H:%M'),
                'end': self.time_slot.end_time.strftime('%H:%M'),
                'duration_hours': self.get_duration_hours(),
            },
            'students': self.expected_students,
            'conflicts': self.has_conflicts(),
        }


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
