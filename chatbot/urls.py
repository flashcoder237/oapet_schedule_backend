"""
URLs pour l'API chatbot
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'conversations', views.ConversationViewSet, basename='conversation')
router.register(r'messages', views.MessageViewSet, basename='message')
router.register(r'knowledge', views.ChatbotKnowledgeViewSet, basename='knowledge')
router.register(r'feedback', views.UserFeedbackViewSet, basename='feedback')

urlpatterns = [
    path('', include(router.urls)),
    path('send/', views.send_message, name='send-message'),
    path('active/', views.get_active_conversation, name='active-conversation'),
    path('analytics/', views.chatbot_analytics, name='chatbot-analytics'),
    path('clear/', views.clear_history, name='clear-history'),
]
