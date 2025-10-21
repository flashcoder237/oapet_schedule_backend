# users/models.py
from django.db import models
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType


class UserProfile(models.Model):
    """Profil utilisateur étendu"""
    ROLE_CHOICES = [
        ('admin', 'Administrateur'),
        ('department_head', 'Chef de Département'),
        ('teacher', 'Enseignant'),
        ('student', 'Étudiant'),
        ('staff', 'Personnel Administratif'),
        ('scheduler', 'Planificateur'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    employee_id = models.CharField(max_length=50, blank=True, null=True, unique=True)
    department = models.ForeignKey('courses.Department', on_delete=models.SET_NULL, blank=True, null=True, related_name='users')
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    
    # Métadonnées de session
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    failed_login_attempts = models.IntegerField(default=0)
    account_locked_until = models.DateTimeField(blank=True, null=True)
    
    # Préférences
    language = models.CharField(max_length=5, default='fr')
    timezone = models.CharField(max_length=50, default='Africa/Douala')
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return f"{self.user.get_full_name()} ({self.get_role_display()})"
    
    class Meta:
        ordering = ['user__last_name', 'user__first_name']
        
    def has_role(self, role):
        """Vérifie si l'utilisateur a un rôle spécifique"""
        return self.role == role
    
    def can_manage_department(self, department=None):
        """Vérifie si l'utilisateur peut gérer un département"""
        if self.role == 'admin':
            return True
        if self.role == 'department_head' and department:
            return hasattr(self.user, 'headed_departments') and \
                   self.user.headed_departments.filter(id=department.id).exists()
        return False
    
    def can_edit_schedule(self, schedule=None):
        """Vérifie si l'utilisateur peut modifier un emploi du temps"""
        if self.role in ['admin', 'scheduler']:
            return True
        if self.role == 'department_head' and schedule:
            return schedule.curriculum and \
                   self.can_manage_department(schedule.curriculum.department)
        return False


class UserSession(models.Model):
    """Gestion des sessions utilisateur"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=40, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    location = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.ip_address}"
    
    class Meta:
        ordering = ['-last_activity']


class LoginAttempt(models.Model):
    """Historique des tentatives de connexion"""
    username = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    success = models.BooleanField()
    failure_reason = models.CharField(max_length=100, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        status = "Succès" if self.success else f"Échec ({self.failure_reason})"
        return f"{self.username} - {status} - {self.timestamp}"
    
    class Meta:
        ordering = ['-timestamp']


class CustomPermission(models.Model):
    """Permissions personnalisées pour le système OAPET"""
    name = models.CharField(max_length=100, unique=True)
    codename = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    category = models.CharField(max_length=50, default='general')
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['category', 'name']


# Signaux pour créer automatiquement les profils
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
