"""
Administration Django pour le système de chatbot
"""
from django.contrib import admin
from .models import Conversation, Message, ChatbotKnowledge, UserFeedback, ChatbotAnalytics


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'title', 'created_at', 'updated_at', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__username', 'title']
    date_hierarchy = 'created_at'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'conversation', 'sender', 'content_preview', 'timestamp', 'intent']
    list_filter = ['sender', 'timestamp']
    search_fields = ['content', 'intent']
    date_hierarchy = 'timestamp'

    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Contenu'


@admin.register(ChatbotKnowledge)
class ChatbotKnowledgeAdmin(admin.ModelAdmin):
    list_display = ['id', 'category', 'question_preview', 'priority', 'usage_count', 'is_active']
    list_filter = ['category', 'is_active', 'priority']
    search_fields = ['question', 'answer', 'keywords']
    ordering = ['-priority', '-usage_count']

    def question_preview(self, obj):
        return obj.question[:50] + '...' if len(obj.question) > 50 else obj.question
    question_preview.short_description = 'Question'


@admin.register(UserFeedback)
class UserFeedbackAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'rating', 'message', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['user__username', 'comment']
    date_hierarchy = 'created_at'


@admin.register(ChatbotAnalytics)
class ChatbotAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_conversations', 'total_messages', 'average_response_time', 'satisfaction_rate']
    list_filter = ['date']
    date_hierarchy = 'date'
