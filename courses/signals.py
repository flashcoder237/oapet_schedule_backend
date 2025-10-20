# courses/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Teacher
from users.models import UserProfile


@receiver(post_save, sender=Teacher)
def create_teacher_profile(sender, instance, created, **kwargs):
    """
    Crée ou met à jour automatiquement un UserProfile avec le rôle 'professor'
    quand un Teacher est créé ou modifié
    """
    if instance.user:
        profile, profile_created = UserProfile.objects.get_or_create(
            user=instance.user
        )

        # Mettre à jour le rôle à professor
        if profile.role != 'professor':
            profile.role = 'professor'
            profile.save()
