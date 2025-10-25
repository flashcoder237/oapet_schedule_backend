# users/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import UserProfile


@receiver(post_save, sender=UserProfile)
def create_teacher_on_teacher_role(sender, instance, created, **kwargs):
    """
    Crée automatiquement un objet Teacher quand un UserProfile
    avec le rôle 'teacher' est créé
    """
    # Importer ici pour éviter les imports circulaires
    from courses.models import Teacher, Department

    # Si le rôle est teacher et qu'aucun Teacher n'existe
    if instance.role == 'teacher' and instance.user:
        # Vérifier si un Teacher existe déjà pour cet utilisateur
        if not Teacher.objects.filter(user=instance.user).exists():
            # Essayer de récupérer le département du profil ou un département par défaut
            department = instance.department
            if not department:
                # Essayer de trouver ou créer un département par défaut
                department, _ = Department.objects.get_or_create(
                    code='DEFAULT',
                    defaults={
                        'name': 'Département par défaut',
                        'description': 'Département par défaut pour les enseignants'
                    }
                )

            # Créer l'objet Teacher
            Teacher.objects.create(
                user=instance.user,
                employee_id=instance.employee_id or f'TEACH-{instance.user.id}',
                department=department,
                is_active=instance.user.is_active
            )
