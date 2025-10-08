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
    """Service principal du chatbot"""

    def __init__(self):
        self.intents = {
            'schedule': {
                'keywords': ['emploi', 'planning', 'horaire', 'programme', 'cours', 'session', 'quand', 'aujourd\'hui', 'demain', 'semaine'],
                'patterns': [
                    r'emploi.*temps',
                    r'(mon|mes)\s+cours',
                    r'quand.*cours',
                    r'planning.*(?:jour|semaine|mois)',
                ]
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
        """Traite le message et génère une réponse"""
        intent, confidence = self.detect_intent(message)

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

        # Traiter selon l'intention
        if intent == 'greeting':
            return self._handle_greeting(user)
        elif intent == 'thanks':
            return self._handle_thanks(user)
        elif intent == 'schedule':
            return self._handle_schedule_query(message, user)
        elif intent == 'course':
            return self._handle_course_query(message, user)
        elif intent == 'room':
            return self._handle_room_query(message, user)
        elif intent == 'teacher':
            return self._handle_teacher_query(message, user)
        elif intent == 'conflict':
            return self._handle_conflict_query(message, user)
        elif intent == 'availability':
            return self._handle_availability_query(message, user)
        elif intent == 'statistics':
            return self._handle_statistics_query(message, user)
        elif intent == 'help':
            return self._handle_help()
        else:
            return self._handle_unknown()

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

    def _handle_schedule_query(self, message, user):
        """Gère les questions sur les emplois du temps"""
        # Chercher des dates dans le message
        today = timezone.now().date()

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

    def _handle_course_query(self, message, user):
        """Gère les questions sur les cours"""
        courses = Course.objects.all()[:5]

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

    def _get_suggested_questions(self):
        """Retourne des suggestions de questions frequentes"""
        return [
            "Quel est mon emploi du temps aujourd'hui ?",
            "Quels cours sont disponibles ?",
            "Ou se trouve la salle A101 ?",
            "Quand est mon prochain cours ?",
            "Y a-t-il des conflits d'horaire ?",
            "Combien de cours y a-t-il ?",
        ]
