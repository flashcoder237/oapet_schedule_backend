# users/permissions.py
from rest_framework import permissions
from .models import UserProfile


class RoleBasedPermission(permissions.BasePermission):
    """Permission basée sur les rôles utilisateur"""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Les admins ont tous les droits
        if request.user.is_superuser:
            return True
        
        profile = getattr(request.user, 'profile', None)
        if not profile:
            return False
        
        # Permissions par action
        action = getattr(view, 'action', None)
        
        # Lecture : tous les utilisateurs authentifiés
        if action in ['list', 'retrieve']:
            return True
        
        # Création/Modification/Suppression : selon le rôle
        if action in ['create', 'update', 'partial_update', 'destroy']:
            return profile.role in ['admin', 'department_head', 'scheduler']
        
        return True


class DepartmentPermission(permissions.BasePermission):
    """Permission basée sur l'appartenance au département"""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Les admins ont tous les droits
        if request.user.is_superuser:
            return True
        
        return True
    
    def has_object_permission(self, request, view, obj):
        # Les admins ont tous les droits
        if request.user.is_superuser:
            return True
        
        profile = getattr(request.user, 'profile', None)
        if not profile:
            return False
        
        # Chef de département peut gérer son département
        if profile.role == 'department_head':
            if hasattr(obj, 'department'):
                return profile.can_manage_department(obj.department)
            elif hasattr(obj, 'curriculum') and hasattr(obj.curriculum, 'department'):
                return profile.can_manage_department(obj.curriculum.department)
        
        # Enseignant peut voir/modifier ses propres ressources
        if profile.role == 'teacher':
            if hasattr(obj, 'teacher'):
                return obj.teacher.user == request.user
            elif hasattr(obj, 'user'):
                return obj.user == request.user
        
        # Étudiant peut voir ses propres données
        if profile.role == 'student':
            if hasattr(obj, 'student'):
                return obj.student.user == request.user
            elif hasattr(obj, 'user'):
                return obj.user == request.user
        
        return False


class SchedulePermission(permissions.BasePermission):
    """Permission pour la gestion des emplois du temps"""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Les admins ont tous les droits
        if request.user.is_superuser:
            return True
        
        profile = getattr(request.user, 'profile', None)
        if not profile:
            return False
        
        action = getattr(view, 'action', None)
        
        # Lecture : tous les utilisateurs authentifiés
        if action in ['list', 'retrieve']:
            return True
        
        # Modification : admin, planificateur, chef de département
        if action in ['create', 'update', 'partial_update']:
            return profile.role in ['admin', 'scheduler', 'department_head']
        
        # Publication : admin, planificateur
        if action in ['publish', 'unpublish']:
            return profile.role in ['admin', 'scheduler']
        
        # Suppression : admin seulement
        if action == 'destroy':
            return profile.role == 'admin'
        
        return True
    
    def has_object_permission(self, request, view, obj):
        # Les admins ont tous les droits
        if request.user.is_superuser:
            return True
        
        profile = getattr(request.user, 'profile', None)
        if not profile:
            return False
        
        # Vérification spécifique selon le rôle
        return profile.can_edit_schedule(obj)


class MLPermission(permissions.BasePermission):
    """Permission pour l'utilisation du ML"""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Les admins ont tous les droits
        if request.user.is_superuser:
            return True
        
        profile = getattr(request.user, 'profile', None)
        if not profile:
            return False
        
        action = getattr(view, 'action', None)
        
        # Prédictions : enseignants, planificateurs, chefs de département
        if action in ['predict_course_difficulty', 'get_predictions']:
            return profile.role in ['admin', 'teacher', 'scheduler', 'department_head']
        
        # Gestion des modèles : admin, planificateur
        if action in ['create', 'update', 'destroy', 'set_active']:
            return profile.role in ['admin', 'scheduler']
        
        # Entraînement : admin seulement
        if action in ['start_training', 'cancel_training']:
            return profile.role == 'admin'
        
        return True


class AdminOnlyPermission(permissions.BasePermission):
    """Permission pour les administrateurs uniquement"""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_superuser or 
            (hasattr(request.user, 'profile') and request.user.profile.role == 'admin')
        )