# chatbot/occurrence_service.py
"""
Extension du chatbot pour gérer le système d'occurrences dynamiques
"""
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q, Count
from schedules.models import SessionOccurrence, ScheduleGenerationConfig


class OccurrenceChatbotService:
    """Extension du chatbot pour les occurrences de sessions"""

    def handle_schedule_query_with_occurrences(self, message, user, context=None):
        """Gère les questions sur les emplois du temps avec le système d'occurrences"""
        today = timezone.now().date()
        message_lower = message.lower()

        # Détection intelligente de la période demandée
        target_date = today
        if 'demain' in message_lower:
            target_date = today + timedelta(days=1)
        elif 'hier' in message_lower:
            target_date = today - timedelta(days=1)
        elif any(word in message_lower for word in ['prochaine', 'prochain']):
            return self._find_next_occurrence(user)
        elif 'semaine' in message_lower:
            return self._get_week_schedule(user, today)

        # Récupérer les occurrences pour la date
        occurrences = SessionOccurrence.objects.filter(
            actual_date=target_date,
            status='scheduled'
        ).select_related(
            'session_template__course',
            'room',
            'teacher__user'
        ).order_by('start_time')[:10]

        if occurrences:
            response = f"Emploi du temps pour {target_date.strftime('%d/%m/%Y')} :\n\n"
            for occ in occurrences:
                response += f"🕐 {occ.start_time.strftime('%H:%M')} - {occ.end_time.strftime('%H:%M')}\n"
                response += f"   📚 {occ.session_template.course.name}\n"
                response += f"   📍 Salle: {occ.room.name}\n"
                response += f"   👨‍🏫 Prof: {occ.teacher.user.get_full_name()}\n"

                # Afficher si modifié
                if occ.is_room_modified or occ.is_teacher_modified or occ.is_time_modified:
                    response += f"   ⚠️ Séance modifiée\n"

                response += "\n"
        else:
            response = f"Aucune séance programmée pour le {target_date.strftime('%d/%m/%Y')}."

        return {
            'response': response,
            'intent': 'schedule',
            'confidence': 90,
            'context_data': {
                'date': str(target_date),
                'occurrence_count': len(occurrences)
            },
            'attachments': self._format_occurrences_attachment(occurrences)
        }

    def handle_cancellation_query(self, message, user):
        """Gère les questions sur les cours annulés"""
        today = timezone.now().date()
        next_week = today + timedelta(days=7)

        cancelled_occurrences = SessionOccurrence.objects.filter(
            actual_date__gte=today,
            actual_date__lte=next_week,
            is_cancelled=True
        ).select_related('session_template__course').order_by('actual_date')

        if cancelled_occurrences:
            response = "Cours annulés dans les 7 prochains jours :\n\n"
            for occ in cancelled_occurrences:
                response += f"📅 {occ.actual_date.strftime('%d/%m/%Y')} - {occ.start_time.strftime('%H:%M')}\n"
                response += f"   📚 {occ.session_template.course.name}\n"
                if occ.cancellation_reason:
                    response += f"   💬 Raison: {occ.cancellation_reason}\n"
                response += "\n"
        else:
            response = "Aucun cours annulé dans les 7 prochains jours."

        return {
            'response': response,
            'intent': 'schedule',
            'confidence': 95,
            'context_data': {'cancelled_count': len(cancelled_occurrences)},
            'attachments': []
        }

    def handle_modification_query(self, message, user):
        """Gère les questions sur les modifications d'emploi du temps"""
        today = timezone.now().date()
        next_week = today + timedelta(days=7)

        modified_occurrences = SessionOccurrence.objects.filter(
            actual_date__gte=today,
            actual_date__lte=next_week
        ).filter(
            Q(is_room_modified=True) |
            Q(is_teacher_modified=True) |
            Q(is_time_modified=True)
        ).select_related('session_template__course', 'room', 'teacher__user')

        if modified_occurrences:
            response = "Modifications d'emploi du temps cette semaine :\n\n"
            for occ in modified_occurrences:
                response += f"📅 {occ.actual_date.strftime('%d/%m/%Y')} - {occ.start_time.strftime('%H:%M')}\n"
                response += f"   📚 {occ.session_template.course.name}\n"

                if occ.is_room_modified:
                    response += f"   📍 Nouvelle salle: {occ.room.name}\n"
                if occ.is_teacher_modified:
                    response += f"   👨‍🏫 Nouvel enseignant: {occ.teacher.user.get_full_name()}\n"
                if occ.is_time_modified:
                    response += f"   🕐 Nouvel horaire: {occ.start_time.strftime('%H:%M')}\n"

                response += "\n"
        else:
            response = "Aucune modification d'emploi du temps cette semaine."

        return {
            'response': response,
            'intent': 'schedule',
            'confidence': 92,
            'context_data': {'modified_count': len(modified_occurrences)},
            'attachments': []
        }

    def handle_conflict_query_with_occurrences(self, message, user):
        """Gère les questions sur les conflits avec le système d'occurrences"""
        today = timezone.now().date()

        # Récupère les occurrences du jour
        occurrences = SessionOccurrence.objects.filter(
            actual_date=today,
            status='scheduled'
        ).select_related('session_template__course', 'room', 'teacher__user')

        # Détecte les conflits
        conflicts = []
        for occ in occurrences:
            occ_conflicts = occ.check_conflicts()
            if occ_conflicts:
                conflicts.extend([{
                    'occurrence': occ,
                    'conflict_details': conflict
                } for conflict in occ_conflicts])

        if conflicts:
            response = f"⚠️ {len(conflicts)} conflit(s) détecté(s) aujourd'hui :\n\n"
            for conf in conflicts[:5]:  # Limiter à 5
                occ = conf['occurrence']
                details = conf['conflict_details']

                response += f"📚 {occ.session_template.course.name}\n"
                response += f"🕐 {occ.start_time.strftime('%H:%M')} - {occ.end_time.strftime('%H:%M')}\n"
                response += f"⚠️ {details['description']}\n"
                response += f"🔴 Gravité: {details['severity']}\n\n"
        else:
            response = "✅ Aucun conflit détecté dans l'emploi du temps actuel."

        return {
            'response': response,
            'intent': 'conflict',
            'confidence': 95,
            'context_data': {'conflict_count': len(conflicts)},
            'attachments': []
        }

    def handle_generation_status_query(self, message, user):
        """Informe sur l'état de génération de l'emploi du temps"""
        # Cherche les configurations de génération actives
        active_configs = ScheduleGenerationConfig.objects.filter(
            is_active=True
        ).select_related('schedule')

        if not active_configs:
            response = "Aucune configuration de génération d'emploi du temps active."
            return {
                'response': response,
                'intent': 'schedule',
                'confidence': 85,
                'context_data': {},
                'attachments': []
            }

        config = active_configs.first()

        response = "📊 Configuration d'emploi du temps actuelle :\n\n"
        response += f"📅 Période: {config.start_date.strftime('%d/%m/%Y')} - {config.end_date.strftime('%d/%m/%Y')}\n"
        response += f"🔄 Récurrence: {config.get_recurrence_type_display()}\n"
        response += f"⚙️ Flexibilité: {config.get_flexibility_level_display()}\n"
        response += f"📈 Priorité d'optimisation: {config.get_optimization_priority_display()}\n"

        # Compte les occurrences générées
        total_occurrences = SessionOccurrence.objects.filter(
            session_template__schedule=config.schedule
        ).count()

        scheduled_count = SessionOccurrence.objects.filter(
            session_template__schedule=config.schedule,
            status='scheduled'
        ).count()

        completed_count = SessionOccurrence.objects.filter(
            session_template__schedule=config.schedule,
            status='completed'
        ).count()

        response += f"\n📊 Statistiques:\n"
        response += f"   Total de séances: {total_occurrences}\n"
        response += f"   Planifiées: {scheduled_count}\n"
        response += f"   Terminées: {completed_count}\n"

        if config.excluded_dates:
            response += f"\n🚫 Jours exclus: {len(config.excluded_dates)} jour(s)\n"

        if config.special_weeks:
            response += f"📌 Semaines spéciales: {len(config.special_weeks)}\n"

        return {
            'response': response,
            'intent': 'schedule',
            'confidence': 88,
            'context_data': {
                'total_occurrences': total_occurrences,
                'scheduled': scheduled_count,
                'completed': completed_count
            },
            'attachments': []
        }

    def _find_next_occurrence(self, user):
        """Trouve la prochaine occurrence pour l'utilisateur"""
        now = timezone.now()

        next_occurrence = SessionOccurrence.objects.filter(
            Q(actual_date__gt=now.date()) |
            Q(actual_date=now.date(), start_time__gt=now.time()),
            status='scheduled'
        ).select_related(
            'session_template__course',
            'room',
            'teacher__user'
        ).order_by('actual_date', 'start_time').first()

        if next_occurrence:
            response = "🎓 Votre prochain cours :\n\n"
            response += f"📚 {next_occurrence.session_template.course.name}\n"
            response += f"📅 {next_occurrence.actual_date.strftime('%d/%m/%Y')}\n"
            response += f"🕐 {next_occurrence.start_time.strftime('%H:%M')} - {next_occurrence.end_time.strftime('%H:%M')}\n"
            response += f"📍 Salle: {next_occurrence.room.name}\n"
            response += f"👨‍🏫 Enseignant: {next_occurrence.teacher.user.get_full_name()}\n"

            if next_occurrence.is_room_modified or next_occurrence.is_teacher_modified:
                response += f"\n⚠️ Attention: Séance modifiée\n"
        else:
            response = "Aucun cours programmé pour le moment."

        return {
            'response': response,
            'intent': 'schedule',
            'confidence': 95,
            'context_data': {},
            'attachments': []
        }

    def _get_week_schedule(self, user, start_date):
        """Récupère l'emploi du temps de la semaine"""
        week_start = start_date - timedelta(days=start_date.weekday())
        week_end = week_start + timedelta(days=6)

        occurrences = SessionOccurrence.objects.filter(
            actual_date__gte=week_start,
            actual_date__lte=week_end,
            status='scheduled'
        ).select_related(
            'session_template__course',
            'room',
            'teacher__user'
        ).order_by('actual_date', 'start_time')

        if occurrences:
            response = f"📅 Emploi du temps de la semaine ({week_start.strftime('%d/%m')} - {week_end.strftime('%d/%m')}) :\n\n"

            # Groupe par jour
            current_date = None
            for occ in occurrences:
                if occ.actual_date != current_date:
                    current_date = occ.actual_date
                    day_name = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'][current_date.weekday()]
                    response += f"\n{day_name} {current_date.strftime('%d/%m')}:\n"

                response += f"  🕐 {occ.start_time.strftime('%H:%M')} - {occ.session_template.course.name}\n"

            # Statistiques
            total_hours = sum(occ.get_duration_hours() for occ in occurrences)
            response += f"\n📊 Total: {len(occurrences)} séances, {total_hours:.1f}h de cours\n"
        else:
            response = "Aucune séance programmée cette semaine."

        return {
            'response': response,
            'intent': 'schedule',
            'confidence': 90,
            'context_data': {
                'week_start': str(week_start),
                'occurrence_count': len(occurrences)
            },
            'attachments': []
        }

    def _format_occurrences_attachment(self, occurrences):
        """Formate les occurrences pour les pièces jointes"""
        if not occurrences:
            return []

        attachment_data = []
        for occ in occurrences:
            attachment_data.append({
                'type': 'occurrence',
                'id': occ.id,
                'course_name': occ.session_template.course.name,
                'course_code': occ.session_template.course.code,
                'date': str(occ.actual_date),
                'start_time': str(occ.start_time),
                'end_time': str(occ.end_time),
                'room': occ.room.name,
                'teacher': occ.teacher.user.get_full_name(),
                'status': occ.status,
                'is_modified': any([occ.is_room_modified, occ.is_teacher_modified, occ.is_time_modified]),
                'is_cancelled': occ.is_cancelled
            })

        return [{'type': 'occurrences', 'data': attachment_data}]
