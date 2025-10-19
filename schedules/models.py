# schedules/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from courses.models import Course, Teacher, Student
from courses.models_class import StudentClass
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
        ('class', 'Par classe'),
        ('teacher', 'Par enseignant'),
        ('room', 'Par salle'),
        ('global', 'Global'),
    ]

    name = models.CharField(max_length=200)
    academic_period = models.ForeignKey(AcademicPeriod, on_delete=models.CASCADE)
    student_class = models.ForeignKey(StudentClass, on_delete=models.CASCADE, blank=True, null=True, related_name='schedules')
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, blank=True, null=True)
    level = models.CharField(max_length=5, choices=[
        ('L1', 'Licence 1'),
        ('L2', 'Licence 2'),
        ('L3', 'Licence 3'),
        ('M1', 'Master 1'),
        ('M2', 'Master 2'),
    ], blank=True)
    schedule_type = models.CharField(max_length=15, choices=SCHEDULE_TYPE_CHOICES, default='class')
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
            models.Index(fields=['student_class', 'level']),
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

    def get_course_coverage(self):
        """
        Calcule la couverture des heures de cours
        Retourne un dictionnaire avec les cours et leur couverture
        """
        from datetime import timedelta
        from django.db.models import Sum, F, ExpressionWrapper, DurationField
        from courses.models_class import ClassCourse

        coverage_report = {
            'courses': [],
            'total_courses': 0,
            'fully_covered': 0,
            'partially_covered': 0,
            'not_covered': 0,
            'summary': {}
        }

        # Récupérer tous les cours de la classe
        if self.student_class:
            class_courses = ClassCourse.objects.filter(
                student_class=self.student_class,
                is_active=True
            ).select_related('course')

            for class_course in class_courses:
                course = class_course.course

                # Calculer les heures planifiées dans l'emploi du temps
                sessions = self.sessions.filter(course=course)

                # Calculer la durée totale en minutes
                total_minutes = 0
                for session in sessions:
                    if session.specific_start_time and session.specific_end_time:
                        start = timedelta(
                            hours=session.specific_start_time.hour,
                            minutes=session.specific_start_time.minute
                        )
                        end = timedelta(
                            hours=session.specific_end_time.hour,
                            minutes=session.specific_end_time.minute
                        )
                        duration = end - start
                        total_minutes += duration.total_seconds() / 60

                # Convertir en heures
                scheduled_hours = total_minutes / 60

                # Heures requises (total_hours du cours)
                required_hours = course.total_hours if course.total_hours else 0

                # Calculer le pourcentage de couverture
                coverage_percentage = (scheduled_hours / required_hours * 100) if required_hours > 0 else 0

                # Déterminer le statut
                if coverage_percentage >= 100:
                    status = 'fully_covered'
                    coverage_report['fully_covered'] += 1
                elif coverage_percentage > 0:
                    status = 'partially_covered'
                    coverage_report['partially_covered'] += 1
                else:
                    status = 'not_covered'
                    coverage_report['not_covered'] += 1

                coverage_report['courses'].append({
                    'course_code': course.code,
                    'course_name': course.name,
                    'required_hours': required_hours,
                    'scheduled_hours': round(scheduled_hours, 2),
                    'coverage_percentage': round(coverage_percentage, 2),
                    'status': status,
                    'missing_hours': max(0, required_hours - scheduled_hours),
                    'sessions_count': sessions.count()
                })

            coverage_report['total_courses'] = class_courses.count()

            # Résumé global
            coverage_report['summary'] = {
                'total_required_hours': sum(c['required_hours'] for c in coverage_report['courses']),
                'total_scheduled_hours': sum(c['scheduled_hours'] for c in coverage_report['courses']),
                'overall_coverage': round(
                    (sum(c['scheduled_hours'] for c in coverage_report['courses']) /
                     sum(c['required_hours'] for c in coverage_report['courses']) * 100)
                    if sum(c['required_hours'] for c in coverage_report['courses']) > 0 else 0,
                    2
                )
            }

        return coverage_report


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
        # Pas de unique_together car specific_date=NULL pose problème
        # La validation des doublons se fait au niveau du service de génération
        ordering = ['time_slot__day_of_week', 'time_slot__start_time']
        indexes = [
            models.Index(fields=['schedule', 'time_slot']),
            models.Index(fields=['teacher', 'time_slot']),
            models.Index(fields=['room', 'time_slot']),
            models.Index(fields=['course', 'session_type']),
            models.Index(fields=['specific_date']),
            models.Index(fields=['schedule', 'time_slot', 'room']),
        ]
        constraints = [
            # Contrainte pour éviter les doublons quand specific_date est défini
            models.UniqueConstraint(
                fields=['schedule', 'time_slot', 'room', 'specific_date'],
                name='unique_schedule_session_with_date',
                condition=models.Q(specific_date__isnull=False)
            ),
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
    student_class = models.ForeignKey(StudentClass, on_delete=models.CASCADE, related_name='templates', null=True, blank=True)
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
        ('class_rule', 'Règle de classe'),
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


class ScheduleGenerationConfig(models.Model):
    """Configuration pour la génération dynamique d'emploi du temps"""
    RECURRENCE_TYPES = [
        ('weekly', 'Hebdomadaire'),
        ('biweekly', 'Bihebdomadaire'),
        ('monthly', 'Mensuel'),
        ('custom', 'Personnalisé'),
    ]

    OPTIMIZATION_PRIORITIES = [
        ('teacher', 'Enseignant'),
        ('room', 'Salle'),
        ('balanced', 'Équilibré'),
    ]

    FLEXIBILITY_LEVELS = [
        ('rigid', 'Rigide'),
        ('balanced', 'Équilibré'),
        ('flexible', 'Flexible'),
    ]

    schedule = models.OneToOneField(Schedule, on_delete=models.CASCADE, related_name='generation_config')

    # Période de génération
    start_date = models.DateField()
    end_date = models.DateField()

    # Paramètres de récurrence
    recurrence_type = models.CharField(max_length=15, choices=RECURRENCE_TYPES, default='weekly')
    recurrence_pattern = models.CharField(max_length=200, blank=True)  # Format iCalendar RRULE

    # Paramètres de génération
    flexibility_level = models.CharField(max_length=15, choices=FLEXIBILITY_LEVELS, default='balanced')
    allow_conflicts = models.BooleanField(default=False)
    max_sessions_per_day = models.IntegerField(default=4)
    respect_teacher_preferences = models.BooleanField(default=True)
    respect_room_preferences = models.BooleanField(default=True)
    optimization_priority = models.CharField(max_length=15, choices=OPTIMIZATION_PRIORITIES, default='balanced')

    # Nouvelles contraintes horaires
    min_break_between_sessions = models.IntegerField(default=15, help_text="Minutes de pause minimale entre sessions")
    max_consecutive_sessions = models.IntegerField(default=3, help_text="Nombre max de sessions consécutives")
    preferred_start_time = models.TimeField(null=True, blank=True, help_text="Heure de début préférée (ex: 08:00)")
    preferred_end_time = models.TimeField(null=True, blank=True, help_text="Heure de fin préférée (ex: 18:00)")

    # Contraintes de charge de travail
    max_hours_per_day_students = models.IntegerField(default=8, help_text="Heures max par jour pour les étudiants")
    max_hours_per_week_students = models.IntegerField(default=30, help_text="Heures max par semaine pour les étudiants")

    # Contraintes enseignants
    max_hours_per_day_teachers = models.IntegerField(default=6, help_text="Heures max par jour pour un enseignant")
    min_rest_time_teachers = models.IntegerField(default=30, help_text="Temps de repos min entre cours (minutes)")

    # Distribution des cours
    distribute_evenly = models.BooleanField(default=True, help_text="Distribuer équitablement les cours sur la semaine")
    avoid_single_sessions = models.BooleanField(default=True, help_text="Éviter les journées avec une seule session")
    group_same_subject = models.BooleanField(default=False, help_text="Grouper les sessions d'une même matière")

    # Préférences de jours
    preferred_days = models.JSONField(default=list, help_text="Jours préférés ['monday', 'tuesday', etc.]")
    excluded_days = models.JSONField(default=list, help_text="Jours exclus ['saturday', 'sunday']")

    # Jours exclus (jours fériés, etc.)
    excluded_dates = models.JSONField(default=list)  # Liste de dates au format YYYY-MM-DD

    # Semaines spéciales (examens, etc.)
    special_weeks = models.JSONField(default=list)  # [{start_date, end_date, type, suspend_classes}]

    # Métadonnées
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='generation_configs')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Config {self.schedule.name} - {self.start_date} à {self.end_date}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Configuration de génération'
        verbose_name_plural = 'Configurations de génération'

    def is_date_excluded(self, date):
        """Vérifie si une date est exclue"""
        date_str = date.strftime('%Y-%m-%d')
        return date_str in self.excluded_dates

    def get_special_week(self, date):
        """Retourne les infos de la semaine spéciale si la date est dans une semaine spéciale"""
        from datetime import datetime
        for week in self.special_weeks:
            start = datetime.strptime(week['start_date'], '%Y-%m-%d').date()
            end = datetime.strptime(week['end_date'], '%Y-%m-%d').date()
            if start <= date <= end:
                return week
        return None


