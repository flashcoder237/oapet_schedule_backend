"""
Modèles pour le système de chatbot intelligent OAPET
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Conversation(models.Model):
    """Conversation entre un utilisateur et le chatbot"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')
    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Conversation {self.id} - {self.user.username}"

    def save(self, *args, **kwargs):
        # Générer un titre automatique si vide
        if not self.title:
            now = timezone.now()
            self.title = f"Conversation du {now.strftime('%d/%m/%Y a %H:%M')}"
        super().save(*args, **kwargs)


class Message(models.Model):
    """Message dans une conversation"""
    SENDER_CHOICES = [
        ('user', 'Utilisateur'),
        ('bot', 'Chatbot'),
        ('system', 'Système'),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    # Métadonnées pour l'IA
    intent = models.CharField(max_length=100, blank=True, null=True)
    confidence = models.FloatField(blank=True, null=True)
    context_data = models.JSONField(default=dict, blank=True)

    # Pour les réponses structurées
    has_attachments = models.BooleanField(default=False)
    attachments = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender}: {self.content[:50]}..."


class ChatbotKnowledge(models.Model):
    """Base de connaissances pour le chatbot"""
    CATEGORY_CHOICES = [
        ('schedule', 'Emploi du temps'),
        ('course', 'Cours'),
        ('room', 'Salles'),
        ('teacher', 'Enseignants'),
        ('general', 'Général'),
        ('faq', 'FAQ'),
    ]

    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    question = models.TextField()
    answer = models.TextField()
    keywords = models.JSONField(default=list, blank=True)
    priority = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    usage_count = models.IntegerField(default=0)

    class Meta:
        ordering = ['-priority', '-usage_count']

    def __str__(self):
        return f"{self.category}: {self.question[:50]}..."


class UserFeedback(models.Model):
    """Feedback utilisateur sur les réponses du chatbot"""
    RATING_CHOICES = [
        (1, 'Très mauvais'),
        (2, 'Mauvais'),
        (3, 'Moyen'),
        (4, 'Bon'),
        (5, 'Excellent'),
    ]

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='feedbacks')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=RATING_CHOICES)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Feedback {self.rating}/5 - {self.user.username}"


class ChatbotAnalytics(models.Model):
    """Statistiques d'utilisation du chatbot"""
    date = models.DateField(default=timezone.now)
    total_conversations = models.IntegerField(default=0)
    total_messages = models.IntegerField(default=0)
    average_response_time = models.FloatField(default=0.0)
    satisfaction_rate = models.FloatField(default=0.0)
    top_intents = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['-date']
        unique_together = ['date']

    def __str__(self):
        return f"Analytics {self.date}"
