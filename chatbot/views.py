"""
Vues API pour le chatbot
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg
from django.utils import timezone
from .models import Conversation, Message, ChatbotKnowledge, UserFeedback, ChatbotAnalytics
from .serializers import (
    ConversationSerializer, ConversationListSerializer, MessageSerializer,
    ChatMessageInputSerializer, ChatbotKnowledgeSerializer,
    UserFeedbackSerializer, ChatbotAnalyticsSerializer
)
from .services import ChatbotService


class ConversationViewSet(viewsets.ModelViewSet):
    """ViewSet pour les conversations"""
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'list':
            return ConversationListSerializer
        return ConversationSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive une conversation"""
        conversation = self.get_object()
        conversation.is_active = False
        conversation.save()
        return Response({'status': 'conversation archived'})

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restaure une conversation"""
        conversation = self.get_object()
        conversation.is_active = True
        conversation.save()
        return Response({'status': 'conversation restored'})


class MessageViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour les messages (lecture seule)"""
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Message.objects.filter(conversation__user=self.request.user)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_message(request):
    """Envoie un message au chatbot et reçoit une réponse"""
    serializer = ChatMessageInputSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user_message = serializer.validated_data['message']
    conversation_id = serializer.validated_data.get('conversation_id')

    # Récupérer ou créer la conversation
    if conversation_id:
        try:
            conversation = Conversation.objects.get(id=conversation_id, user=request.user)
        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    else:
        # Créer une nouvelle conversation
        conversation = Conversation.objects.create(user=request.user)

    # Sauvegarder le message de l'utilisateur
    user_msg = Message.objects.create(
        conversation=conversation,
        sender='user',
        content=user_message
    )

    # Traiter le message avec le service chatbot
    chatbot_service = ChatbotService()
    bot_response = chatbot_service.process_message(user_message, request.user, conversation)

    # Sauvegarder la réponse du bot
    bot_msg = Message.objects.create(
        conversation=conversation,
        sender='bot',
        content=bot_response['response'],
        intent=bot_response.get('intent'),
        confidence=bot_response.get('confidence'),
        context_data=bot_response.get('context_data', {}),
        has_attachments=len(bot_response.get('attachments', [])) > 0,
        attachments=bot_response.get('attachments', [])
    )

    # Mettre à jour le titre de la conversation si c'est le premier message
    if conversation.messages.count() == 2:  # user + bot
        preview = user_message[:50] + '...' if len(user_message) > 50 else user_message
        conversation.title = preview
        conversation.save()

    return Response({
        'conversation_id': conversation.id,
        'user_message': MessageSerializer(user_msg).data,
        'bot_response': MessageSerializer(bot_msg).data,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_conversation(request):
    """Récupère la conversation active de l'utilisateur"""
    conversation = Conversation.objects.filter(
        user=request.user,
        is_active=True
    ).order_by('-updated_at').first()

    if conversation:
        serializer = ConversationSerializer(conversation)
        return Response(serializer.data)
    else:
        return Response({'message': 'No active conversation'}, status=status.HTTP_404_NOT_FOUND)


class ChatbotKnowledgeViewSet(viewsets.ModelViewSet):
    """ViewSet pour la base de connaissances"""
    queryset = ChatbotKnowledge.objects.all()
    serializer_class = ChatbotKnowledgeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        return queryset.filter(is_active=True)


class UserFeedbackViewSet(viewsets.ModelViewSet):
    """ViewSet pour le feedback utilisateur"""
    serializer_class = UserFeedbackSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserFeedback.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chatbot_analytics(request):
    """Récupère les statistiques du chatbot"""
    today = timezone.now().date()

    # Statistiques générales
    total_conversations = Conversation.objects.filter(user=request.user).count()
    total_messages = Message.objects.filter(conversation__user=request.user).count()

    # Statistiques récentes (7 derniers jours)
    week_ago = today - timezone.timedelta(days=7)
    recent_conversations = Conversation.objects.filter(
        user=request.user,
        created_at__date__gte=week_ago
    ).count()

    # Intent distribution
    intent_stats = Message.objects.filter(
        conversation__user=request.user,
        sender='bot',
        intent__isnull=False
    ).values('intent').annotate(count=Count('intent')).order_by('-count')[:5]

    # Satisfaction moyenne
    avg_rating = UserFeedback.objects.filter(
        user=request.user
    ).aggregate(avg=Avg('rating'))['avg'] or 0

    return Response({
        'total_conversations': total_conversations,
        'total_messages': total_messages,
        'recent_conversations': recent_conversations,
        'top_intents': list(intent_stats),
        'average_rating': round(avg_rating, 2),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clear_history(request):
    """Supprime l'historique des conversations"""
    conversation_id = request.data.get('conversation_id')

    if conversation_id:
        # Supprimer une conversation spécifique
        try:
            conversation = Conversation.objects.get(id=conversation_id, user=request.user)
            conversation.delete()
            return Response({'status': 'conversation deleted'})
        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    else:
        # Supprimer toutes les conversations
        Conversation.objects.filter(user=request.user).delete()
        return Response({'status': 'all conversations deleted'})
