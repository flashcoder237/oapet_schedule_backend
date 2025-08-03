# users/views.py
import uuid
from datetime import datetime, timedelta
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth.hashers import check_password

from .models import UserProfile, UserSession, LoginAttempt, CustomPermission


def get_client_ip(request):
    """Récupère l'IP du client"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request):
    """Récupère le user agent"""
    return request.META.get('HTTP_USER_AGENT', '')


@api_view(['POST'])
@permission_classes([AllowAny])
def enhanced_login(request):
    """Connexion avancée avec sécurité renforcée"""
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response({
            'error': 'Nom d\'utilisateur et mot de passe requis'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    # Vérifier le blocage IP (optionnel)
    recent_failures = LoginAttempt.objects.filter(
        ip_address=ip_address,
        success=False,
        timestamp__gte=timezone.now() - timedelta(minutes=15)
    ).count()
    
    if recent_failures >= 5:
        LoginAttempt.objects.create(
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            failure_reason='IP bloquée - trop de tentatives'
        )
        return Response({
            'error': 'Trop de tentatives échouées. Réessayez dans 15 minutes.'
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)
    
    # Tenter l'authentification
    user = authenticate(username=username, password=password)
    
    if user is not None:
        if user.is_active:
            # Vérifier si le compte est verrouillé
            profile = getattr(user, 'profile', None)
            if profile and profile.account_locked_until:
                if timezone.now() < profile.account_locked_until:
                    LoginAttempt.objects.create(
                        username=username,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        success=False,
                        failure_reason='Compte verrouillé'
                    )
                    return Response({
                        'error': f'Compte verrouillé jusqu\'à {profile.account_locked_until}'
                    }, status=status.HTTP_423_LOCKED)
                else:
                    # Déverrouiller le compte
                    profile.account_locked_until = None
                    profile.failed_login_attempts = 0
                    profile.save()
            
            # Connexion réussie
            token, created = Token.objects.get_or_create(user=user)
            
            # Enregistrer la session
            session_key = request.session.session_key or str(uuid.uuid4())
            UserSession.objects.update_or_create(
                user=user,
                session_key=session_key,
                defaults={
                    'ip_address': ip_address,
                    'user_agent': user_agent,
                    'is_active': True,
                    'last_activity': timezone.now()
                }
            )
            
            # Mettre à jour le profil
            if profile:
                profile.last_login_ip = ip_address
                profile.failed_login_attempts = 0
                profile.save()
            
            # Enregistrer la tentative réussie
            LoginAttempt.objects.create(
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                success=True
            )
            
            return Response({
                'token': token.key,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': profile.role if profile else 'student',
                    'last_login': user.last_login
                }
            }, status=status.HTTP_200_OK)
        else:
            LoginAttempt.objects.create(
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                failure_reason='Compte désactivé'
            )
            return Response({
                'error': 'Compte désactivé'
            }, status=status.HTTP_403_FORBIDDEN)
    else:
        # Échec d'authentification
        try:
            user_obj = User.objects.get(username=username)
            profile = getattr(user_obj, 'profile', None)
            if profile:
                profile.failed_login_attempts += 1
                
                # Verrouiller après 5 tentatives
                if profile.failed_login_attempts >= 5:
                    profile.account_locked_until = timezone.now() + timedelta(hours=1)
                    failure_reason = 'Compte verrouillé - trop de tentatives'
                else:
                    failure_reason = 'Mot de passe incorrect'
                
                profile.save()
            else:
                failure_reason = 'Utilisateur inexistant'
        except User.DoesNotExist:
            failure_reason = 'Utilisateur inexistant'
        
        LoginAttempt.objects.create(
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            failure_reason=failure_reason
        )
        
        return Response({
            'error': 'Identifiants invalides'
        }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enhanced_logout(request):
    """Déconnexion avec nettoyage de session"""
    try:
        # Supprimer le token
        request.user.auth_token.delete()
        
        # Marquer la session comme inactive
        UserSession.objects.filter(
            user=request.user,
            session_key=request.session.session_key
        ).update(is_active=False)
        
        return Response({
            'message': 'Déconnexion réussie'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'error': 'Erreur lors de la déconnexion'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    """Récupère les informations de l'utilisateur actuel"""
    user = request.user
    profile = getattr(user, 'profile', None)
    
    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'full_name': user.get_full_name(),
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'last_login': user.last_login,
        'date_joined': user.date_joined,
        'profile': {
            'role': profile.role if profile else 'student',
            'phone': profile.phone if profile else '',
            'language': profile.language if profile else 'fr',
            'timezone': profile.timezone if profile else 'Africa/Douala'
        } if profile else None
    }, status=status.HTTP_200_OK)


class UserProfileViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des profils utilisateur"""
    queryset = UserProfile.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Les utilisateurs normaux ne voient que leur profil
        if not self.request.user.is_superuser:
            queryset = queryset.filter(user=self.request.user)
        
        return queryset
    
    def get_serializer_class(self):
        from .serializers import UserProfileSerializer
        return UserProfileSerializer
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Profil de l'utilisateur actuel"""
        profile = getattr(request.user, 'profile', None)
        if profile:
            from .serializers import UserProfileSerializer
            serializer = UserProfileSerializer(profile)
            return Response(serializer.data)
        return Response({'error': 'Profil non trouvé'}, status=status.HTTP_404_NOT_FOUND)


class UserSessionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour la gestion des sessions utilisateur"""
    queryset = UserSession.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Les utilisateurs voient leurs propres sessions
        return UserSession.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        from .serializers import UserSessionSerializer
        return UserSessionSerializer
    
    @action(detail=True, methods=['post'])
    def terminate(self, request, pk=None):
        """Terminer une session"""
        session = self.get_object()
        session.is_active = False
        session.save()
        
        return Response({
            'message': 'Session terminée'
        }, status=status.HTTP_200_OK)


class LoginAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour l'historique des connexions"""
    queryset = LoginAttempt.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Seuls les admins voient tous les logs
        if self.request.user.is_superuser:
            return LoginAttempt.objects.all()
        
        # Les autres voient leurs propres tentatives
        return LoginAttempt.objects.filter(username=self.request.user.username)
    
    def get_serializer_class(self):
        from .serializers import LoginAttemptSerializer
        return LoginAttemptSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """Inscription d'un nouvel utilisateur"""
    from .serializers import UserRegistrationSerializer
    
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        
        # Créer le token
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'token': token.key,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            }
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Changement de mot de passe"""
    from .serializers import PasswordChangeSerializer
    
    serializer = PasswordChangeSerializer(data=request.data)
    if serializer.is_valid():
        # Vérifier l'ancien mot de passe
        if not check_password(serializer.validated_data['old_password'], request.user.password):
            return Response({
                'old_password': ['Mot de passe incorrect']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Changer le mot de passe
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        
        # Supprimer tous les tokens pour forcer une nouvelle connexion
        Token.objects.filter(user=request.user).delete()
        
        return Response({
            'message': 'Mot de passe modifié avec succès'
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
