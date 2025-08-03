# users/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import UserProfile, UserSession, LoginAttempt, CustomPermission


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer pour les profils utilisateur"""
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'user_username', 'user_email', 'user_full_name',
            'role', 'phone', 'address', 'avatar', 'date_of_birth',
            'language', 'timezone', 'email_notifications', 'sms_notifications',
            'is_verified', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_verified']


class UserSessionSerializer(serializers.ModelSerializer):
    """Serializer pour les sessions utilisateur"""
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = UserSession
        fields = [
            'id', 'user_username', 'session_key', 'ip_address', 
            'user_agent', 'location', 'is_active', 'created_at', 'last_activity'
        ]
        read_only_fields = ['id', 'created_at', 'last_activity']


class LoginAttemptSerializer(serializers.ModelSerializer):
    """Serializer pour l'historique des connexions"""
    
    class Meta:
        model = LoginAttempt
        fields = [
            'id', 'username', 'ip_address', 'user_agent', 
            'success', 'failure_reason', 'timestamp'
        ]
        read_only_fields = ['id', 'timestamp']


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer pour l'inscription d'un nouvel utilisateur"""
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES, required=False, default='student')
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password', 'password_confirm', 'role']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Les mots de passe ne correspondent pas.")
        return attrs
    
    def create(self, validated_data):
        # Retirer password_confirm et role des données
        validated_data.pop('password_confirm')
        role = validated_data.pop('role', 'student')
        
        # Créer l'utilisateur
        user = User.objects.create_user(**validated_data)
        
        # Mettre à jour le profil avec le rôle
        if hasattr(user, 'profile'):
            user.profile.role = role
            user.profile.save()
        
        return user


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer pour le changement de mot de passe"""
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("Les nouveaux mots de passe ne correspondent pas.")
        return attrs


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour du profil"""
    
    class Meta:
        model = UserProfile
        fields = [
            'phone', 'address', 'date_of_birth', 'language', 
            'timezone', 'email_notifications', 'sms_notifications'
        ]
    
    def validate_phone(self, value):
        """Validation du numéro de téléphone"""
        if value and not value.startswith(('+237', '237', '6', '2')):
            raise serializers.ValidationError("Format de téléphone camerounais invalide.")
        return value


class UserDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour les utilisateurs"""
    profile = UserProfileSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'is_staff', 'is_superuser', 'last_login',
            'date_joined', 'profile'
        ]
        read_only_fields = ['id', 'username', 'last_login', 'date_joined']


class CustomPermissionSerializer(serializers.ModelSerializer):
    """Serializer pour les permissions personnalisées"""
    
    class Meta:
        model = CustomPermission
        fields = ['id', 'name', 'codename', 'description', 'category']
        read_only_fields = ['id']