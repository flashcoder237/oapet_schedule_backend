# courses/models_class.py
from django.db import models
from django.contrib.auth.models import User


class StudentClass(models.Model):
    """
    Modèle pour représenter une classe/groupe d'étudiants
    Simplifié pour la gestion d'emploi du temps sans gérer les étudiants individuellement
    """
    LEVEL_CHOICES = [
        ('L1', 'Licence 1'),
        ('L2', 'Licence 2'),
        ('L3', 'Licence 3'),
        ('M1', 'Master 1'),
        ('M2', 'Master 2'),
    ]

    # Informations de base
    name = models.CharField(max_length=100, help_text="Ex: INFO-L1-A")
    code = models.CharField(max_length=20, unique=True, help_text="Code unique de la classe")
    level = models.CharField(max_length=5, choices=LEVEL_CHOICES)

    # Département et cursus
    department = models.ForeignKey(
        'Department',
        on_delete=models.CASCADE,
        related_name='student_classes'
    )
    curriculum = models.ForeignKey(
        'Curriculum',
        on_delete=models.CASCADE,
        related_name='student_classes',
        null=True,
        blank=True,
        help_text="Cursus/Programme de la classe"
    )

    # Effectif
    student_count = models.IntegerField(
        default=0,
        help_text="Nombre d'étudiants dans cette classe"
    )
    max_capacity = models.IntegerField(
        default=50,
        help_text="Capacité maximale de la classe"
    )

    # Année académique
    academic_year = models.CharField(max_length=10, default='2024-2025')
    semester = models.CharField(
        max_length=5,
        choices=[('S1', 'Semestre 1'), ('S2', 'Semestre 2')],
        default='S1'
    )

    # Métadonnées
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_classes'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    # Notes optionnelles
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    # Contraintes de salle et horaires fixes
    fixed_room = models.ForeignKey(
        'rooms.Room',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fixed_classes',
        help_text="Salle fixe attribuée à cette classe (si applicable)"
    )
    has_fixed_schedule = models.BooleanField(
        default=False,
        help_text="Cette classe a-t-elle un emploi du temps fixe qui se répète chaque semaine?"
    )
    fixed_schedule_pattern = models.JSONField(
        default=dict,
        blank=True,
        help_text="Modèle d'emploi du temps fixe: {jour: [{heure_debut, heure_fin, cours_id}]}"
    )
    # Exemple: {"monday": [{"start": "08:00", "end": "10:00", "course_id": 5}], "tuesday": [...]}

    def __str__(self):
        return f"{self.code} - {self.name} ({self.student_count} étudiants)"

    class Meta:
        verbose_name = "Classe"
        verbose_name_plural = "Classes"
        ordering = ['level', 'code']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['level', 'academic_year']),
            models.Index(fields=['department', 'is_active']),
        ]

    @property
    def occupancy_rate(self):
        """Retourne le taux d'occupation de la classe"""
        if self.max_capacity > 0:
            return (self.student_count / self.max_capacity) * 100
        return 0

    def get_assigned_courses(self):
        """Retourne les cours assignés à cette classe"""
        return self.class_courses.filter(is_active=True).select_related('course')


class ClassCourse(models.Model):
    """
    Liaison entre une classe et ses cours
    """
    student_class = models.ForeignKey(
        StudentClass,
        on_delete=models.CASCADE,
        related_name='class_courses'
    )
    course = models.ForeignKey(
        'Course',
        on_delete=models.CASCADE,
        related_name='assigned_classes'
    )

    # Informations complémentaires
    is_mandatory = models.BooleanField(default=True)
    semester = models.CharField(max_length=5, default='S1')
    order = models.IntegerField(default=0, help_text="Ordre d'affichage")

    # Effectif spécifique pour ce cours (optionnel)
    # Utile si tous les étudiants ne prennent pas le cours
    specific_student_count = models.IntegerField(
        null=True,
        blank=True,
        help_text="Nombre d'étudiants pour ce cours spécifiquement (sinon utilise l'effectif de la classe)"
    )

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.student_class.code} - {self.course.code}"

    class Meta:
        verbose_name = "Cours de la classe"
        verbose_name_plural = "Cours des classes"
        unique_together = ['student_class', 'course']
        ordering = ['semester', 'order']

    @property
    def effective_student_count(self):
        """Retourne l'effectif effectif pour ce cours"""
        return self.specific_student_count or self.student_class.student_count
