"""
URL configuration for oapet_schedule_backend project.
Système de gestion d'emplois du temps universitaire avec IA
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from django.http import JsonResponse
from .dashboard_views import dashboard_stats, system_health
from .search_views import global_search, search_suggestions

def api_root(request):
    """Point d'entrée de l'API avec informations générales"""
    return JsonResponse({
        'message': 'API Système de Gestion d\'Emplois du Temps Universitaire',
        'version': '1.0.0',
        'endpoints': {
            'auth': '/api/auth/',
            'admin': '/admin/',
            'courses': '/api/courses/',
            'rooms': '/api/rooms/', 
            'schedules': '/api/schedules/',
            'ml_engine': '/api/ml/',
            'docs': '/api/docs/'
        },
        'features': [
            'Gestion des cours et enseignants',
            'Gestion des salles et équipements',
            'Planification d\'emplois du temps',
            'Intelligence artificielle pour l\'optimisation',
            'Détection de conflits automatique',
            'Export multi-format'
        ]
    })

# Configuration des URLs principales
urlpatterns = [
    # Administration Django
    path('admin/', admin.site.urls),
    
    # Point d'entrée de l'API
    path('api/', api_root, name='api-root'),
    
    # Authentification
    path('api/auth/token/', obtain_auth_token, name='api_token_auth'),
    
    # Endpoints dashboard
    path('api/dashboard/stats/', dashboard_stats, name='dashboard-stats'),
    path('api/dashboard/health/', system_health, name='system-health'),

    # Endpoints recherche
    path('api/search/', global_search, name='global-search'),
    path('api/search/suggestions/', search_suggestions, name='search-suggestions'),
    
    # APIs des applications
    path('api/users/', include('users.urls')),
    path('api/courses/', include('courses.urls')),
    path('api/rooms/', include('rooms.urls')),
    path('api/schedules/', include('schedules.urls')),
    path('api/ml/', include('ml_engine.urls')),
    path('api/chatbot/', include('chatbot.urls')),
    
    # API de base pour l'authentification DRF
    path('api-auth/', include('rest_framework.urls')),
]

# Servir les fichiers média en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
