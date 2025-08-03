# courses/models.py
from django.db import models
from django.contrib.auth.models import User


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
    ]
    
    COURSE_TYPE_CHOICES = [
        ('CM', 'Cours Magistral'),
        ('TD', 'Travaux Dirigés'),
        ('TP', 'Travaux Pratiques'),
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
    semester = models.CharField(max_length=10, default='S1')  # S1, S2
    academic_year = models.CharField(max_length=10, default='2024-2025')
    min_sessions_per_week = models.IntegerField(default=1)
    max_sessions_per_week = models.IntegerField(default=3)
    preferred_times = models.JSONField(default=list)  # Créneaux préférés
    unavailable_times = models.JSONField(default=list)  # Créneaux indisponibles
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

    class Meta:
        ordering = ['code']


class Curriculum(models.Model):
    """Modèle pour les cursus/programmes"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='curricula')
    level = models.CharField(max_length=5, choices=Course.LEVEL_CHOICES)
    courses = models.ManyToManyField(Course, through='CurriculumCourse')
    total_credits = models.IntegerField(default=60)
    description = models.TextField(blank=True)
    academic_year = models.CharField(max_length=10, default='2024-2025')
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
    academic_year = models.CharField(max_length=10, default='2024-2025')
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
