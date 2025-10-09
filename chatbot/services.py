"""
Services pour le chatbot intelligent OAPET
"""
import re
from datetime import datetime, timedelta
from django.db.models import Q, Count, Avg
from django.utils import timezone
from courses.models import Course, Teacher, Department
from schedules.models import Schedule, ScheduleSession
from rooms.models import Room
from .models import ChatbotKnowledge
from difflib import SequenceMatcher


class ChatbotService:
    """Service principal du chatbot avec IA avancée"""

    def __init__(self):
        # Mémoire contextuelle pour les conversations
        self.context = {}

        self.intents = {
            'schedule': {
                'keywords': ['emploi', 'planning', 'horaire', 'programme', 'cours', 'session', 'quand', 'aujourd\'hui', 'demain', 'semaine', 'prochain'],
                'patterns': [
                    r'emploi.*temps',
                    r'(mon|mes)\s+cours',
                    r'quand.*cours',
                    r'planning.*(?:jour|semaine|mois)',
                    r'prochaine?\s+(?:cours|session)',
                ],
                'actions': ['view_schedule', 'find_next_class']
            },
            'course': {
                'keywords': ['cours', 'matière', 'module', 'enseignement', 'crédit', 'heures', 'leçon'],
                'patterns': [
                    r'(?:quel|quels|quelles)\s+cours',
                    r'cours.*(?:disponible|offert)',
                    r'information.*cours',
                ]
            },
            'room': {
                'keywords': ['salle', 'local', 'amphithéâtre', 'amphitheatre', 'classe', 'bâtiment', 'lieu', 'où'],
                'patterns': [
                    r'(?:où|ou)\s+(?:se trouve|est|trouver)',
                    r'salle.*(?:disponible|libre)',
                    r'capacité.*salle',
                ]
            },
            'teacher': {
                'keywords': ['professeur', 'enseignant', 'prof', 'instructeur', 'docteur', 'dr'],
                'patterns': [
                    r'(?:prof|professeur|enseignant).*(?:contact|email|téléphone)',
                    r'qui\s+enseigne',
                    r'contact.*(?:prof|professeur)',
                ]
            },
            'conflict': {
                'keywords': ['conflit', 'chevauchement', 'collision', 'problème', 'erreur', 'incompatible'],
                'patterns': [
                    r'conflit.*(?:emploi|planning|horaire)',
                    r'(?:cours|session).*(?:même.*temps|simultané)',
                ]
            },
            'availability': {
                'keywords': ['disponible', 'disponibilité', 'libre', 'occupé', 'réserver'],
                'patterns': [
                    r'(?:salle|prof).*disponible',
                    r'(?:qui|quand).*(?:libre|disponible)',
                ]
            },
            'statistics': {
                'keywords': ['statistique', 'nombre', 'combien', 'total', 'moyenne'],
                'patterns': [
                    r'combien\s+de\s+(?:cours|salles|professeurs)',
                    r'(?:nombre|total).*(?:cours|session)',
                ]
            },
            'help': {
                'keywords': ['aide', 'comment', 'qui', 'quoi', 'où', 'quand', 'pourquoi', 'help', 'info'],
                'patterns': [
                    r'comment.*(?:faire|utiliser|fonction)',
                    r'(?:qu\'est|c\'est\s+quoi)',
                ]
            },
            'greeting': {
                'keywords': ['bonjour', 'salut', 'hello', 'bonsoir', 'hey', 'hi', 'coucou'],
                'patterns': [
                    r'^(?:bonjour|salut|hello|hey|hi|bonsoir)',
                ]
            },
            'thanks': {
                'keywords': ['merci', 'thank', 'remercie'],
                'patterns': [
                    r'merci(?:\s+beaucoup)?',
                    r'je\s+(?:te|vous)\s+remercie',
                ]
            },
            'create': {
                'keywords': ['creer', 'ajouter', 'nouveau', 'nouvelle', 'inscrire', 'enregistrer'],
                'patterns': [
                    r'(?:creer|ajouter|nouveau)\s+(?:cours|salle|enseignant|etudiant)',
                    r'(?:inscrire|enregistrer)\s+un',
                ]
            },
            'modify': {
                'keywords': ['modifier', 'changer', 'mettre a jour', 'editer', 'corriger'],
                'patterns': [
                    r'modifier.*(?:cours|salle|horaire)',
                    r'changer.*(?:date|heure|salle)',
                ]
            },
            'delete': {
                'keywords': ['supprimer', 'effacer', 'retirer', 'annuler'],
                'patterns': [
                    r'supprimer.*(?:cours|session)',
                    r'annuler.*(?:cours|reservation)',
                ]
            },
            'search': {
                'keywords': ['chercher', 'trouver', 'rechercher', 'localiser'],
                'patterns': [
                    r'(?:chercher|trouver|rechercher)\s+(?:cours|salle|prof)',
                    r'ou\s+(?:se trouve|est|trouver)',
                ]
            },
            'recommendation': {
                'keywords': ['suggerer', 'proposer', 'recommander', 'meilleur', 'optimal'],
                'patterns': [
                    r'(?:suggerer|proposer|recommander)\s+',
                    r'(?:meilleur|optimal).*(?:horaire|planning)',
                ]
            },
            'export': {
                'keywords': ['exporter', 'telecharger', 'extraire', 'sauvegarder'],
                'patterns': [
                    r'exporter.*(?:emploi|planning|donnees)',
                    r'telecharger.*(?:csv|excel|pdf)',
                ]
            },
        }

    def detect_intent(self, message):
        """Détecte l'intention de l'utilisateur avec NLP amélioré"""
        message_lower = message.lower()
        message_words = message_lower.split()

        intent_scores = {}

        for intent, data in self.intents.items():
            score = 0

            # Score basé sur les mots-clés
            keywords = data.get('keywords', [])
            keyword_matches = sum(1 for keyword in keywords if keyword in message_lower)
            score += keyword_matches * 2

            # Score basé sur les patterns regex
            patterns = data.get('patterns', [])
            for pattern in patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    score += 3

            # Score de similarité avec Levenshtein
            for keyword in keywords:
                for word in message_words:
                    similarity = SequenceMatcher(None, keyword, word).ratio()
                    if similarity > 0.8:
                        score += similarity

            if score > 0:
                intent_scores[intent] = score

        if intent_scores:
            detected_intent = max(intent_scores, key=intent_scores.get)
            max_score = intent_scores[detected_intent]
            # Calculer la confiance normalisée
            total_score = sum(intent_scores.values())
            confidence = min((max_score / total_score) * 100, 99)
            return detected_intent, confidence

        return 'unknown', 0.0

    def process_message(self, message, user):
        """Traite le message et génère une réponse avec contexte"""
        intent, confidence = self.detect_intent(message)

        # Gérer le contexte de la conversation
        user_context = self.context.get(user.id, {})

        # Chercher dans la base de connaissances
        knowledge_response = self._search_knowledge_base(message, intent)
        if knowledge_response:
            return {
                'response': knowledge_response['answer'],
                'intent': intent,
                'confidence': confidence,
                'context_data': {'source': 'knowledge_base'},
                'attachments': []
            }

        # Traiter selon l'intention avec contexte
        handlers = {
            'greeting': lambda: self._handle_greeting(user),
            'thanks': lambda: self._handle_thanks(user),
            'schedule': lambda: self._handle_schedule_query(message, user, user_context),
            'course': lambda: self._handle_course_query(message, user, user_context),
            'room': lambda: self._handle_room_query(message, user),
            'teacher': lambda: self._handle_teacher_query(message, user),
            'conflict': lambda: self._handle_conflict_query(message, user),
            'availability': lambda: self._handle_availability_query(message, user),
            'statistics': lambda: self._handle_statistics_query(message, user),
            'create': lambda: self._handle_create_action(message, user),
            'modify': lambda: self._handle_modify_action(message, user),
            'delete': lambda: self._handle_delete_action(message, user),
            'search': lambda: self._handle_search_query(message, user),
            'recommendation': lambda: self._handle_recommendation(message, user),
            'export': lambda: self._handle_export_request(message, user),
            'help': lambda: self._handle_help(),
        }

        handler = handlers.get(intent, self._handle_unknown)
        response = handler()

        # Mettre à jour le contexte
        self.context[user.id] = {
            'last_intent': intent,
            'last_message': message,
            'timestamp': timezone.now()
        }

        return response

    def _search_knowledge_base(self, message, intent):
        """Recherche dans la base de connaissances"""
        message_lower = message.lower()

        # Recherche par catégorie et mots-clés
        knowledge = ChatbotKnowledge.objects.filter(
            is_active=True,
            category=intent
        )

        for kb in knowledge:
            keywords = kb.keywords if isinstance(kb.keywords, list) else []
            if any(keyword.lower() in message_lower for keyword in keywords):
                kb.usage_count += 1
                kb.save()
                return {
                    'answer': kb.answer,
                    'category': kb.category
                }

        return None

    def _handle_greeting(self, user):
        """Gère les salutations"""
        hour = datetime.now().hour
        if hour < 12:
            greeting = "Bonjour"
        elif hour < 18:
            greeting = "Bon après-midi"
        else:
            greeting = "Bonsoir"

        response = f"{greeting} {user.first_name or user.username} !\n\n"
        response += "Je suis l'assistant intelligent OAPET. Je peux vous aider avec :\n"
        response += "- Consulter les emplois du temps\n"
        response += "- Obtenir des informations sur les cours\n"
        response += "- Trouver des salles disponibles\n"
        response += "- Contacter des enseignants\n"
        response += "- Repondre a vos questions\n\n"
        response += "Comment puis-je vous aider aujourd'hui ?"

        return {
            'response': response,
            'intent': 'greeting',
            'confidence': 100,
            'context_data': {'greeting_time': hour},
            'attachments': []
        }

    def _handle_schedule_query(self, message, user, context=None):
        """Gère les questions sur les emplois du temps avec contexte"""
        # Chercher des dates dans le message
        today = timezone.now().date()
        message_lower = message.lower()

        # Détection intelligente de la période demandée
        if 'demain' in message_lower:
            today = today + timezone.timedelta(days=1)
        elif 'hier' in message_lower:
            today = today - timezone.timedelta(days=1)
        elif any(word in message_lower for word in ['prochaine', 'prochain']):
            # Chercher la prochaine session
            return self._find_next_session(user)

        # Récupérer les sessions d'aujourd'hui
        sessions = ScheduleSession.objects.filter(
            specific_date=today
        ).select_related('course', 'room', 'teacher')[:5]

        if sessions:
            response = f"Emploi du temps pour aujourd'hui ({today.strftime('%d/%m/%Y')}) :\n\n"
            for session in sessions:
                start = session.specific_start_time or (session.time_slot.start_time if session.time_slot else "N/A")
                end = session.specific_end_time or (session.time_slot.end_time if session.time_slot else "N/A")
                response += f"- {start} - {end} : "
                response += f"{session.course.name}\n"
                teacher_name = session.teacher.user.get_full_name() if session.teacher else "N/A"
                room_name = session.room.name if session.room else "N/A"
                response += f"  Salle : {room_name}, Prof : {teacher_name}\n\n"
        else:
            response = "Aucune session programmee pour aujourd'hui."

        return {
            'response': response,
            'intent': 'schedule',
            'confidence': 85,
            'context_data': {'date': str(today), 'session_count': len(sessions)},
            'attachments': [{'type': 'schedule', 'sessions': list(sessions.values())}] if sessions else []
        }

    def _handle_course_query(self, message, user, context=None):
        """Gère les questions sur les cours avec recherche intelligente"""
        message_lower = message.lower()

        # Recherche intelligente dans le message
        courses = Course.objects.all()

        # Filtrer par mots-clés du message
        words = message_lower.split()
        for word in words:
            if len(word) > 3:
                courses = courses.filter(
                    Q(name__icontains=word) |
                    Q(code__icontains=word) |
                    Q(description__icontains=word)
                )

        courses = courses[:5]

        if courses:
            response = "Voici quelques cours disponibles :\n\n"
            for course in courses:
                response += f"- {course.name} ({course.code})\n"
                response += f"  Credits : {course.credits}, Heures : {course.hours_per_week}h/semaine\n"
                if course.teacher:
                    response += f"  Enseignant : {course.teacher.name}\n"
                response += "\n"
        else:
            response = "Aucun cours trouve dans la base de donnees."

        return {
            'response': response,
            'intent': 'course',
            'confidence': 80,
            'context_data': {'course_count': len(courses)},
            'attachments': []
        }

    def _handle_room_query(self, message, user):
        """Gère les questions sur les salles"""
        rooms = Room.objects.filter(is_active=True)[:5]

        if rooms:
            response = "Salles disponibles :\n\n"
            for room in rooms:
                response += f"- {room.name} ({room.building})\n"
                response += f"  Capacite : {room.capacity} places\n"
                if room.equipment:
                    response += f"  Equipements : {', '.join(room.equipment)}\n"
                response += "\n"
        else:
            response = "Aucune salle disponible actuellement."

        return {
            'response': response,
            'intent': 'room',
            'confidence': 80,
            'context_data': {'room_count': len(rooms)},
            'attachments': []
        }

    def _handle_teacher_query(self, message, user):
        """Gère les questions sur les enseignants"""
        teachers = Teacher.objects.filter(is_active=True)[:5]

        if teachers:
            response = "Enseignants disponibles :\n\n"
            for teacher in teachers:
                response += f"- {teacher.name}\n"
                if teacher.email:
                    response += f"  Email : {teacher.email}\n"
                if teacher.department:
                    response += f"  Departement : {teacher.department.name}\n"
                response += "\n"
        else:
            response = "Aucun enseignant trouve."

        return {
            'response': response,
            'intent': 'teacher',
            'confidence': 80,
            'context_data': {'teacher_count': len(teachers)},
            'attachments': []
        }

    def _handle_help(self):
        """Gère les demandes d'aide"""
        response = "Guide d'utilisation du chatbot OAPET\n\n"
        response += "Je peux vous aider avec les questions suivantes :\n\n"
        response += "**Emplois du temps**\n"
        response += '- "Quel est mon emploi du temps aujourd\'hui ?"\n'
        response += '- "Quand est mon prochain cours ?"\n\n'
        response += "**Cours**\n"
        response += '- "Quels cours sont disponibles ?"\n'
        response += '- "Montre-moi les cours de cette semaine"\n\n'
        response += "**Salles**\n"
        response += '- "Quelles salles sont disponibles ?"\n'
        response += '- "Ou se trouve la salle X ?"\n\n'
        response += "**Enseignants**\n"
        response += '- "Comment contacter le professeur X ?"\n'
        response += '- "Qui enseigne le cours Y ?"\n\n'
        response += "Posez-moi une question et je ferai de mon mieux pour vous aider !"

        return {
            'response': response,
            'intent': 'help',
            'confidence': 100,
            'context_data': {},
            'attachments': []
        }

    def _handle_unknown(self):
        """Gère les messages non compris"""
        response = "Je ne suis pas sur de comprendre votre question.\n\n"
        response += "Voici quelques suggestions :\n"
        response += "- Essayez de reformuler votre question\n"
        response += "- Utilisez des mots-cles comme 'emploi du temps', 'cours', 'salle'\n"
        response += "- Tapez 'aide' pour voir ce que je peux faire\n\n"
        response += "Je suis la pour vous aider !"

        # Ajouter des suggestions de questions
        suggestions = self._get_suggested_questions()

        return {
            'response': response,
            'intent': 'unknown',
            'confidence': 0,
            'context_data': {'suggestions': suggestions},
            'attachments': []
        }

    def _handle_thanks(self, user):
        """Gère les remerciements"""
        responses = [
            "De rien ! Je suis la pour vous aider.",
            "Avec plaisir ! N'hesitez pas si vous avez d'autres questions.",
            "Content de pouvoir vous aider !",
            "C'est un plaisir ! Bonne journee !",
        ]
        import random
        response = random.choice(responses)

        return {
            'response': response,
            'intent': 'thanks',
            'confidence': 100,
            'context_data': {},
            'attachments': []
        }

    def _handle_conflict_query(self, message, user):
        """Gère les questions sur les conflits d'horaire"""
        from schedules.models import ScheduleSession

        # Rechercher les conflits potentiels
        today = timezone.now().date()
        sessions = ScheduleSession.objects.filter(specific_date=today).order_by('specific_start_time')

        conflicts = []
        for i, session in enumerate(sessions):
            for other_session in sessions[i+1:]:
                # Obtenir les heures
                s1_start = session.specific_start_time or (session.time_slot.start_time if session.time_slot else None)
                s1_end = session.specific_end_time or (session.time_slot.end_time if session.time_slot else None)
                s2_start = other_session.specific_start_time or (other_session.time_slot.start_time if other_session.time_slot else None)
                s2_end = other_session.specific_end_time or (other_session.time_slot.end_time if other_session.time_slot else None)

                if not all([s1_start, s1_end, s2_start, s2_end]):
                    continue

                # Vérifier le chevauchement
                if (s1_start < s2_end and s1_end > s2_start):
                    # Vérifier si même salle ou même enseignant
                    if (session.room == other_session.room or
                        session.teacher == other_session.teacher):
                        conflicts.append({
                            'session1': session,
                            'session2': other_session,
                            'type': 'room' if session.room == other_session.room else 'teacher'
                        })

        if conflicts:
            response = f"J'ai detecte {len(conflicts)} conflit(s) aujourd'hui :\n\n"
            for conflict in conflicts[:3]:  # Limiter a 3
                s1, s2 = conflict['session1'], conflict['session2']
                response += f"- {s1.course.name} et {s2.course.name}\n"
                s1_start = s1.specific_start_time or (s1.time_slot.start_time if s1.time_slot else "N/A")
                s2_end = s2.specific_end_time or (s2.time_slot.end_time if s2.time_slot else "N/A")
                response += f"  Heure : {s1_start} - {s2_end}\n"
                if conflict['type'] == 'room':
                    response += f"  Conflit de salle : {s1.room.name}\n"
                else:
                    response += f"  Conflit d'enseignant : {s1.teacher.user.get_full_name()}\n"
                response += "\n"
        else:
            response = "Aucun conflit detecte dans l'emploi du temps actuel."

        return {
            'response': response,
            'intent': 'conflict',
            'confidence': 85,
            'context_data': {'conflict_count': len(conflicts)},
            'attachments': []
        }

    def _handle_availability_query(self, message, user):
        """Gère les questions sur la disponibilité"""
        message_lower = message.lower()

        # Determiner ce qui est demande
        if any(word in message_lower for word in ['salle', 'local', 'classe']):
            # Disponibilite des salles
            available_rooms = Room.objects.filter(is_active=True)[:5]
            response = "Salles actuellement disponibles :\n\n"
            for room in available_rooms:
                response += f"- {room.name} - Capacite : {room.capacity} places\n"
        elif any(word in message_lower for word in ['prof', 'enseignant', 'professeur']):
            # Disponibilite des enseignants
            teachers = Teacher.objects.filter(is_active=True)[:5]
            response = "Enseignants disponibles :\n\n"
            for teacher in teachers:
                response += f"- {teacher.name}\n"
                if teacher.email:
                    response += f"  Contact : {teacher.email}\n"
        else:
            response = "Pour verifier la disponibilite, precisez si vous cherchez une salle ou un enseignant."

        return {
            'response': response,
            'intent': 'availability',
            'confidence': 75,
            'context_data': {},
            'attachments': []
        }

    def _handle_statistics_query(self, message, user):
        """Gère les questions statistiques"""
        from django.db.models import Count

        # Compter les différentes entités
        course_count = Course.objects.count()
        room_count = Room.objects.filter(is_active=True).count()
        teacher_count = Teacher.objects.filter(is_active=True).count()

        today = timezone.now().date()
        session_count = ScheduleSession.objects.filter(specific_date=today).count()

        response = "Statistiques du systeme OAPET :\n\n"
        response += f"- Cours : {course_count} cours disponibles\n"
        response += f"- Salles : {room_count} salles actives\n"
        response += f"- Enseignants : {teacher_count} enseignants actifs\n"
        response += f"- Sessions aujourd'hui : {session_count} sessions\n"

        return {
            'response': response,
            'intent': 'statistics',
            'confidence': 90,
            'context_data': {
                'courses': course_count,
                'rooms': room_count,
                'teachers': teacher_count,
                'sessions': session_count
            },
            'attachments': []
        }

    def _find_next_session(self, user):
        """Trouve la prochaine session pour l'utilisateur"""
        now = timezone.now()
        next_session = ScheduleSession.objects.filter(
            specific_date__gte=now.date(),
            specific_start_time__gte=now.time() if now.date() == now.date() else None
        ).select_related('course', 'room', 'teacher').order_by('specific_date', 'specific_start_time').first()

        if next_session:
            start = next_session.specific_start_time or (next_session.time_slot.start_time if next_session.time_slot else "N/A")
            response = f"Votre prochain cours est :\n\n"
            response += f"- {next_session.course.name}\n"
            response += f"- Date : {next_session.specific_date.strftime('%d/%m/%Y')}\n"
            response += f"- Heure : {start}\n"
            response += f"- Salle : {next_session.room.name if next_session.room else 'N/A'}\n"
            if next_session.teacher:
                response += f"- Enseignant : {next_session.teacher.user.get_full_name()}\n"
        else:
            response = "Aucun cours programme pour le moment."

        return {
            'response': response,
            'intent': 'schedule',
            'confidence': 90,
            'context_data': {},
            'attachments': []
        }

    def _handle_create_action(self, message, user):
        """Guide l'utilisateur pour créer de nouvelles entités"""
        message_lower = message.lower()

        if 'cours' in message_lower:
            entity = "cours"
            steps = ["nom du cours", "code", "nombre de credits", "heures par semaine"]
        elif 'salle' in message_lower:
            entity = "salle"
            steps = ["nom de la salle", "batiment", "capacite"]
        elif 'enseignant' in message_lower:
            entity = "enseignant"
            steps = ["nom", "prenom", "email", "departement"]
        else:
            entity = "entite"
            steps = []

        response = f"Pour creer un nouveau/nouvelle {entity}, vous devez fournir :\n\n"
        for i, step in enumerate(steps, 1):
            response += f"{i}. {step}\n"
        response += f"\nVeuillez utiliser le formulaire correspondant dans l'interface pour creer un {entity}."

        return {
            'response': response,
            'intent': 'create',
            'confidence': 85,
            'context_data': {'entity': entity},
            'attachments': []
        }

    def _handle_modify_action(self, message, user):
        """Guide pour modifier des entités"""
        response = "Pour modifier des informations :\n\n"
        response += "- Utilisez le tableau de bord\n"
        response += "- Cliquez sur l'element a modifier\n"
        response += "- Apportez vos changements\n"
        response += "- Sauvegardez\n\n"
        response += "Que souhaitez-vous modifier ?"

        return {
            'response': response,
            'intent': 'modify',
            'confidence': 80,
            'context_data': {},
            'attachments': []
        }

    def _handle_delete_action(self, message, user):
        """Guide pour supprimer des entités"""
        response = "Attention ! La suppression est irreversible.\n\n"
        response += "Pour supprimer un element :\n"
        response += "- Allez dans la section correspondante\n"
        response += "- Selectionnez l'element\n"
        response += "- Cliquez sur supprimer\n"
        response += "- Confirmez l'action\n\n"
        response += "Assurez-vous que l'element n'est pas utilise ailleurs avant de le supprimer."

        return {
            'response': response,
            'intent': 'delete',
            'confidence': 80,
            'context_data': {},
            'attachments': []
        }

    def _handle_search_query(self, message, user):
        """Recherche avancée multi-entités"""
        message_lower = message.lower()
        words = [w for w in message_lower.split() if len(w) > 3]

        results = {
            'cours': [],
            'salles': [],
            'enseignants': []
        }

        for word in words:
            # Recherche cours
            courses = Course.objects.filter(
                Q(name__icontains=word) | Q(code__icontains=word)
            )[:3]
            results['cours'].extend(courses)

            # Recherche salles
            rooms = Room.objects.filter(
                Q(name__icontains=word) | Q(building__icontains=word)
            )[:3]
            results['salles'].extend(rooms)

            # Recherche enseignants
            teachers = Teacher.objects.filter(
                Q(user__first_name__icontains=word) | Q(user__last_name__icontains=word)
            )[:3]
            results['enseignants'].extend(teachers)

        response = "Resultats de recherche :\n\n"

        if results['cours']:
            response += "Cours trouves :\n"
            for c in results['cours'][:3]:
                response += f"- {c.name} ({c.code})\n"
            response += "\n"

        if results['salles']:
            response += "Salles trouvees :\n"
            for r in results['salles'][:3]:
                response += f"- {r.name} ({r.building})\n"
            response += "\n"

        if results['enseignants']:
            response += "Enseignants trouves :\n"
            for t in results['enseignants'][:3]:
                response += f"- {t.user.get_full_name()}\n"

        if not any(results.values()):
            response = "Aucun resultat trouve pour votre recherche."

        return {
            'response': response,
            'intent': 'search',
            'confidence': 85,
            'context_data': results,
            'attachments': []
        }

    def _handle_recommendation(self, message, user):
        """Fournit des recommandations intelligentes"""
        # Analyser les conflits existants
        from schedules.models import ScheduleSession
        today = timezone.now().date()
        sessions = ScheduleSession.objects.filter(specific_date__gte=today)[:20]

        response = "Recommandations intelligentes :\n\n"
        response += "1. Optimisation des horaires :\n"
        response += "   - Evitez les cours tardifs le vendredi\n"
        response += "   - Privilegiez les matins pour les cours theoriques\n\n"
        response += "2. Gestion des salles :\n"
        response += "   - Groupez les cours par batiment\n"
        response += "   - Reservez les grandes salles pour les CM\n\n"
        response += "3. Charge de travail :\n"
        response += "   - Maximum 6h de cours par jour\n"
        response += "   - Pause dejeuner de 1h minimum\n"

        return {
            'response': response,
            'intent': 'recommendation',
            'confidence': 75,
            'context_data': {},
            'attachments': []
        }

    def _handle_export_request(self, message, user):
        """Guide pour exporter des données"""
        response = "Export de donnees :\n\n"
        response += "Formats disponibles :\n"
        response += "- CSV : Pour Excel et tableurs\n"
        response += "- JSON : Pour integration technique\n"
        response += "- PDF : Pour impression\n\n"
        response += "Dans chaque section, utilisez le bouton 'Exporter' pour telecharger les donnees.\n\n"
        response += "Que souhaitez-vous exporter ?"

        return {
            'response': response,
            'intent': 'export',
            'confidence': 85,
            'context_data': {'formats': ['csv', 'json', 'pdf']},
            'attachments': []
        }

    def _get_suggested_questions(self):
        """Retourne des suggestions de questions frequentes"""
        return [
            "Quel est mon emploi du temps aujourd'hui ?",
            "Quels cours sont disponibles ?",
            "Ou se trouve la salle A101 ?",
            "Quand est mon prochain cours ?",
            "Y a-t-il des conflits d'horaire ?",
            "Combien de cours y a-t-il ?",
            "Cherche le cours de mathematiques",
            "Suggere-moi un meilleur horaire",
            "Comment exporter mon emploi du temps ?",
        ]
