# users/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Router pour les ViewSets
router = DefaultRouter()
router.register(r'profiles', views.UserProfileViewSet, basename='userprofile')
router.register(r'sessions', views.UserSessionViewSet, basename='usersession')
router.register(r'login-attempts', views.LoginAttemptViewSet, basename='loginattempt')

urlpatterns = [
    # Authentification
    path('auth/login/', views.enhanced_login, name='enhanced-login'),
    path('auth/logout/', views.enhanced_logout, name='enhanced-logout'),
    path('auth/me/', views.current_user, name='current-user'),
    path('auth/register/', views.register_user, name='register-user'),
    path('auth/change-password/', views.change_password, name='change-password'),
    
    # ViewSets
    path('', include(router.urls)),
]