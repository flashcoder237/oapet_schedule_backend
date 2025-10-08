"""
Serializers pour l'API chatbot
"""
from rest_framework import serializers
from .models import Conversation, Message, ChatbotKnowledge, UserFeedback, ChatbotAnalytics


class MessageSerializer(serializers.ModelSerializer):
    """Serializer pour les messages"""
    class Meta:
        model = Message
        fields = ['id', 'conversation', 'sender', 'content', 'timestamp',
                  'intent', 'confidence', 'context_data', 'has_attachments', 'attachments']
        read_only_fields = ['id', 'timestamp']


class ConversationSerializer(serializers.ModelSerializer):
    """Serializer pour les conversations"""
    messages = MessageSerializer(many=True, read_only=True)
    message_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'user', 'title', 'created_at', 'updated_at',
                  'is_active', 'messages', 'message_count', 'last_message']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_message_count(self, obj):
        return obj.messages.count()

    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        if last_msg:
            return {
                'content': last_msg.content,
                'sender': last_msg.sender,
                'timestamp': last_msg.timestamp
            }
        return None


class ConversationListSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour la liste des conversations"""
    message_count = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'title', 'created_at', 'updated_at',
                  'is_active', 'message_count', 'last_message_preview']

    def get_message_count(self, obj):
        return obj.messages.count()

    def get_last_message_preview(self, obj):
        last_msg = obj.messages.last()
        if last_msg:
            content = last_msg.content[:50] + '...' if len(last_msg.content) > 50 else last_msg.content
            return {
                'content': content,
                'sender': last_msg.sender,
                'timestamp': last_msg.timestamp
            }
        return None


class ChatMessageInputSerializer(serializers.Serializer):
    """Serializer pour l'envoi de messages au chatbot"""
    message = serializers.CharField(max_length=5000)
    conversation_id = serializers.IntegerField(required=False, allow_null=True)


class ChatbotKnowledgeSerializer(serializers.ModelSerializer):
    """Serializer pour la base de connaissances"""
    class Meta:
        model = ChatbotKnowledge
        fields = ['id', 'category', 'question', 'answer', 'keywords',
                  'priority', 'is_active', 'usage_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'usage_count', 'created_at', 'updated_at']


class UserFeedbackSerializer(serializers.ModelSerializer):
    """Serializer pour le feedback utilisateur"""
    class Meta:
        model = UserFeedback
        fields = ['id', 'message', 'user', 'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']


class ChatbotAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer pour les statistiques du chatbot"""
    class Meta:
        model = ChatbotAnalytics
        fields = ['date', 'total_conversations', 'total_messages',
                  'average_response_time', 'satisfaction_rate', 'top_intents']
        read_only_fields = ['date']
