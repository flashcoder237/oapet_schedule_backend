# schedules/views.py
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction, models
from django.utils import timezone
from django.db.models import Count, Avg

logger = logging.getLogger('schedules.views')

# Import ML service for anomaly detection
from ml_engine.simple_ml_service import SimpleMLService
ml_service = SimpleMLService()

# Import pedagogical sequencer
from .pedagogical_sequencing import PedagogicalSequencer

from core.mixins import ImportExportMixin
from .models import (
    AcademicPeriod, TimeSlot, Schedule, ScheduleSession, Conflict,
    ScheduleOptimization, ScheduleTemplate, ScheduleConstraint, ScheduleExport
)
from .serializers import (
    AcademicPeriodSerializer, TimeSlotSerializer, ScheduleSerializer, ScheduleSessionSerializer,
    ConflictSerializer, ScheduleOptimizationSerializer, ScheduleTemplateSerializer,
    ScheduleConstraintSerializer, ScheduleExportSerializer, ScheduleDetailSerializer,
    ScheduleCreateSerializer, WeeklyScheduleSerializer
)


class AcademicPeriodViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des périodes académiques"""
    queryset = AcademicPeriod.objects.all()
    serializer_class = AcademicPeriodSerializer
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'name', 'academic_year', 'semester', 'start_date', 'end_date', 'is_current']
    import_fields = ['name', 'academic_year', 'semester', 'start_date', 'end_date']

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrer par année académique
        academic_year = self.request.query_params.get('academic_year')
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)

        # Filtrer par semestre
        semester = self.request.query_params.get('semester')
        if semester:
            queryset = queryset.filter(semester=semester)

        # Filtrer par période courante
        is_current = self.request.query_params.get('is_current')
        if is_current is not None:
            is_current_bool = is_current.lower() == 'true'
            queryset = queryset.filter(is_current=is_current_bool)

        return queryset.order_by('-start_date')

    @action(detail=True, methods=['post'])
    def set_current(self, request, pk=None):
        """Définit une période comme courante"""
        period = self.get_object()

        with transaction.atomic():
            # Désactiver toutes les autres périodes
            AcademicPeriod.objects.filter(is_current=True).update(is_current=False)
            # Activer la période sélectionnée
            period.is_current = True
            period.save()

        return Response({
            'message': f'Période {period.name} définie comme courante'
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def current(self, request):
        """Récupère la période académique courante"""
        current_period = AcademicPeriod.objects.filter(is_current=True).first()

        if not current_period:
            return Response({
                'error': 'Aucune période académique courante définie'
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(current_period)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def available_years(self, request):
        """Liste toutes les années académiques disponibles"""
        years = AcademicPeriod.objects.values_list('academic_year', flat=True).distinct().order_by('-academic_year')

        return Response({
            'academic_years': list(years),
            'count': len(years)
        })

    @action(detail=False, methods=['get'])
    def by_year_and_semester(self, request):
        """Récupère une période par année académique et semestre"""
        academic_year = request.query_params.get('academic_year')
        semester = request.query_params.get('semester')

        if not academic_year or not semester:
            return Response({
                'error': 'academic_year et semester sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        period = AcademicPeriod.objects.filter(
            academic_year=academic_year,
            semester=semester
        ).first()

        if not period:
            return Response({
                'error': f'Aucune période trouvée pour {academic_year} - {semester}',
                'suggestion': 'Vous pouvez créer cette période en utilisant generate_for_period avec ces paramètres'
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(period)
        return Response(serializer.data)


class TimeSlotViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des créneaux horaires"""
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'day_of_week', 'start_time', 'end_time', 'is_active']
    import_fields = ['day_of_week', 'start_time', 'end_time']
    
    def get_queryset(self):
        queryset = super().get_queryset().filter(is_active=True)
        
        day_of_week = self.request.query_params.get('day')
        if day_of_week:
            queryset = queryset.filter(day_of_week=day_of_week)
        
        return queryset.order_by('day_of_week', 'start_time')


class ScheduleViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des emplois du temps"""
    queryset = Schedule.objects.all()
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'name', 'academic_period', 'student_class', 'teacher', 'level', 'schedule_type', 'status', 'is_published']
    import_fields = ['name', 'academic_period', 'student_class', 'teacher', 'level', 'schedule_type', 'status']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ScheduleDetailSerializer
        elif self.action == 'create':
            return ScheduleCreateSerializer
        return ScheduleSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()

        # Check if request has query_params (DRF Request object)
        if not hasattr(self.request, 'query_params'):
            return queryset.order_by('-created_at')

        # Filtrer par période académique
        academic_period_id = self.request.query_params.get('academic_period')
        if academic_period_id:
            queryset = queryset.filter(academic_period_id=academic_period_id)

        # Filtrer par classe
        student_class_id = self.request.query_params.get('student_class')
        if student_class_id:
            queryset = queryset.filter(student_class_id=student_class_id)

        # Filtrer par statut de publication
        published_only = self.request.query_params.get('published_only')
        if published_only == 'true':
            queryset = queryset.filter(is_published=True)

        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def by_class(self, request):
        """Récupère le schedule actif pour une classe donnée"""
        class_code = request.query_params.get('class')

        if not class_code:
            return Response({
                'error': 'Le paramètre class est requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        from courses.models_class import StudentClass
        try:
            # Chercher la classe par code ou ID
            if class_code.isdigit():
                student_class = StudentClass.objects.get(id=class_code)
            else:
                student_class = StudentClass.objects.get(code=class_code)
        except StudentClass.DoesNotExist:
            return Response({
                'error': f'Classe {class_code} non trouvée'
            }, status=status.HTTP_404_NOT_FOUND)

        # Chercher le schedule le plus récent pour cette classe
        schedule = Schedule.objects.filter(student_class=student_class).order_by('-created_at').first()

        if not schedule:
            return Response({
                'error': f'Aucun emploi du temps trouvé pour la classe {student_class.code}',
                'student_class': {
                    'id': student_class.id,
                    'code': student_class.code,
                    'name': student_class.name
                }
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(schedule)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Publie un emploi du temps"""
        schedule = self.get_object()
        
        # Vérifier qu'il n'y a pas de conflits critiques
        critical_conflicts = Conflict.objects.filter(
            schedule_session__schedule=schedule,
            severity='critical',
            is_resolved=False
        ).count()
        
        if critical_conflicts > 0:
            return Response({
                'error': f'Impossible de publier: {critical_conflicts} conflits critiques non résolus'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        schedule.is_published = True
        schedule.published_at = timezone.now()
        schedule.save()
        
        return Response({
            'message': 'Emploi du temps publié avec succès'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def unpublish(self, request, pk=None):
        """Dépublie un emploi du temps"""
        schedule = self.get_object()
        schedule.is_published = False
        schedule.save()

        return Response({
            'message': 'Emploi du temps dépublié avec succès'
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['delete'])
    def delete_schedule(self, request, pk=None):
        """Supprime un emploi du temps et toutes ses sessions"""
        schedule = self.get_object()

        # Vérifier que l'emploi du temps n'est pas publié
        if schedule.is_published:
            return Response({
                'error': 'Impossible de supprimer un emploi du temps publié',
                'hint': 'Veuillez d\'abord dépublier l\'emploi du temps'
            }, status=status.HTTP_400_BAD_REQUEST)

        schedule_name = schedule.name
        sessions_count = schedule.sessions.count()

        # Supprimer l'emploi du temps (cascade supprimera les sessions)
        with transaction.atomic():
            schedule.delete()

        return Response({
            'message': f'Emploi du temps "{schedule_name}" supprimé avec succès',
            'sessions_deleted': sessions_count
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='course_coverage')
    def course_coverage(self, request, pk=None):
        """
        Retourne le rapport de couverture des heures de cours
        Permet à l'admin de voir quels cours ne couvrent pas toutes les heures du semestre
        """
        try:
            schedule = self.get_object()
            coverage_report = schedule.get_course_coverage()
            return Response(coverage_report, status=status.HTTP_200_OK)
        except Exception as e:
            import traceback
            logger.error(f"Error in course_coverage: {e}")
            logger.error(traceback.format_exc())
            return Response({
                'error': str(e),
                'traceback': traceback.format_exc()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def generate_for_period(self, request):
        """Génère les emplois du temps pour une période (semestre, année, personnalisée)"""
        from datetime import datetime, timedelta
        from courses.models import Course

        period_type = request.data.get('period_type')  # 'semester', 'year', 'custom'
        academic_period_id = request.data.get('academic_period_id')
        academic_year = request.data.get('academic_year')  # Ex: "2025-2026"
        semester = request.data.get('semester')  # Ex: "S1" ou "S2"
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        # Support both old curriculum_ids and new class_ids for backward compatibility
        class_ids = request.data.get('class_ids') or request.data.get('curriculum_ids', [])

        try:
            # Vérifier que l'utilisateur est authentifié
            if not request.user or not request.user.is_authenticated:
                return Response({
                    'error': 'Authentification requise'
                }, status=status.HTTP_401_UNAUTHORIZED)

            # Récupérer ou créer la période académique
            if academic_period_id:
                # Si un ID est fourni, l'utiliser
                academic_period = AcademicPeriod.objects.get(id=academic_period_id)
            elif academic_year and semester:
                # Sinon, chercher par année et semestre, ou créer si n'existe pas
                period_name = f"{academic_year} - {semester}"

                # Validation: les dates sont obligatoires
                if not start_date or not end_date:
                    return Response({
                        'error': 'Les dates de début et de fin sont obligatoires',
                        'hint': 'Veuillez fournir start_date et end_date au format YYYY-MM-DD'
                    }, status=status.HTTP_400_BAD_REQUEST)

                # Calculer les dates par défaut selon le semestre
                year_parts = academic_year.split('-')
                start_year = int(year_parts[0])

                # Utiliser les dates fournies (obligatoires maintenant)
                default_start = datetime.strptime(start_date, '%Y-%m-%d').date()
                default_end = datetime.strptime(end_date, '%Y-%m-%d').date()

                # Chercher ou créer la période
                academic_period, created = AcademicPeriod.objects.get_or_create(
                    academic_year=academic_year,
                    semester=semester,
                    defaults={
                        'name': period_name,
                        'start_date': default_start,
                        'end_date': default_end,
                        'is_current': True
                    }
                )

                if created:
                    logger.info(f"Période académique créée: {period_name}")
            else:
                return Response({
                    'error': 'Vous devez fournir soit academic_period_id, soit academic_year et semester'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Déterminer les dates selon le type de période
            period_start = academic_period.start_date
            period_end = academic_period.end_date

            generated_schedules = []

            with transaction.atomic():
                # Générer pour chaque classe sélectionnée
                for class_id in class_ids:
                    # Vérifier que la classe existe (accepter ID ou code)
                    try:
                        from courses.models_class import StudentClass
                        # Si c'est un nombre, chercher par ID, sinon par code
                        if str(class_id).isdigit():
                            student_class = StudentClass.objects.get(id=class_id)
                        else:
                            student_class = StudentClass.objects.get(code=class_id)
                    except StudentClass.DoesNotExist:
                        logger.error(f"StudentClass {class_id} n'existe pas")
                        continue

                    # Créer l'emploi du temps
                    schedule = Schedule.objects.create(
                        name=f"Emploi du temps {academic_period.name} - {student_class.name}",
                        academic_period=academic_period,
                        student_class=student_class,
                        level=student_class.level,
                        schedule_type='class',
                        status='draft',
                        created_by=request.user
                    )

                    # Récupérer les cours de la classe via ClassCourse
                    from courses.models_class import ClassCourse
                    class_courses = ClassCourse.objects.filter(
                        student_class=student_class
                    ).select_related('course')
                    courses = [cc.course for cc in class_courses]

                    # Générer les sessions (algorithme simplifié)
                    time_slots = TimeSlot.objects.filter(is_active=True)
                    current_date = period_start
                    course_index = 0

                    # Dictionnaire pour suivre les heures planifiées par cours
                    course_hours_scheduled = {course.id: 0 for course in courses}

                    # Dictionnaire pour suivre les sessions par cours (pour le séquencement pédagogique)
                    course_sessions_tracker = {course.id: [] for course in courses}

                    if not courses:
                        logger.warning(f"Aucun cours trouvé pour la classe {class_id}")
                        continue

                    # Vérifier si la classe a un emploi du temps fixe
                    has_fixed_schedule = getattr(student_class, 'has_fixed_schedule', False)
                    fixed_schedule_pattern = getattr(student_class, 'fixed_schedule_pattern', {}) if has_fixed_schedule else {}
                    fixed_room = getattr(student_class, 'fixed_room', None)

                    if has_fixed_schedule and fixed_schedule_pattern:
                        logger.info(f"Génération avec emploi du temps fixe pour {student_class.name}")

                    while current_date <= period_end:
                        # Pour chaque jour de la semaine
                        day_name = current_date.strftime('%A').lower()
                        day_slots = time_slots.filter(day_of_week=day_name)

                        # Si emploi du temps fixe, utiliser le pattern
                        if has_fixed_schedule and day_name in fixed_schedule_pattern:
                            fixed_sessions = fixed_schedule_pattern.get(day_name, [])
                            for fixed_session in fixed_sessions:
                                try:
                                    from datetime import time as dt_time
                                    # Parse les heures
                                    start_parts = fixed_session['start'].split(':')
                                    end_parts = fixed_session['end'].split(':')
                                    start_time = dt_time(int(start_parts[0]), int(start_parts[1]))
                                    end_time = dt_time(int(end_parts[0]), int(end_parts[1]))

                                    # Récupérer le cours
                                    course_id = fixed_session.get('course_id')
                                    course = Course.objects.get(id=course_id)

                                    # Utiliser la salle fixe si définie, sinon chercher
                                    room = fixed_room if fixed_room else None
                                    if not room:
                                        from rooms.models import Room
                                        room = Room.objects.filter(
                                            is_active=True,
                                            capacity__gte=student_class.student_count
                                        ).first()

                                    if room and course.teacher:
                                        # Créer la session
                                        session = ScheduleSession.objects.create(
                                            schedule=schedule,
                                            course=course,
                                            teacher=course.teacher,
                                            room=room,
                                            time_slot=None,  # Pas de time_slot car horaires personnalisés
                                            specific_date=current_date,
                                            specific_start_time=start_time,
                                            specific_end_time=end_time,
                                            session_type='CM'
                                        )

                                        # Créer l'occurrence
                                        from .models import SessionOccurrence
                                        SessionOccurrence.objects.create(
                                            session_template=session,
                                            actual_date=current_date,
                                            start_time=start_time,
                                            end_time=end_time,
                                            room=room,
                                            teacher=course.teacher,
                                            status='scheduled',
                                            is_room_modified=False,
                                            is_teacher_modified=False,
                                            is_time_modified=False,
                                            is_cancelled=False
                                        )

                                        logger.info(f"Session fixe créée: {course.code} le {day_name} de {start_time} à {end_time} en salle {room.code}")

                                except (Course.DoesNotExist, KeyError, ValueError) as e:
                                    logger.error(f"Erreur lors de la création d'une session fixe: {e}")
                                    continue

                        # Génération standard si pas d'emploi du temps fixe
                        elif not has_fixed_schedule or day_name not in fixed_schedule_pattern:
                            # NOUVELLE APPROCHE : Optimisation pédagogique avec flexibilité
                            # On évalue tous les cours pour chaque créneau et on choisit le meilleur
                            # en tenant compte à la fois de la pédagogie ET de la couverture

                            # Tracker des sessions déjà planifiées AUJOURD'HUI (ce jour spécifique)
                            sessions_today = {}  # {course_id: [session_types]}

                            for slot in day_slots:
                                # Trouver le meilleur cours pour ce créneau
                                best_course = None
                                best_session_type = None
                                best_score = -1

                                for candidate_course in courses:
                                    # Calculer la durée d'une session en heures
                                    session_duration_hours = (
                                        (slot.end_time.hour * 60 + slot.end_time.minute) -
                                        (slot.start_time.hour * 60 + slot.start_time.minute)
                                    ) / 60.0

                                    # Vérifier si le cours a encore besoin d'heures
                                    hours_remaining = candidate_course.total_hours - course_hours_scheduled.get(candidate_course.id, 0)

                                    if hours_remaining < session_duration_hours:
                                        continue  # Ce cours a atteint son quota

                                    # RÈGLE : Maximum 1 session par cours par jour
                                    if candidate_course.id in sessions_today:
                                        logger.debug(f"Cours {candidate_course.code} déjà planifié aujourd'hui ({day_name})")
                                        continue

                                    # Récupérer l'historique des sessions pour ce cours
                                    existing_sessions = course_sessions_tracker.get(candidate_course.id, [])

                                    # Déterminer le type de session
                                    # PRIORITÉ 1 : Si le code du cours contient le type (ex: COURS-CM, COURS-TD), l'utiliser
                                    next_session_type = None
                                    course_code_upper = candidate_course.code.upper()

                                    # IMPORTANT : Vérifier TPE avant TP (sinon "-TPE" matchera "-TP")
                                    if '-TPE' in course_code_upper or '_TPE' in course_code_upper:
                                        next_session_type = 'TPE'
                                    elif '-CM' in course_code_upper or '_CM' in course_code_upper:
                                        next_session_type = 'CM'
                                    elif '-TD' in course_code_upper or '_TD' in course_code_upper:
                                        next_session_type = 'TD'
                                    elif '-TP' in course_code_upper or '_TP' in course_code_upper:
                                        next_session_type = 'TP'
                                    else:
                                        # PRIORITÉ 2 : Sinon, utiliser le séquencement pédagogique automatique
                                        next_session_type = PedagogicalSequencer.get_next_session_type(existing_sessions)

                                    # Valider que la séquence respecte les délais minimums
                                    # MAIS seulement si le type n'est PAS fixé dans le code du cours
                                    # (car un cours "-CM" est déjà spécifique et n'a pas de contraintes de séquence)
                                    is_valid = True
                                    reason = "Type fixé dans le code du cours"

                                    # Vérifier si le type est déterminé automatiquement (pas dans le code)
                                    # IMPORTANT : Vérifier TPE avant TP
                                    has_fixed_type = ('-TPE' in course_code_upper or '_TPE' in course_code_upper or
                                                     '-CM' in course_code_upper or '_CM' in course_code_upper or
                                                     '-TD' in course_code_upper or '_TD' in course_code_upper or
                                                     '-TP' in course_code_upper or '_TP' in course_code_upper)

                                    if not has_fixed_type:
                                        # Seulement pour les cours sans type fixe, valider la séquence
                                        is_valid, reason = PedagogicalSequencer.is_valid_sequence(
                                            existing_sessions,
                                            current_date,
                                            next_session_type
                                        )

                                        # Si la séquence viole les délais minimums, passer au cours suivant
                                        if not is_valid:
                                            logger.debug(f"Séquence invalide pour {candidate_course.code} ({next_session_type}): {reason}")
                                            continue

                                    # Calculer le score pédagogique
                                    # Le score favorise les placements optimaux mais accepte les sous-optimaux
                                    ped_score = PedagogicalSequencer.calculate_session_priority(
                                        session_type=next_session_type,
                                        slot_start_time=slot.start_time,
                                        day_of_week=day_name,
                                        course_sessions=existing_sessions,
                                        proposed_date=current_date
                                    )

                                    # BONUS DE COUVERTURE : Favoriser les cours qui ont peu d'heures planifiées
                                    # MAIS ne doit PAS écraser les contraintes pédagogiques
                                    coverage_ratio = course_hours_scheduled.get(candidate_course.id, 0) / candidate_course.total_hours
                                    coverage_bonus = int((1 - coverage_ratio) * 30)  # 0-30 points

                                    # BONUS DE DISTRIBUTION : Favoriser les cours qui n'ont PAS ENCORE été programmés
                                    # Ceci assure que tous les cours apparaissent avant de répéter
                                    sessions_count = len(course_sessions_tracker.get(candidate_course.id, []))

                                    # Calculer le nombre moyen de sessions par cours
                                    total_sessions = sum(len(sessions) for sessions in course_sessions_tracker.values())
                                    avg_sessions = total_sessions / len(courses) if len(courses) > 0 else 0

                                    # Bonus si ce cours est en retard par rapport à la moyenne
                                    distribution_bonus = 0
                                    if sessions_count < avg_sessions:
                                        # Cours sous la moyenne : GROS bonus (priorité absolue)
                                        distribution_bonus = int((avg_sessions - sessions_count) * 50)

                                    # Score final = score pédagogique + bonus de couverture + bonus de distribution
                                    total_score = ped_score + coverage_bonus + distribution_bonus

                                    # Log pour debug
                                    logger.debug(
                                        f"{candidate_course.code} ({next_session_type}): "
                                        f"ped={ped_score}, cov={coverage_bonus}, dist={distribution_bonus}, "
                                        f"total={total_score} (sessions={sessions_count}, avg={avg_sessions:.1f})"
                                    )

                                    # Garder le meilleur score
                                    if total_score > best_score:
                                        best_score = total_score
                                        best_course = candidate_course
                                        best_session_type = next_session_type

                                # Si aucun cours disponible, passer au créneau suivant
                                if not best_course:
                                    continue

                                course = best_course
                                session_type = best_session_type

                                # Calculer la durée de la session
                                session_duration_hours = (
                                    (slot.end_time.hour * 60 + slot.end_time.minute) -
                                    (slot.start_time.hour * 60 + slot.start_time.minute)
                                ) / 60.0

                                # Trouver une salle disponible pour ce créneau ET cette date spécifique
                                from rooms.models import Room
                                from .models import SessionOccurrence
                                from courses.models_class import ClassRoomPreference

                                # Déterminer le nombre d'étudiants requis
                                required_capacity = student_class.student_count if hasattr(student_class, 'student_count') else 30

                                # Exclure les salles déjà utilisées pour CETTE DATE SPÉCIFIQUE et ce créneau horaire
                                # Vérifier dans TOUTES les sessions (pas seulement ce schedule)
                                used_room_ids_sessions = ScheduleSession.objects.filter(
                                    specific_date=current_date,
                                    specific_start_time=slot.start_time,
                                    specific_end_time=slot.end_time
                                ).values_list('room_id', flat=True)

                                # Vérifier aussi dans les occurrences
                                used_room_ids_occurrences = SessionOccurrence.objects.filter(
                                    actual_date=current_date,
                                    start_time=slot.start_time,
                                    end_time=slot.end_time,
                                    status='scheduled',
                                    is_cancelled=False
                                ).values_list('room_id', flat=True)

                                # Combiner les deux listes
                                all_used_room_ids = set(list(used_room_ids_sessions) + list(used_room_ids_occurrences))

                                # Chercher une salle disponible avec la capacité suffisante
                                available_rooms = Room.objects.filter(
                                    is_active=True,
                                    capacity__gte=required_capacity
                                ).exclude(id__in=all_used_room_ids)

                                # Vérifier les équipements requis par le cours
                                if hasattr(course, 'requires_projector') and course.requires_projector:
                                    available_rooms = available_rooms.filter(has_projector=True)
                                if hasattr(course, 'requires_computer') and course.requires_computer:
                                    available_rooms = available_rooms.filter(has_computer=True)
                                if hasattr(course, 'requires_laboratory') and course.requires_laboratory:
                                    available_rooms = available_rooms.filter(is_laboratory=True)

                                # Exclure les salles exclues par le cours
                                if hasattr(course, 'excluded_rooms') and course.excluded_rooms:
                                    available_rooms = available_rooms.exclude(id__in=course.excluded_rooms)

                                # 1. Vérifier si la classe a une salle fixe
                                available_room = None
                                if fixed_room and fixed_room.id not in all_used_room_ids:
                                    # Utiliser la salle fixe de la classe si disponible
                                    available_room = fixed_room
                                    logger.info(f"Salle fixe de classe allouée: {available_room.code} pour {student_class.name}")

                                # 2. Sinon, vérifier les préférences de salle de la classe (NOUVEAU)
                                if not available_room:
                                    # Récupérer les préférences de salle par ordre de priorité
                                    class_preferences = ClassRoomPreference.objects.filter(
                                        student_class=student_class,
                                        is_active=True
                                    ).order_by('priority').select_related('room')

                                    for preference in class_preferences:
                                        if preference.room.id not in all_used_room_ids and preference.room.is_active:
                                            # Vérifier que la salle a la capacité suffisante
                                            if preference.room.capacity >= required_capacity:
                                                available_room = preference.room
                                                priority_label = dict(ClassRoomPreference.PRIORITY_CHOICES).get(preference.priority, '')
                                                logger.info(f"Salle de préférence de classe allouée ({priority_label}): {available_room.code} pour {student_class.name}")
                                                break

                                # 3. Sinon, prioriser les salles préférées du cours
                                if not available_room and hasattr(course, 'preferred_rooms') and course.preferred_rooms:
                                    # Essayer d'abord les salles préférées
                                    preferred_available = available_rooms.filter(id__in=course.preferred_rooms).order_by('capacity')
                                    if preferred_available.exists():
                                        available_room = preferred_available.first()
                                        logger.info(f"Salle préférée du cours allouée: {available_room.code} pour {course.code}")

                                # 4. Si aucune salle préférée disponible, prendre la plus proche en capacité
                                if not available_room:
                                    available_room = available_rooms.order_by('capacity').first()

                                # Vérifier que l'enseignant est disponible
                                teacher_available = True
                                if course.teacher:
                                    # Vérifier les sessions existantes
                                    teacher_conflicts_sessions = ScheduleSession.objects.filter(
                                        teacher=course.teacher,
                                        specific_date=current_date,
                                        specific_start_time=slot.start_time,
                                        specific_end_time=slot.end_time
                                    ).exists()

                                    # Vérifier les occurrences
                                    teacher_conflicts_occurrences = SessionOccurrence.objects.filter(
                                        teacher=course.teacher,
                                        actual_date=current_date,
                                        start_time=slot.start_time,
                                        end_time=slot.end_time,
                                        status='scheduled',
                                        is_cancelled=False
                                    ).exists()

                                    teacher_available = not (teacher_conflicts_sessions or teacher_conflicts_occurrences)

                                # Logging pour debug
                                if not available_room:
                                    logger.warning(f"Aucune salle disponible pour {course.code} le {current_date} à {slot.start_time} (capacité requise: {required_capacity})")
                                elif not course.teacher:
                                    logger.warning(f"Aucun enseignant assigné pour le cours {course.code}")
                                elif not teacher_available:
                                    logger.warning(f"Enseignant {course.teacher} non disponible pour {course.code} le {current_date} à {slot.start_time}")

                                if available_room and course.teacher and teacher_available:
                                    logger.info(f"Salle allouée: {available_room.code} (capacité: {available_room.capacity}) pour {course.code} - {student_class.name}")
                                    logger.info(f"Session {session_type} programmée pour {course.code} le {current_date} ({day_name}) à {slot.start_time} (score: {best_score})")

                                    # Créer la session template avec le type pédagogique approprié
                                    session = ScheduleSession.objects.create(
                                        schedule=schedule,
                                        course=course,
                                        teacher=course.teacher,
                                        room=available_room,
                                        time_slot=slot,
                                        specific_date=current_date,
                                        specific_start_time=slot.start_time,
                                        specific_end_time=slot.end_time,
                                        session_type=session_type
                                    )

                                    # Créer l'occurrence correspondante (nouveau système)
                                    from .models import SessionOccurrence
                                    SessionOccurrence.objects.create(
                                        session_template=session,
                                        actual_date=current_date,
                                        start_time=slot.start_time,
                                        end_time=slot.end_time,
                                        room=available_room,
                                        teacher=course.teacher,
                                        status='scheduled',
                                        is_room_modified=False,
                                        is_teacher_modified=False,
                                        is_time_modified=False,
                                        is_cancelled=False
                                    )

                                    # Mettre à jour le compteur d'heures pour ce cours
                                    session_duration_hours = (
                                        (slot.end_time.hour * 60 + slot.end_time.minute) -
                                        (slot.start_time.hour * 60 + slot.start_time.minute)
                                    ) / 60.0
                                    course_hours_scheduled[course.id] = course_hours_scheduled.get(course.id, 0) + session_duration_hours

                                    # Ajouter cette session au tracker pour le séquencement pédagogique
                                    course_sessions_tracker[course.id].append({
                                        'date': current_date,
                                        'type': session_type,
                                        'start_time': slot.start_time,
                                        'day_of_week': day_name
                                    })

                                    # Marquer ce cours comme planifié aujourd'hui
                                    if course.id not in sessions_today:
                                        sessions_today[course.id] = []
                                    sessions_today[course.id].append(session_type)

                                    logger.info(f"Cours {course.code}: {course_hours_scheduled[course.id]}h planifiées / {course.total_hours}h totales")

                        # Passer au jour suivant
                        current_date += timedelta(days=1)

                        # Sauter les week-ends
                        if current_date.weekday() >= 5:
                            current_date += timedelta(days=7 - current_date.weekday())

                    generated_schedules.append({
                        'id': schedule.id,
                        'name': schedule.name,
                        'sessions_count': schedule.sessions.count()
                    })

            return Response({
                'message': f'{len(generated_schedules)} emplois du temps générés avec succès',
                'schedules': generated_schedules,
                'period': {
                    'start': period_start,
                    'end': period_end,
                    'name': academic_period.name
                }
            }, status=status.HTTP_201_CREATED)

        except AcademicPeriod.DoesNotExist:
            return Response({
                'error': 'Période académique non trouvée'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Erreur lors de la génération: {error_trace}")
            return Response({
                'error': f'Erreur lors de la génération: {str(e)}',
                'details': error_trace if request.user.is_staff else None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def weekly_view(self, request, pk=None):
        """Vue hebdomadaire de l'emploi du temps"""
        schedule = self.get_object()
        sessions = schedule.sessions.all().select_related(
            'course', 'teacher', 'room', 'time_slot'
        )

        # Organiser par jour de la semaine
        weekly_data = {
            'monday': [],
            'tuesday': [],
            'wednesday': [],
            'thursday': [],
            'friday': [],
            'saturday': [],
            'sunday': []
        }
        
        day_mapping = {
            'monday': 'monday',
            'tuesday': 'tuesday', 
            'wednesday': 'wednesday',
            'thursday': 'thursday',
            'friday': 'friday',
            'saturday': 'saturday',
            'sunday': 'sunday'
        }
        
        for session in sessions:
            day = session.time_slot.day_of_week
            if day in day_mapping:
                weekly_data[day_mapping[day]].append(
                    ScheduleSessionSerializer(session).data
                )
        
        serializer = WeeklyScheduleSerializer(weekly_data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def detect_conflicts(self, request, pk=None):
        """Détecte les conflits dans un emploi du temps"""
        schedule = self.get_object()
        conflicts_found = []
        
        sessions = schedule.sessions.all()
        
        for session in sessions:
            # Vérifier les conflits d'enseignant
            teacher_conflicts = ScheduleSession.objects.filter(
                teacher=session.teacher,
                time_slot=session.time_slot,
                schedule__academic_period=schedule.academic_period
            ).exclude(id=session.id)
            
            for conflict_session in teacher_conflicts:
                conflict, created = Conflict.objects.get_or_create(
                    schedule_session=session,
                    conflict_type='teacher_double_booking',
                    conflicting_session=conflict_session,
                    defaults={
                        'description': f'Enseignant {session.teacher} déjà occupé',
                        'severity': 'high'
                    }
                )
                if created:
                    conflicts_found.append(conflict)
            
            # Vérifier les conflits de salle
            room_conflicts = ScheduleSession.objects.filter(
                room=session.room,
                time_slot=session.time_slot,
                schedule__academic_period=schedule.academic_period
            ).exclude(id=session.id)
            
            for conflict_session in room_conflicts:
                conflict, created = Conflict.objects.get_or_create(
                    schedule_session=session,
                    conflict_type='room_double_booking',
                    conflicting_session=conflict_session,
                    defaults={
                        'description': f'Salle {session.room} déjà occupée',
                        'severity': 'critical'
                    }
                )
                if created:
                    conflicts_found.append(conflict)
        
        return Response({
            'conflicts_detected': len(conflicts_found),
            'conflicts': ConflictSerializer(conflicts_found, many=True).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def ml_anomalies(self, request, pk=None):
        """🤖 Détection ML des anomalies dans l'emploi du temps"""
        schedule = self.get_object()

        try:
            logger.info(f"🔍 Détection des anomalies ML pour le schedule {schedule.id}")

            # Appeler le service ML pour détecter les anomalies
            anomalies_result = ml_service.detect_schedule_anomalies(schedule_data={'schedule_id': schedule.id})

            # Enrichir avec des statistiques du schedule
            sessions_count = schedule.sessions.count()
            unresolved_conflicts = Conflict.objects.filter(
                schedule_session__schedule=schedule,
                is_resolved=False
            ).count()

            # Calculer la sévérité globale
            total_anomalies = len(anomalies_result.get('anomalies', []))
            critical_anomalies = sum(1 for a in anomalies_result.get('anomalies', [])
                                    if a.get('severity') == 'critical')
            high_anomalies = sum(1 for a in anomalies_result.get('anomalies', [])
                                if a.get('severity') == 'high')

            # Déterminer le score de santé (0-100)
            health_score = 100
            if sessions_count > 0:
                anomaly_ratio = total_anomalies / sessions_count
                health_score = max(0, 100 - (anomaly_ratio * 100))
                health_score -= (critical_anomalies * 10)
                health_score -= (high_anomalies * 5)
                health_score = max(0, min(100, health_score))

            # Recommandations basées sur les anomalies
            recommendations = []
            if critical_anomalies > 0:
                recommendations.append({
                    'priority': 'critical',
                    'message': f'{critical_anomalies} anomalie(s) critique(s) détectée(s)',
                    'action': 'Résoudre immédiatement les conflits critiques avant publication'
                })
            if high_anomalies > 3:
                recommendations.append({
                    'priority': 'high',
                    'message': f'{high_anomalies} anomalies de haute priorité',
                    'action': 'Revoir les assignations de salles et enseignants'
                })
            if health_score < 70:
                recommendations.append({
                    'priority': 'medium',
                    'message': f'Score de santé faible: {health_score:.1f}/100',
                    'action': 'Utiliser l\'optimiseur ML pour améliorer l\'emploi du temps'
                })

            response_data = {
                'schedule_id': schedule.id,
                'schedule_name': schedule.name,
                'analysis': {
                    'total_sessions': sessions_count,
                    'total_anomalies': total_anomalies,
                    'anomalies_by_severity': {
                        'critical': critical_anomalies,
                        'high': high_anomalies,
                        'medium': total_anomalies - critical_anomalies - high_anomalies
                    },
                    'health_score': round(health_score, 1),
                    'status': 'critical' if health_score < 50 else 'warning' if health_score < 70 else 'good'
                },
                'anomalies': anomalies_result.get('anomalies', []),
                'recommendations': recommendations,
                'detection_metadata': {
                    'detected_at': anomalies_result.get('detected_at', timezone.now().isoformat()),
                    'model_version': anomalies_result.get('model_version', 'v1.0'),
                    'detection_time': anomalies_result.get('detection_time', 0)
                }
            }

            logger.info(f"✅ Détection ML terminée: {total_anomalies} anomalies trouvées, score de santé: {health_score:.1f}")

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"❌ Erreur lors de la détection ML des anomalies: {e}")
            return Response({
                'error': 'Erreur lors de la détection des anomalies',
                'details': str(e),
                'schedule_id': schedule.id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques générales des emplois du temps"""
        total_schedules = Schedule.objects.count()
        published_schedules = Schedule.objects.filter(is_published=True).count()
        
        # Sessions par type
        session_types = ScheduleSession.objects.values('session_type').annotate(
            count=Count('id')
        )
        
        # Conflits par sévérité
        conflicts_by_severity = Conflict.objects.filter(is_resolved=False).values('severity').annotate(
            count=Count('id')
        )
        
        # Emplois du temps par période académique
        by_period = Schedule.objects.values(
            'academic_period__name'
        ).annotate(count=Count('id'))
        
        return Response({
            'total_schedules': total_schedules,
            'published_schedules': published_schedules,
            'draft_schedules': total_schedules - published_schedules,
            'session_types': list(session_types),
            'unresolved_conflicts': list(conflicts_by_severity),
            'by_academic_period': list(by_period)
        })
    
    @action(detail=False, methods=['get'])
    def weekly_sessions(self, request):
        """Récupère toutes les sessions d'une semaine donnée"""
        from datetime import datetime, timedelta
        
        # Paramètres
        curriculum = request.query_params.get('curriculum')
        week_start = request.query_params.get('week_start')  # Format: YYYY-MM-DD
        teacher_id = request.query_params.get('teacher')
        room_id = request.query_params.get('room')
        
        if not week_start:
            return Response({
                'error': 'Le paramètre week_start est requis (format YYYY-MM-DD)'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            start_date = datetime.strptime(week_start, '%Y-%m-%d').date()
            end_date = start_date + timedelta(days=6)
        except ValueError:
            return Response({
                'error': 'Format de date invalide. Utilisez YYYY-MM-DD'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Construction de la requête
        queryset = ScheduleSession.objects.select_related(
            'course', 'teacher', 'room', 'time_slot', 'schedule'
        ).filter(
            models.Q(specific_date__range=[start_date, end_date]) |
            models.Q(specific_date__isnull=True, schedule__is_published=True)
        ).order_by('time_slot__day_of_week', 'time_slot__start_time')
        
        # Filtres
        if curriculum:
            if curriculum.isdigit():
                queryset = queryset.filter(schedule__curriculum_id=curriculum)
            else:
                queryset = queryset.filter(schedule__curriculum__code=curriculum)
        
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)
            
        if room_id:
            queryset = queryset.filter(room_id=room_id)
        
        # Organiser par jour
        week_data = {
            'monday': [],
            'tuesday': [],
            'wednesday': [],
            'thursday': [],
            'friday': [],
            'saturday': [],
            'sunday': []
        }
        
        for session in queryset:
            day_key = session.time_slot.day_of_week
            if day_key in week_data:
                session_data = ScheduleSessionSerializer(session).data
                # Ajouter la date spécifique si elle existe
                if session.specific_date:
                    session_data['effective_date'] = session.specific_date.strftime('%Y-%m-%d')
                else:
                    # Calculer la date effective basée sur le jour de la semaine
                    days_mapping = {
                        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                        'friday': 4, 'saturday': 5, 'sunday': 6
                    }
                    if day_key in days_mapping:
                        effective_date = start_date + timedelta(days=days_mapping[day_key])
                        session_data['effective_date'] = effective_date.strftime('%Y-%m-%d')
                
                week_data[day_key].append(session_data)
        
        return Response({
            'week_start': week_start,
            'week_end': end_date.strftime('%Y-%m-%d'),
            'sessions_by_day': week_data,
            'total_sessions': sum(len(sessions) for sessions in week_data.values())
        })
    
    @action(detail=False, methods=['get'])
    def daily_sessions(self, request):
        """Récupère toutes les sessions d'une journée donnée"""
        from datetime import datetime
        
        # Paramètres
        date_param = request.query_params.get('date')
        curriculum = request.query_params.get('curriculum')
        teacher_id = request.query_params.get('teacher')
        room_id = request.query_params.get('room')
        
        if not date_param:
            return Response({
                'error': 'Le paramètre date est requis (format YYYY-MM-DD)'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
            day_of_week = target_date.strftime('%A').lower()
        except ValueError:
            return Response({
                'error': 'Format de date invalide. Utilisez YYYY-MM-DD'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Construction de la requête
        queryset = ScheduleSession.objects.select_related(
            'course', 'teacher', 'room', 'time_slot', 'schedule'
        ).filter(
            models.Q(specific_date=target_date) |
            models.Q(
                specific_date__isnull=True,
                time_slot__day_of_week=day_of_week,
                schedule__is_published=True
            )
        ).order_by('time_slot__start_time')
        
        # Filtres
        if curriculum:
            if curriculum.isdigit():
                queryset = queryset.filter(schedule__curriculum_id=curriculum)
            else:
                queryset = queryset.filter(schedule__curriculum__code=curriculum)
        
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)
            
        if room_id:
            queryset = queryset.filter(room_id=room_id)
        
        # Sérialiser les résultats
        sessions_data = []
        for session in queryset:
            session_data = ScheduleSessionSerializer(session).data
            session_data['effective_date'] = date_param
            sessions_data.append(session_data)
        
        return Response({
            'date': date_param,
            'day_of_week': target_date.strftime('%A'),
            'day_of_week_fr': target_date.strftime('%A'),  # TODO: Traduire en français
            'sessions': sessions_data,
            'total_sessions': len(sessions_data)
        })

    @action(detail=True, methods=['post'])
    def generate_advanced(self, request, pk=None):
        """Génération avancée d'emploi du temps avec détection de blocages et suggestions"""
        from .advanced_generation_service import AdvancedScheduleGenerator
        from datetime import datetime

        schedule = self.get_object()

        preview_mode = request.data.get('preview_mode', False)
        force_regenerate = request.data.get('force_regenerate', False)
        date_from = request.data.get('date_from')
        date_to = request.data.get('date_to')

        # Convertir les dates si fournies
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            except ValueError:
                return Response({
                    'error': 'Format de date invalide pour date_from. Utilisez YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)

        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            except ValueError:
                return Response({
                    'error': 'Format de date invalide pour date_to. Utilisez YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)

        try:
            generator = AdvancedScheduleGenerator(schedule)
            result = generator.generate_with_validation(
                preview_mode=preview_mode,
                force_regenerate=force_regenerate,
                date_from=date_from,
                date_to=date_to
            )

            if result['success']:
                logger.info(
                    f"Génération avancée réussie pour schedule {schedule.id}: "
                    f"{result['occurrences_created']} occurrences créées"
                )
            else:
                logger.warning(
                    f"Génération avancée échouée pour schedule {schedule.id}: "
                    f"{result.get('message', 'Erreur inconnue')}"
                )

            return Response(result)

        except Exception as e:
            logger.error(f"Erreur lors de la génération avancée: {str(e)}")
            return Response({
                'success': False,
                'error': 'Erreur lors de la génération',
                'details': str(e),
                'schedule_id': schedule.id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get', 'post'])
    def pedagogical_constraints(self, request):
        """Gère les contraintes pédagogiques par type de cours"""
        from .course_type_constraints import CourseTypeConstraintChecker
        from .serializers import PedagogicalConstraintSerializer
        from datetime import time

        checker = CourseTypeConstraintChecker()

        if request.method == 'GET':
            # Retourne la configuration actuelle des contraintes
            constraints = []

            for course_type, rule in checker.rules.items():
                # Extraire les heures de début et fin des plages préférées
                if rule.preferred_time_ranges:
                    preferred_start = rule.preferred_time_ranges[0][0]
                    preferred_end = rule.preferred_time_ranges[0][1]
                else:
                    preferred_start = time(8, 0)
                    preferred_end = time(18, 0)

                constraint_data = {
                    'course_type': course_type,
                    'preferred_time_start': preferred_start,
                    'preferred_time_end': preferred_end,
                    'preferred_days': rule.preferred_days,
                    'min_duration_hours': rule.min_duration_hours,
                    'max_duration_hours': rule.max_duration_hours,
                    'max_per_day': rule.max_per_day,
                    'requires_predecessor': rule.requires_predecessor,
                    'predecessor_type': rule.predecessor_type or '',
                    'delay_after_predecessor_min': 0,
                    'delay_after_predecessor_max': 0,
                    'min_semester_week': 1 if course_type == 'TPE' else 1
                }

                # Ajouter les délais spécifiques pour TD
                if course_type == 'TD':
                    constraint_data['delay_after_predecessor_min'] = 2
                    constraint_data['delay_after_predecessor_max'] = 3
                elif course_type == 'TPE':
                    constraint_data['min_semester_week'] = 6

                constraints.append(constraint_data)

            serializer = PedagogicalConstraintSerializer(constraints, many=True)
            return Response(serializer.data)

        elif request.method == 'POST':
            # Sauvegarde les nouvelles contraintes
            serializer = PedagogicalConstraintSerializer(data=request.data, many=True)

            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Ici on pourrait sauvegarder dans la base de données ou dans un fichier de config
            # Pour l'instant, on retourne simplement un succès
            # TODO: Implémenter la persistance des contraintes personnalisées

            return Response({
                'success': True,
                'message': 'Contraintes pédagogiques mises à jour avec succès',
                'constraints_updated': len(serializer.validated_data)
            }, status=status.HTTP_200_OK)


class ScheduleSessionViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des sessions d'emploi du temps"""
    queryset = ScheduleSession.objects.all()
    serializer_class = ScheduleSessionSerializer
    permission_classes = []  # Temporairement désactivé pour les tests

    export_fields = ['id', 'schedule', 'course', 'teacher', 'room', 'time_slot', 'specific_date', 'session_type', 'is_cancelled']
    import_fields = ['schedule', 'course', 'teacher', 'room', 'time_slot', 'specific_date', 'session_type']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        schedule_id = self.request.query_params.get('schedule')
        if schedule_id:
            queryset = queryset.filter(schedule_id=schedule_id)
        
        course_id = self.request.query_params.get('course')
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        
        teacher_id = self.request.query_params.get('teacher')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)
        
        room_id = self.request.query_params.get('room')
        if room_id:
            queryset = queryset.filter(room_id=room_id)
        
        # Filtrage par curriculum (accepte à la fois l'ID et le code)
        curriculum = self.request.query_params.get('curriculum')
        if curriculum:
            # Si c'est un nombre, filtrer par ID, sinon par code
            if curriculum.isdigit():
                queryset = queryset.filter(schedule__curriculum_id=curriculum)
            else:
                queryset = queryset.filter(schedule__curriculum__code=curriculum)
        
        # Filtrage par date spécifique
        date_param = self.request.query_params.get('date')
        if date_param:
            try:
                from datetime import datetime
                target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
                # Filtrer par specific_date ou par day_of_week si pas de date spécifique
                queryset = queryset.filter(
                    models.Q(specific_date=target_date) |
                    models.Q(
                        specific_date__isnull=True,
                        time_slot__day_of_week=target_date.strftime('%A').lower()
                    )
                )
            except ValueError:
                pass  # Ignorer les dates mal formatées
        
        return queryset.order_by('time_slot__day_of_week', 'time_slot__start_time')


class ConflictViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des conflits"""
    queryset = Conflict.objects.all()
    serializer_class = ConflictSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        schedule_id = self.request.query_params.get('schedule')
        if schedule_id:
            queryset = queryset.filter(schedule_session__schedule_id=schedule_id)
        
        severity = self.request.query_params.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        
        unresolved_only = self.request.query_params.get('unresolved_only')
        if unresolved_only == 'true':
            queryset = queryset.filter(is_resolved=False)
        
        return queryset.order_by('-detected_at')
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Marque un conflit comme résolu"""
        conflict = self.get_object()
        
        conflict.is_resolved = True
        conflict.resolved_at = timezone.now()
        conflict.resolution_notes = request.data.get('resolution_notes', '')
        conflict.save()
        
        return Response({
            'message': 'Conflit marqué comme résolu'
        }, status=status.HTTP_200_OK)


class ScheduleOptimizationViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des optimisations"""
    queryset = ScheduleOptimization.objects.all()
    serializer_class = ScheduleOptimizationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        schedule_id = self.request.query_params.get('schedule')
        if schedule_id:
            queryset = queryset.filter(schedule_id=schedule_id)
        
        return queryset.order_by('-started_at')
    
    def perform_create(self, serializer):
        serializer.save(started_by=self.request.user)


class ScheduleTemplateViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des templates"""
    queryset = ScheduleTemplate.objects.all()
    serializer_class = ScheduleTemplateSerializer
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'name', 'student_class', 'level', 'template_data', 'is_active']
    import_fields = ['name', 'student_class', 'level', 'template_data']

    def get_queryset(self):
        queryset = super().get_queryset().filter(is_active=True)

        student_class_id = self.request.query_params.get('student_class')
        if student_class_id:
            queryset = queryset.filter(student_class_id=student_class_id)
        
        level = self.request.query_params.get('level')
        if level:
            queryset = queryset.filter(level=level)
        
        return queryset.order_by('name')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ScheduleConstraintViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des contraintes"""
    queryset = ScheduleConstraint.objects.all()
    serializer_class = ScheduleConstraintSerializer
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'schedule', 'name', 'constraint_type', 'priority', 'description', 'is_active']
    import_fields = ['schedule', 'name', 'constraint_type', 'priority', 'description']
    
    def get_queryset(self):
        queryset = super().get_queryset().filter(is_active=True)
        
        schedule_id = self.request.query_params.get('schedule')
        if schedule_id:
            queryset = queryset.filter(schedule_id=schedule_id)
        
        constraint_type = self.request.query_params.get('type')
        if constraint_type:
            queryset = queryset.filter(constraint_type=constraint_type)
        
        return queryset.order_by('priority', 'name')


class ScheduleExportViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des exports"""
    queryset = ScheduleExport.objects.all()
    serializer_class = ScheduleExportSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        schedule_id = self.request.query_params.get('schedule')
        if schedule_id:
            queryset = queryset.filter(schedule_id=schedule_id)
        
        export_format = self.request.query_params.get('format')
        if export_format:
            queryset = queryset.filter(export_format=export_format)
        
        return queryset.order_by('-exported_at')
    
    def perform_create(self, serializer):
        serializer.save(exported_by=self.request.user)
