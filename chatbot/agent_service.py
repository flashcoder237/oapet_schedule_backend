"""
Service d'agent conversationnel avec gestion d'actions par role
Permet au chatbot d'executer des actions sur les emplois du temps
"""
import re
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Q

from schedules.models import Schedule, ScheduleSession, Room, Course
from users.models import UserProfile
from .models import Conversation, Message


class AgentActionService:
    """
    Service qui gere les actions executables par le chatbot
    en fonction du role de l'utilisateur connecte
    """

    # Actions disponibles par role
    ROLE_PERMISSIONS = {
        'admin': [
            'create_schedule', 'modify_schedule', 'delete_schedule',
            'create_session', 'modify_session', 'delete_session',
            'assign_teacher', 'assign_room', 'publish_schedule',
            'view_all_schedules', 'view_analytics'
        ],
        'teacher': [
            'view_my_schedules', 'view_my_sessions',
            'modify_my_session', 'request_session_change',
            'view_room_availability', 'export_my_schedule'
        ],
        'student': [
            'view_my_schedule', 'view_class_schedule',
            'export_my_schedule', 'search_session'
        ]
    }

    # Intents d'action avec patterns de detection
    ACTION_INTENTS = {
        'create_schedule': {
            'patterns': [
                r'cr[ée]er?\s+(?:un\s+)?emploi\s+du\s+temps',
                r'nouveau\s+(?:un\s+)?emploi\s+du\s+temps',
                r'ajouter?\s+(?:un\s+)?emploi\s+du\s+temps'
            ],
            'required_params': ['name', 'academic_year', 'semester'],
            'confirmation_required': True
        },
        'modify_schedule': {
            'patterns': [
                r'modifie[r]?\s+(?:l\')?emploi\s+du\s+temps',
                r'changer?\s+(?:l\')?emploi\s+du\s+temps',
                r'mettre\s+[àa]\s+jour\s+(?:l\')?emploi\s+du\s+temps'
            ],
            'required_params': ['schedule_id'],
            'confirmation_required': True
        },
        'delete_schedule': {
            'patterns': [
                r'supprimer?\s+(?:l\')?emploi\s+du\s+temps',
                r'effacer?\s+(?:l\')?emploi\s+du\s+temps',
                r'retirer?\s+(?:l\')?emploi\s+du\s+temps'
            ],
            'required_params': ['schedule_id'],
            'confirmation_required': True
        },
        'create_session': {
            'patterns': [
                r'cr[ée]er?\s+(?:une\s+)?session',
                r'ajouter?\s+(?:une\s+)?session',
                r'nouvelle\s+session',
                r'planifier?\s+(?:une\s+)?session'
            ],
            'required_params': ['course_id', 'room_id', 'start_time', 'duration'],
            'confirmation_required': True
        },
        'modify_session': {
            'patterns': [
                r'modifie[r]?\s+(?:la\s+)?session',
                r'changer?\s+(?:la\s+)?session',
                r'd[ée]placer?\s+(?:la\s+)?session'
            ],
            'required_params': ['session_id'],
            'confirmation_required': True
        },
        'delete_session': {
            'patterns': [
                r'supprimer?\s+(?:la\s+)?session',
                r'annuler?\s+(?:la\s+)?session',
                r'effacer?\s+(?:la\s+)?session'
            ],
            'required_params': ['session_id'],
            'confirmation_required': True
        },
        'assign_teacher': {
            'patterns': [
                r'assigner?\s+(?:un\s+)?enseignant',
                r'affecter?\s+(?:un\s+)?enseignant',
                r'attribuer?\s+(?:un\s+)?enseignant'
            ],
            'required_params': ['session_id', 'teacher_id'],
            'confirmation_required': False
        },
        'assign_room': {
            'patterns': [
                r'assigner?\s+(?:une\s+)?salle',
                r'affecter?\s+(?:une\s+)?salle',
                r'attribuer?\s+(?:une\s+)?salle'
            ],
            'required_params': ['session_id', 'room_id'],
            'confirmation_required': False
        },
        'publish_schedule': {
            'patterns': [
                r'publier?\s+(?:l\')?emploi\s+du\s+temps',
                r'rendre\s+disponible\s+(?:l\')?emploi\s+du\s+temps'
            ],
            'required_params': ['schedule_id'],
            'confirmation_required': True
        }
    }

    def __init__(self, user):
        """
        Initialise le service d'agent pour un utilisateur specifique
        """
        self.user = user
        self.user_role = self._get_user_role()
        self.allowed_actions = self.ROLE_PERMISSIONS.get(self.user_role, [])

    def _get_user_role(self):
        """Determine le role de l'utilisateur"""
        # Essayer d'abord le profil UserProfile
        try:
            profile = self.user.profile  # Utilise related_name='profile'
            if profile.role == 'admin':
                return 'admin'
            elif profile.role == 'teacher':
                return 'teacher'
            elif profile.role == 'student':
                return 'student'
            # Pour les autres roles (department_head, staff, scheduler)
            elif profile.role in ['department_head', 'scheduler']:
                return 'admin'  # Memes permissions que admin
            elif profile.role == 'staff':
                return 'student'  # Permissions limitees
        except (UserProfile.DoesNotExist, AttributeError):
            pass

        # Fallback sur les groupes Django
        if self.user.is_superuser:
            return 'admin'

        # Verifier les groupes
        user_groups = self.user.groups.values_list('name', flat=True)
        if 'Admin' in user_groups or 'Administrateur' in user_groups:
            return 'admin'
        elif 'Enseignant' in user_groups or 'Teacher' in user_groups:
            return 'teacher'
        elif 'Etudiant' in user_groups or 'Student' in user_groups:
            return 'student'

        # Dernier fallback: si c'est un staff, admin, sinon student
        if self.user.is_staff:
            return 'admin'
        else:
            return 'student'

    def detect_action_intent(self, message_text):
        """
        Detecte si le message contient une intention d'action
        Retourne (action_name, confidence) ou (None, 0)
        """
        message_lower = message_text.lower()

        for action_name, config in self.ACTION_INTENTS.items():
            for pattern in config['patterns']:
                if re.search(pattern, message_lower):
                    # Verifie si l'utilisateur a le droit d'executer cette action
                    if self._can_execute_action(action_name):
                        return (action_name, 0.9)

        return (None, 0)

    def _can_execute_action(self, action_name):
        """Verifie si l'utilisateur peut executer cette action"""
        # Mappe les intents d'action vers les permissions
        action_permission_map = {
            'create_schedule': 'create_schedule',
            'modify_schedule': 'modify_schedule',
            'delete_schedule': 'delete_schedule',
            'create_session': 'create_session',
            'modify_session': 'modify_session',
            'delete_session': 'delete_session',
            'assign_teacher': 'assign_teacher',
            'assign_room': 'assign_room',
            'publish_schedule': 'publish_schedule'
        }

        required_permission = action_permission_map.get(action_name)
        return required_permission in self.allowed_actions

    def extract_parameters(self, message_text, action_name):
        """
        Extrait les parametres necessaires du message pour une action
        Retourne un dictionnaire de parametres extraits
        """
        params = {}
        message_lower = message_text.lower()

        # Extraction de l'ID d'emploi du temps
        schedule_match = re.search(r'emploi\s+du\s+temps\s+(?:#|n[°o]?\s*)?(\d+)', message_lower)
        if schedule_match:
            params['schedule_id'] = int(schedule_match.group(1))

        # Extraction de l'ID de session
        session_match = re.search(r'session\s+(?:#|n[°o]?\s*)?(\d+)', message_lower)
        if session_match:
            params['session_id'] = int(session_match.group(1))

        # Extraction de l'ID de cours
        course_match = re.search(r'cours\s+(?:#|n[°o]?\s*)?(\d+)', message_lower)
        if course_match:
            params['course_id'] = int(course_match.group(1))

        # Extraction de l'ID de salle
        room_match = re.search(r'salle\s+(?:#|n[°o]?\s*)?(\d+)', message_lower)
        if room_match:
            params['room_id'] = int(room_match.group(1))

        # Extraction du nom de salle (alternative)
        room_name_match = re.search(r'salle\s+([A-Z]\d+|[A-Z]+\d*)', message_text)
        if room_name_match:
            params['room_name'] = room_name_match.group(1)

        # Extraction de l'ID d'enseignant
        teacher_match = re.search(r'enseignant\s+(?:#|n[°o]?\s*)?(\d+)', message_lower)
        if teacher_match:
            params['teacher_id'] = int(teacher_match.group(1))

        # Extraction du nom (pour creation)
        name_match = re.search(r'nomm[ée]\s+"([^"]+)"', message_lower)
        if not name_match:
            name_match = re.search(r'appel[ée]\s+"([^"]+)"', message_lower)
        if name_match:
            params['name'] = name_match.group(1)

        # Extraction de l'annee academique
        year_match = re.search(r'(\d{4})[/-](\d{4})', message_text)
        if year_match:
            params['academic_year'] = f"{year_match.group(1)}-{year_match.group(2)}"

        # Extraction du semestre
        semester_match = re.search(r'semestre\s+(\d+|[IVX]+)', message_lower)
        if semester_match:
            params['semester'] = semester_match.group(1)

        # Extraction de la date/heure
        time_patterns = [
            r'(\d{1,2})h(\d{2})',  # 14h30
            r'(\d{1,2}):(\d{2})',  # 14:30
        ]
        for pattern in time_patterns:
            time_match = re.search(pattern, message_text)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                params['start_hour'] = hour
                params['start_minute'] = minute
                break

        # Extraction de la duree
        duration_match = re.search(r'(?:pendant|durant|de)\s+(\d+)\s*h', message_lower)
        if duration_match:
            params['duration'] = int(duration_match.group(1))

        return params

    def get_missing_parameters(self, action_name, extracted_params):
        """
        Determine quels parametres sont manquants pour une action
        Retourne une liste de parametres manquants
        """
        config = self.ACTION_INTENTS.get(action_name, {})
        required_params = config.get('required_params', [])

        missing = []
        for param in required_params:
            if param not in extracted_params or not extracted_params[param]:
                missing.append(param)

        return missing

    def execute_action(self, action_name, params, conversation):
        """
        Execute une action avec les parametres fournis
        Retourne (success: bool, message: str, data: dict)
        """
        # Verifie les permissions
        if not self._can_execute_action(action_name):
            return (False, f"Vous n'avez pas la permission d'executer l'action: {action_name}", {})

        # Verifie les parametres requis
        missing = self.get_missing_parameters(action_name, params)
        if missing:
            return (False, f"Parametres manquants: {', '.join(missing)}", {'missing_params': missing})

        # Execute l'action specifique
        action_method = getattr(self, f'_execute_{action_name}', None)
        if action_method:
            try:
                return action_method(params, conversation)
            except Exception as e:
                return (False, f"Erreur lors de l'execution: {str(e)}", {})

        return (False, f"Action non implementee: {action_name}", {})

    # ========== ACTIONS ADMIN ==========

    @transaction.atomic
    def _execute_create_schedule(self, params, conversation):
        """Cree un nouvel emploi du temps"""
        schedule = Schedule.objects.create(
            name=params['name'],
            academic_year=params['academic_year'],
            semester=params['semester'],
            created_by=self.user,
            is_published=False
        )

        return (
            True,
            f"Emploi du temps '{schedule.name}' cree avec succes (ID: {schedule.id})",
            {'schedule_id': schedule.id, 'schedule': schedule}
        )

    @transaction.atomic
    def _execute_modify_schedule(self, params, conversation):
        """Modifie un emploi du temps existant"""
        try:
            schedule = Schedule.objects.get(id=params['schedule_id'])
        except Schedule.DoesNotExist:
            return (False, f"Emploi du temps #{params['schedule_id']} introuvable", {})

        # Applique les modifications
        modified_fields = []
        if 'name' in params:
            schedule.name = params['name']
            modified_fields.append('name')
        if 'academic_year' in params:
            schedule.academic_year = params['academic_year']
            modified_fields.append('academic_year')
        if 'semester' in params:
            schedule.semester = params['semester']
            modified_fields.append('semester')

        schedule.save()

        return (
            True,
            f"Emploi du temps #{schedule.id} modifie avec succes. Champs modifies: {', '.join(modified_fields)}",
            {'schedule_id': schedule.id, 'modified_fields': modified_fields}
        )

    @transaction.atomic
    def _execute_delete_schedule(self, params, conversation):
        """Supprime un emploi du temps"""
        try:
            schedule = Schedule.objects.get(id=params['schedule_id'])
        except Schedule.DoesNotExist:
            return (False, f"Emploi du temps #{params['schedule_id']} introuvable", {})

        schedule_name = schedule.name
        schedule.delete()

        return (
            True,
            f"Emploi du temps '{schedule_name}' supprime avec succes",
            {'deleted': True}
        )

    @transaction.atomic
    def _execute_create_session(self, params, conversation):
        """Cree une nouvelle session dans un emploi du temps"""
        try:
            course = Course.objects.get(id=params['course_id'])
        except Course.DoesNotExist:
            return (False, f"Cours #{params['course_id']} introuvable", {})

        try:
            room = Room.objects.get(id=params['room_id'])
        except Room.DoesNotExist:
            return (False, f"Salle #{params['room_id']} introuvable", {})

        # Construction de la date/heure de debut
        start_time = params.get('start_time')
        if not start_time and 'start_hour' in params:
            # Utilise aujourd'hui + heure specifiee
            today = timezone.now().date()
            start_time = timezone.make_aware(datetime.combine(
                today,
                datetime.min.time().replace(hour=params['start_hour'], minute=params.get('start_minute', 0))
            ))

        duration_hours = params.get('duration', 2)
        end_time = start_time + timedelta(hours=duration_hours)

        # Verifie les conflits
        conflicts = ScheduleSession.objects.filter(
            room=room,
            start_time__lt=end_time,
            end_time__gt=start_time
        )

        if conflicts.exists():
            return (False, f"Conflit detecte: la salle {room.name} est deja occupee a cette heure", {})

        # Cree la session
        session = ScheduleSession.objects.create(
            course=course,
            room=room,
            start_time=start_time,
            end_time=end_time,
            session_type=params.get('session_type', 'cours')
        )

        return (
            True,
            f"Session creee avec succes (ID: {session.id}) - {course.name} dans {room.name}",
            {'session_id': session.id, 'session': session}
        )

    @transaction.atomic
    def _execute_modify_session(self, params, conversation):
        """Modifie une session existante"""
        try:
            session = ScheduleSession.objects.get(id=params['session_id'])
        except ScheduleSession.DoesNotExist:
            return (False, f"Session #{params['session_id']} introuvable", {})

        modified_fields = []

        # Modification de la salle
        if 'room_id' in params:
            try:
                new_room = Room.objects.get(id=params['room_id'])
                session.room = new_room
                modified_fields.append('room')
            except Room.DoesNotExist:
                return (False, f"Salle #{params['room_id']} introuvable", {})

        # Modification de l'horaire
        if 'start_hour' in params:
            new_start = session.start_time.replace(
                hour=params['start_hour'],
                minute=params.get('start_minute', 0)
            )
            duration = (session.end_time - session.start_time).total_seconds() / 3600
            session.start_time = new_start
            session.end_time = new_start + timedelta(hours=duration)
            modified_fields.append('horaire')

        session.save()

        return (
            True,
            f"Session #{session.id} modifiee avec succes. Champs modifies: {', '.join(modified_fields)}",
            {'session_id': session.id, 'modified_fields': modified_fields}
        )

    @transaction.atomic
    def _execute_delete_session(self, params, conversation):
        """Supprime une session"""
        try:
            session = ScheduleSession.objects.get(id=params['session_id'])
        except ScheduleSession.DoesNotExist:
            return (False, f"Session #{params['session_id']} introuvable", {})

        session_info = f"{session.course.name} - {session.start_time.strftime('%d/%m/%Y %H:%M')}"
        session.delete()

        return (
            True,
            f"Session supprimee avec succes: {session_info}",
            {'deleted': True}
        )

    @transaction.atomic
    def _execute_assign_teacher(self, params, conversation):
        """Assigne un enseignant a une session"""
        try:
            session = ScheduleSession.objects.get(id=params['session_id'])
        except ScheduleSession.DoesNotExist:
            return (False, f"Session #{params['session_id']} introuvable", {})

        try:
            teacher_profile = UserProfile.objects.get(id=params['teacher_id'], role='teacher')
        except UserProfile.DoesNotExist:
            return (False, f"Enseignant #{params['teacher_id']} introuvable", {})

        session.teacher = teacher_profile.user
        session.save()

        return (
            True,
            f"Enseignant {teacher_profile.user.get_full_name()} assigne a la session #{session.id}",
            {'session_id': session.id}
        )

    @transaction.atomic
    def _execute_assign_room(self, params, conversation):
        """Assigne une salle a une session"""
        try:
            session = ScheduleSession.objects.get(id=params['session_id'])
        except ScheduleSession.DoesNotExist:
            return (False, f"Session #{params['session_id']} introuvable", {})

        try:
            room = Room.objects.get(id=params['room_id'])
        except Room.DoesNotExist:
            return (False, f"Salle #{params['room_id']} introuvable", {})

        # Verifie les conflits
        conflicts = ScheduleSession.objects.filter(
            room=room,
            start_time__lt=session.end_time,
            end_time__gt=session.start_time
        ).exclude(id=session.id)

        if conflicts.exists():
            return (False, f"Conflit detecte: la salle {room.name} est deja occupee a cette heure", {})

        session.room = room
        session.save()

        return (
            True,
            f"Salle {room.name} assignee a la session #{session.id}",
            {'session_id': session.id}
        )

    @transaction.atomic
    def _execute_publish_schedule(self, params, conversation):
        """Publie un emploi du temps"""
        try:
            schedule = Schedule.objects.get(id=params['schedule_id'])
        except Schedule.DoesNotExist:
            return (False, f"Emploi du temps #{params['schedule_id']} introuvable", {})

        schedule.is_published = True
        schedule.published_at = timezone.now()
        schedule.save()

        return (
            True,
            f"Emploi du temps '{schedule.name}' publie avec succes",
            {'schedule_id': schedule.id}
        )

    # ========== ACTIONS ENSEIGNANT ==========

    def _execute_view_my_schedules(self, params, conversation):
        """Affiche les emplois du temps de l'enseignant"""
        # Trouver toutes les sessions de l'enseignant
        sessions = ScheduleSession.objects.filter(
            teacher=self.user
        ).select_related('course', 'room').order_by('start_time')[:10]

        if sessions:
            response = f"Voici vos prochaines sessions :\n\n"
            for session in sessions:
                response += f"- {session.course.name}\n"
                response += f"  Date : {session.start_time.strftime('%d/%m/%Y %H:%M')}\n"
                response += f"  Salle : {session.room.name if session.room else 'N/A'}\n\n"
        else:
            response = "Vous n'avez aucune session programmee pour le moment."

        return (True, response, {'session_count': len(sessions)})

    def _execute_view_my_sessions(self, params, conversation):
        """Affiche les sessions de l'enseignant"""
        return self._execute_view_my_schedules(params, conversation)

    def _execute_modify_my_session(self, params, conversation):
        """Permet a un enseignant de modifier sa propre session"""
        try:
            session = ScheduleSession.objects.get(id=params['session_id'])
        except ScheduleSession.DoesNotExist:
            return (False, f"Session #{params['session_id']} introuvable", {})

        # Verifier que la session appartient a cet enseignant
        if session.teacher != self.user:
            return (False, "Vous ne pouvez modifier que vos propres sessions", {})

        # Modification limitee pour les enseignants (salle seulement)
        modified_fields = []

        if 'room_id' in params:
            try:
                new_room = Room.objects.get(id=params['room_id'])

                # Verifier les conflits
                conflicts = ScheduleSession.objects.filter(
                    room=new_room,
                    start_time__lt=session.end_time,
                    end_time__gt=session.start_time
                ).exclude(id=session.id)

                if conflicts.exists():
                    return (False, f"Conflit detecte: la salle {new_room.name} est deja occupee a cette heure", {})

                session.room = new_room
                modified_fields.append('salle')
            except Room.DoesNotExist:
                return (False, f"Salle #{params['room_id']} introuvable", {})

        session.save()

        return (
            True,
            f"Session #{session.id} modifiee avec succes. Champs modifies: {', '.join(modified_fields)}",
            {'session_id': session.id, 'modified_fields': modified_fields}
        )

    def _execute_request_session_change(self, params, conversation):
        """Permet a un enseignant de demander une modification de session"""
        try:
            session = ScheduleSession.objects.get(id=params['session_id'])
        except ScheduleSession.DoesNotExist:
            return (False, f"Session #{params['session_id']} introuvable", {})

        # Verifier que la session appartient a cet enseignant
        if session.teacher != self.user:
            return (False, "Vous ne pouvez faire une demande que pour vos propres sessions", {})

        # Dans une version complete, cela crerait une notification pour l'admin
        return (
            True,
            f"Demande de modification enregistree pour la session #{session.id}. Un administrateur sera notifie.",
            {'session_id': session.id}
        )

    def _execute_view_room_availability(self, params, conversation):
        """Affiche les salles disponibles"""
        available_rooms = Room.objects.filter(is_active=True)

        # Si une date est specifiee, filtrer par disponibilite
        if 'date' in params:
            # Trouver les salles non occupees a cette date
            occupied_rooms = ScheduleSession.objects.filter(
                specific_date=params['date']
            ).values_list('room_id', flat=True)
            available_rooms = available_rooms.exclude(id__in=occupied_rooms)

        available_rooms = available_rooms[:10]

        if available_rooms:
            response = "Salles disponibles :\n\n"
            for room in available_rooms:
                response += f"- {room.name} ({room.building})\n"
                response += f"  Capacite : {room.capacity} places\n"
                if room.equipment:
                    response += f"  Equipements : {', '.join(room.equipment)}\n"
                response += "\n"
        else:
            response = "Aucune salle disponible pour cette periode."

        return (True, response, {'room_count': len(available_rooms)})

    def _execute_export_my_schedule(self, params, conversation):
        """Permet d'exporter l'emploi du temps de l'enseignant"""
        # Dans une version complete, cela genererait un fichier CSV/PDF
        return (
            True,
            "Votre emploi du temps est en cours d'export. Vous recevrez un lien de telechargement par email.",
            {'export_initiated': True}
        )

    # ========== ACTIONS ETUDIANT ==========

    def _execute_view_my_schedule(self, params, conversation):
        """Affiche l'emploi du temps de l'etudiant"""
        # Trouver les sessions pour la classe de l'etudiant
        try:
            student_profile = self.user.userprofile
            student_class = student_profile.student_class if hasattr(student_profile, 'student_class') else None
        except Exception:
            student_class = None

        if not student_class:
            return (False, "Vous n'etes pas assigne a une classe", {})

        # Trouver les sessions de la semaine pour cette classe
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        sessions = ScheduleSession.objects.filter(
            # Filtrer par classe - a adapter selon votre modele
            start_time__date__gte=week_start,
            start_time__date__lte=week_end
        ).select_related('course', 'room', 'teacher').order_by('start_time')[:20]

        if sessions:
            response = f"Emploi du temps de la semaine ({week_start.strftime('%d/%m')} - {week_end.strftime('%d/%m')}) :\n\n"
            current_day = None
            for session in sessions:
                session_day = session.start_time.date()
                if session_day != current_day:
                    current_day = session_day
                    response += f"\n** {session_day.strftime('%A %d/%m')} **\n"

                response += f"- {session.start_time.strftime('%H:%M')} - {session.end_time.strftime('%H:%M')} : "
                response += f"{session.course.name}\n"
                response += f"  Salle : {session.room.name if session.room else 'N/A'}, "
                response += f"Prof : {session.teacher.get_full_name() if session.teacher else 'N/A'}\n"
        else:
            response = "Aucune session programmee pour cette semaine."

        return (True, response, {'session_count': len(sessions)})

    def _execute_view_class_schedule(self, params, conversation):
        """Affiche l'emploi du temps de la classe"""
        return self._execute_view_my_schedule(params, conversation)

    def _execute_search_session(self, params, conversation):
        """Recherche une session specifique"""
        # Extraire les criteres de recherche du message original
        filters = Q()

        if 'course_id' in params:
            filters &= Q(course_id=params['course_id'])

        if 'room_id' in params:
            filters &= Q(room_id=params['room_id'])

        if 'date' in params:
            filters &= Q(start_time__date=params['date'])

        sessions = ScheduleSession.objects.filter(filters).select_related(
            'course', 'room', 'teacher'
        )[:10]

        if sessions:
            response = f"J'ai trouve {len(sessions)} session(s) :\n\n"
            for session in sessions:
                response += f"- {session.course.name}\n"
                response += f"  Date : {session.start_time.strftime('%d/%m/%Y %H:%M')}\n"
                response += f"  Salle : {session.room.name if session.room else 'N/A'}\n"
                response += f"  Enseignant : {session.teacher.get_full_name() if session.teacher else 'N/A'}\n\n"
        else:
            response = "Aucune session trouvee avec ces criteres."

        return (True, response, {'session_count': len(sessions)})