class SessionOccurrence(models.Model):
    """Occurrence individuelle d'une session planifiée (instance concrète d'un cours)"""
    SESSION_STATUS = [
        ('scheduled', 'Planifié'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminé'),
        ('cancelled', 'Annulé'),
        ('rescheduled', 'Reprogrammé'),
    ]

    # Référence au template de session
    session_template = models.ForeignKey(
        ScheduleSession,
        on_delete=models.CASCADE,
        related_name='occurrences'
    )

    # Date et heure concrètes
    actual_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    # Ressources (peuvent être différentes du template)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)

    # Statut et suivi
    status = models.CharField(max_length=15, choices=SESSION_STATUS, default='scheduled')
    attendance_count = models.IntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    # Modifications par rapport au template
    is_room_modified = models.BooleanField(default=False)
    is_teacher_modified = models.BooleanField(default=False)
    is_time_modified = models.BooleanField(default=False)

    # Annulation / Reprogrammation
    is_cancelled = models.BooleanField(default=False)
    cancellation_reason = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_sessions'
    )

    # Reprogrammation
    rescheduled_from = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rescheduled_to'
    )

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.session_template.course.code} - {self.actual_date} {self.start_time}"

    class Meta:
        ordering = ['actual_date', 'start_time']
        unique_together = ['session_template', 'actual_date', 'start_time']
        indexes = [
            models.Index(fields=['actual_date', 'status']),
            models.Index(fields=['room', 'actual_date']),
            models.Index(fields=['teacher', 'actual_date']),
            models.Index(fields=['session_template', 'actual_date']),
        ]
        verbose_name = 'Occurrence de session'
        verbose_name_plural = 'Occurrences de sessions'

    def get_duration_hours(self):
        """Retourne la durée en heures de l'occurrence"""
        duration = timezone.datetime.combine(timezone.datetime.today(), self.end_time) - \
                  timezone.datetime.combine(timezone.datetime.today(), self.start_time)
        return duration.total_seconds() / 3600

    def cancel(self, reason, cancelled_by):
        """Annule l'occurrence"""
        self.status = 'cancelled'
        self.is_cancelled = True
        self.cancellation_reason = reason
        self.cancelled_at = timezone.now()
        self.cancelled_by = cancelled_by
        self.save()

    def reschedule(self, new_date, new_start_time, new_end_time, new_room=None, new_teacher=None):
        """Reprogramme l'occurrence en créant une nouvelle occurrence"""
        new_occurrence = SessionOccurrence.objects.create(
            session_template=self.session_template,
            actual_date=new_date,
            start_time=new_start_time,
            end_time=new_end_time,
            room=new_room or self.room,
            teacher=new_teacher or self.teacher,
            status='scheduled',
            rescheduled_from=self,
            is_room_modified=new_room is not None and new_room != self.room,
            is_teacher_modified=new_teacher is not None and new_teacher != self.teacher,
            is_time_modified=True,
        )

        # Marque l'occurrence actuelle comme reprogrammée
        self.status = 'rescheduled'
        self.save()

        return new_occurrence

    def check_conflicts(self):
        """Vérifie les conflits pour cette occurrence"""
        from datetime import datetime, timedelta
        conflicts = []

        # Fonction helper pour vérifier le chevauchement avec buffer
        def has_overlap_with_buffer(start1, end1, start2, end2):
            """Vérifie le chevauchement avec buffer de 5 minutes"""
            today = datetime.today().date()
            dt_start1 = datetime.combine(today, start1)
            dt_end1 = datetime.combine(today, end1)
            dt_start2 = datetime.combine(today, start2)
            dt_end2 = datetime.combine(today, end2)

            transition_buffer = timedelta(minutes=5)
            dt_end1_with_buffer = dt_end1 + transition_buffer
            dt_end2_with_buffer = dt_end2 + transition_buffer

            return not (dt_end1_with_buffer <= dt_start2 or dt_end2_with_buffer <= dt_start1)

        # Conflit de salle
        room_conflicts = SessionOccurrence.objects.filter(
            room=self.room,
            actual_date=self.actual_date,
            status='scheduled'
        ).exclude(id=self.id)

        for rc in room_conflicts:
            if has_overlap_with_buffer(self.start_time, self.end_time, rc.start_time, rc.end_time):
                conflicts.append({
                    'type': 'room_double_booking',
                    'severity': 'critical',
                    'description': f"La salle {self.room.code} est déjà occupée",
                    'conflicting_course': rc.session_template.course.code,
                    'time': f"{rc.start_time} - {rc.end_time}"
                })
                break  # Un seul conflit suffit pour la salle

        # Conflit d'enseignant
        teacher_conflicts = SessionOccurrence.objects.filter(
            teacher=self.teacher,
            actual_date=self.actual_date,
            status='scheduled'
        ).exclude(id=self.id)

        for tc in teacher_conflicts:
            if has_overlap_with_buffer(self.start_time, self.end_time, tc.start_time, tc.end_time):
                conflicts.append({
                    'type': 'teacher_double_booking',
                    'severity': 'critical',
                    'description': f"L'enseignant {self.teacher.user.get_full_name()} est déjà occupé",
                    'conflicting_course': tc.session_template.course.code,
                    'time': f"{tc.start_time} - {tc.end_time}"
                })
                break  # Un seul conflit suffit pour l'enseignant

        return conflicts
