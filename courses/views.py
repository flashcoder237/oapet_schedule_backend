# courses/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg, Q
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

from core.mixins import ImportExportMixin
from .models import (
    Department, Teacher, Course, Curriculum, CurriculumCourse,
    Student, CourseEnrollment, CoursePrerequisite,
    TeacherPreference, TeacherUnavailability, TeacherScheduleRequest, SessionFeedback
)
from .serializers import (
    DepartmentSerializer, TeacherSerializer, CourseSerializer, CurriculumSerializer,
    StudentSerializer, CourseEnrollmentSerializer, CoursePrerequisiteSerializer,
    TeacherCreateSerializer, StudentCreateSerializer, CourseDetailSerializer,
    CurriculumDetailSerializer, TeacherPreferenceSerializer, TeacherPreferenceCreateSerializer,
    TeacherUnavailabilitySerializer, TeacherUnavailabilityCreateSerializer,
    TeacherDetailWithPreferencesSerializer, TeacherScheduleRequestSerializer,
    TeacherScheduleRequestCreateSerializer, SessionFeedbackSerializer,
    SessionFeedbackCreateSerializer, TeacherDashboardSerializer
)


class DepartmentViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des départements"""
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'name', 'code', 'description', 'is_active']
    import_fields = ['name', 'code', 'description']
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Statistiques d'un département"""
        department = self.get_object()
        
        stats = {
            'teachers_count': department.teachers.filter(is_active=True).count(),
            'courses_count': department.courses.filter(is_active=True).count(),
            'curricula_count': department.curricula.filter(is_active=True).count(),
            'total_students': Student.objects.filter(
                curriculum__department=department,
                is_active=True
            ).count()
        }
        
        return Response(stats)


class TeacherViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des enseignants"""
    queryset = Teacher.objects.all()
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'employee_id', 'department', 'specializations', 'max_hours_per_week', 'is_active']
    import_fields = ['employee_id', 'department', 'specializations', 'max_hours_per_week']

    def get_serializer_class(self):
        if self.action == 'create':
            return TeacherCreateSerializer
        return TeacherSerializer

    def get_queryset(self):
        queryset = super().get_queryset().select_related('user', 'department')
        department_id = self.request.query_params.get('department')
        if department_id:
            queryset = queryset.filter(department_id=department_id)

        # Filtrer par enseignants actifs ET avec utilisateurs actifs
        return queryset.filter(
            is_active=True,
            user__is_active=True
        ).order_by('user__last_name', 'user__first_name')
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques des enseignants"""
        total_teachers = Teacher.objects.filter(is_active=True).count()
        
        # Par département
        by_department = Teacher.objects.filter(is_active=True).values(
            'department__name', 'department__code'
        ).annotate(count=Count('id'))
        
        # Charge de travail moyenne
        avg_hours = Teacher.objects.filter(is_active=True).aggregate(
            avg_max_hours=Avg('max_hours_per_week')
        )
        
        return Response({
            'total_teachers': total_teachers,
            'by_department': list(by_department),
            'averages': avg_hours
        })
    
    @action(detail=True, methods=['get'])
    def schedule(self, request, pk=None):
        """Planning d'un enseignant"""
        from schedules.models import ScheduleSession
        teacher = self.get_object()

        # Sessions programmées
        sessions = ScheduleSession.objects.filter(
            teacher=teacher,
            is_cancelled=False
        ).select_related('course', 'room', 'time_slot')

        data = []
        for session in sessions:
            data.append({
                'id': session.id,
                'course_name': session.course.name,
                'course_code': session.course.code,
                'room': session.room.code,
                'day': session.time_slot.day_of_week,
                'start_time': session.time_slot.start_time,
                'end_time': session.time_slot.end_time,
                'session_type': session.session_type
            })

        return Response({
            'teacher': teacher.user.get_full_name(),
            'total_sessions': len(data),
            'sessions': data
        })

    @action(detail=True, methods=['get'])
    def dashboard(self, request, pk=None):
        """Dashboard complet pour un enseignant

        Utilise SessionOccurrence pour refléter les modifications admin
        (déplacements de sessions, changements de salle, etc.)
        """
        from schedules.models import ScheduleSession, SessionOccurrence, Conflict
        from django.utils import timezone
        from django.db.models import Q
        from datetime import timedelta, datetime

        teacher = self.get_object()
        now = timezone.now()
        today = now.date()
        current_time = now.time()

        # Statistiques générales (basées sur les templates)
        total_courses = teacher.courses.filter(is_active=True).count()
        # Sessions où l'enseignant est assigné directement OU via le cours
        session_templates = ScheduleSession.objects.filter(
            Q(teacher=teacher) | Q(course__teacher=teacher),
            is_cancelled=False
        ).select_related('course', 'room', 'time_slot').distinct()

        # Utiliser les occurrences pour les données réelles
        # Chercher les occurrences où:
        # 1. teacher est directement sur l'occurrence (si modifié)
        # 2. OU teacher est sur le session_template
        # 3. OU teacher est sur le cours (Course.teacher)
        teacher_occurrences = SessionOccurrence.objects.filter(
            Q(teacher=teacher) |
            Q(session_template__teacher=teacher) |
            Q(session_template__course__teacher=teacher),
            is_cancelled=False
        ).select_related(
            'session_template__course',
            'session_template__course__teacher',
            'session_template__teacher',
            'room',
            'teacher'
        ).distinct()

        # Statistiques basées sur les occurrences si disponibles, sinon sur les templates
        if teacher_occurrences.exists():
            total_sessions = teacher_occurrences.count()
            total_hours_per_week = sum(occ.get_duration_hours() for occ in teacher_occurrences[:100])
        else:
            total_sessions = session_templates.count()
            total_hours_per_week = sum(session.get_duration_hours() for session in session_templates)

        # ===== COURS EN COURS (current_session) =====
        current_session = None

        # D'abord chercher dans les occurrences
        current_occurrence = teacher_occurrences.filter(
            actual_date=today,
            start_time__lte=current_time,
            end_time__gte=current_time
        ).first()

        if current_occurrence:
            current_session = {
                'id': current_occurrence.id,
                'course_name': current_occurrence.session_template.course.name if current_occurrence.session_template else 'N/A',
                'course_code': current_occurrence.session_template.course.code if current_occurrence.session_template else 'N/A',
                'room': current_occurrence.room.name if current_occurrence.room else 'N/A',
                'room_code': current_occurrence.room.code if current_occurrence.room else 'N/A',
                'date': today.isoformat(),
                'start_time': current_occurrence.start_time.strftime('%H:%M'),
                'end_time': current_occurrence.end_time.strftime('%H:%M'),
                'session_type': current_occurrence.session_template.session_type if current_occurrence.session_template else 'CM',
                'is_modified': current_occurrence.is_room_modified or current_occurrence.is_time_modified
            }
        else:
            # Fallback: chercher dans les ScheduleSession (templates)
            current_template = session_templates.filter(
                specific_date=today,
                specific_start_time__lte=current_time,
                specific_end_time__gte=current_time
            ).select_related('course', 'room').first()

            if current_template:
                current_session = {
                    'id': current_template.id,
                    'course_name': current_template.course.name if current_template.course else 'N/A',
                    'course_code': current_template.course.code if current_template.course else 'N/A',
                    'room': current_template.room.name if current_template.room else 'N/A',
                    'room_code': current_template.room.code if current_template.room else 'N/A',
                    'date': today.isoformat(),
                    'start_time': current_template.specific_start_time.strftime('%H:%M') if current_template.specific_start_time else 'N/A',
                    'end_time': current_template.specific_end_time.strftime('%H:%M') if current_template.specific_end_time else 'N/A',
                    'session_type': current_template.session_type,
                    'is_modified': False
                }

        # ===== PROCHAIN COURS (next_session) =====
        next_session = None

        # D'abord chercher dans les occurrences
        next_occurrence = teacher_occurrences.filter(
            actual_date=today,
            start_time__gt=current_time
        ).order_by('start_time').first()

        # Si pas de cours aujourd'hui, chercher demain ou après
        if not next_occurrence:
            next_occurrence = teacher_occurrences.filter(
                actual_date__gt=today
            ).order_by('actual_date', 'start_time').first()

        if next_occurrence:
            next_session = {
                'id': next_occurrence.id,
                'course_name': next_occurrence.session_template.course.name if next_occurrence.session_template else 'N/A',
                'course_code': next_occurrence.session_template.course.code if next_occurrence.session_template else 'N/A',
                'room': next_occurrence.room.name if next_occurrence.room else 'N/A',
                'room_code': next_occurrence.room.code if next_occurrence.room else 'N/A',
                'date': next_occurrence.actual_date.isoformat(),
                'day_of_week': ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'][next_occurrence.actual_date.weekday()],
                'start_time': next_occurrence.start_time.strftime('%H:%M'),
                'end_time': next_occurrence.end_time.strftime('%H:%M'),
                'session_type': next_occurrence.session_template.session_type if next_occurrence.session_template else 'CM',
                'is_modified': next_occurrence.is_room_modified or next_occurrence.is_time_modified
            }
        else:
            # Fallback: chercher dans les ScheduleSession (templates)
            # D'abord aujourd'hui après l'heure actuelle
            next_template = session_templates.filter(
                specific_date=today,
                specific_start_time__gt=current_time
            ).select_related('course', 'room').order_by('specific_start_time').first()

            # Sinon chercher les jours suivants
            if not next_template:
                next_template = session_templates.filter(
                    specific_date__gt=today
                ).select_related('course', 'room').order_by('specific_date', 'specific_start_time').first()

            if next_template:
                next_session = {
                    'id': next_template.id,
                    'course_name': next_template.course.name if next_template.course else 'N/A',
                    'course_code': next_template.course.code if next_template.course else 'N/A',
                    'room': next_template.room.name if next_template.room else 'N/A',
                    'room_code': next_template.room.code if next_template.room else 'N/A',
                    'date': next_template.specific_date.isoformat() if next_template.specific_date else 'N/A',
                    'day_of_week': ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'][next_template.specific_date.weekday()] if next_template.specific_date else 'N/A',
                    'start_time': next_template.specific_start_time.strftime('%H:%M') if next_template.specific_start_time else 'N/A',
                    'end_time': next_template.specific_end_time.strftime('%H:%M') if next_template.specific_end_time else 'N/A',
                    'session_type': next_template.session_type,
                    'is_modified': False
                }

        # ===== SESSIONS À VENIR (cette semaine) =====
        week_end = today + timedelta(days=7)
        upcoming_sessions = []

        # Utiliser les occurrences si disponibles
        upcoming_occurrences = teacher_occurrences.filter(
            actual_date__gte=today,
            actual_date__lte=week_end
        ).order_by('actual_date', 'start_time')[:10]

        if upcoming_occurrences.exists():
            for occ in upcoming_occurrences:
                upcoming_sessions.append({
                    'id': occ.id,
                    'course_name': occ.session_template.course.name if occ.session_template else 'N/A',
                    'course_code': occ.session_template.course.code if occ.session_template else 'N/A',
                    'room': occ.room.code if occ.room else 'N/A',
                    'date': occ.actual_date.isoformat(),
                    'day': ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'][occ.actual_date.weekday()],
                    'start_time': occ.start_time.strftime('%H:%M'),
                    'end_time': occ.end_time.strftime('%H:%M'),
                    'session_type': occ.session_template.get_session_type_display() if occ.session_template else 'CM',
                    'is_modified': occ.is_room_modified or occ.is_time_modified or occ.is_teacher_modified
                })
        else:
            # Fallback sur les templates si pas d'occurrences
            for session in session_templates.select_related('course', 'room', 'time_slot')[:10]:
                upcoming_sessions.append({
                    'id': session.id,
                    'course_name': session.course.name,
                    'course_code': session.course.code,
                    'room': session.room.code if session.room else 'N/A',
                    'day': session.time_slot.get_day_of_week_display() if session.time_slot else 'N/A',
                    'start_time': session.time_slot.start_time.strftime('%H:%M') if session.time_slot else 'N/A',
                    'end_time': session.time_slot.end_time.strftime('%H:%M') if session.time_slot else 'N/A',
                    'session_type': session.get_session_type_display(),
                    'is_modified': False
                })

        # Préférences et indisponibilités
        active_preferences_count = teacher.preferences.filter(is_active=True).count()
        pending_unavailabilities_count = teacher.unavailabilities.filter(is_approved=False).count()

        # Demandes de modification
        pending_requests_count = teacher.schedule_requests.filter(status='pending').count()
        recent_requests = teacher.schedule_requests.all()[:5]

        # Retours récents
        recent_feedbacks = teacher.session_feedbacks.all()[:5]

        # Conflits (basés sur les templates pour l'instant)
        conflicts = []
        conflicts_count = 0
        for session in session_templates[:20]:  # Limiter pour performance
            session_conflicts = session.get_conflicts()
            if session_conflicts.exists():
                conflicts_count += session_conflicts.count()
                for conflict in session_conflicts[:3]:
                    conflicts.append({
                        'id': conflict.id,
                        'type': conflict.get_conflict_type_display(),
                        'severity': conflict.get_severity_display(),
                        'description': conflict.description,
                        'session_id': session.id,
                        'course': session.course.name
                    })

        # Assembler les données du dashboard
        dashboard_data = {
            'teacher': TeacherSerializer(teacher).data,
            'total_courses': total_courses,
            'total_sessions': total_sessions,
            'total_hours_per_week': round(total_hours_per_week, 2),
            'current_session': current_session,  # NOUVEAU: cours en cours
            'next_session': next_session,  # NOUVEAU: prochain cours
            'upcoming_sessions': upcoming_sessions,
            'active_preferences_count': active_preferences_count,
            'pending_unavailabilities_count': pending_unavailabilities_count,
            'pending_requests_count': pending_requests_count,
            'recent_requests': TeacherScheduleRequestSerializer(recent_requests, many=True).data,
            'recent_feedbacks': SessionFeedbackSerializer(recent_feedbacks, many=True).data,
            'conflicts_count': conflicts_count,
            'conflicts': conflicts[:10]
        }

        return Response(dashboard_data)

    @action(detail=True, methods=['get'])
    def ml_insights(self, request, pk=None):
        """
        🤖 INSIGHTS ML pour l'enseignant
        Analyse ML complète de la charge de travail et recommandations personnalisées
        """
        teacher = self.get_object()

        try:
            from ml_engine.simple_ml_service import ml_service

            logger.info(f"🤖 Génération d'insights ML pour l'enseignant {teacher.user.get_full_name()}")

            # 1. Analyse de la charge de travail
            workload_analysis = ml_service.analyze_workload_balance()
            teacher_workload = next(
                (t for t in workload_analysis.get('teachers', [])
                 if t.get('teacher_id') == teacher.id),
                None
            )

            # 2. Recommandations personnalisées
            recommendations = ml_service.generate_personalized_recommendations({
                'type': 'teacher',
                'teacher_id': teacher.id,
                'name': teacher.user.get_full_name()
            })

            # 3. Suggestions de planification
            scheduling_tips = ml_service.generate_schedule_suggestions(
                context=f"teacher_{teacher.id}"
            )

            # 4. Analyse des cours de l'enseignant
            courses = teacher.courses.filter(is_active=True)
            courses_ml_analysis = []

            for course in courses[:10]:  # Limiter à 10 cours
                if course.ml_difficulty_score:
                    courses_ml_analysis.append({
                        'code': course.code,
                        'name': course.name,
                        'difficulty_score': course.ml_difficulty_score,
                        'complexity_level': course.ml_complexity_level,
                        'priority': course.ml_scheduling_priority,
                        'last_updated': course.ml_last_updated
                    })

            # 5. Assembler la réponse
            ml_insights = {
                'teacher': {
                    'id': teacher.id,
                    'name': teacher.user.get_full_name(),
                    'employee_id': teacher.employee_id
                },
                'workload_analysis': teacher_workload or {
                    'message': 'Aucune session planifiée actuellement'
                },
                'personalized_recommendations': recommendations,
                'scheduling_tips': scheduling_tips,
                'courses_ml_analysis': courses_ml_analysis,
                'summary': {
                    'total_courses': courses.count(),
                    'analyzed_courses': len(courses_ml_analysis),
                    'avg_difficulty': round(sum(c['difficulty_score'] for c in courses_ml_analysis) / len(courses_ml_analysis), 2) if courses_ml_analysis else 0,
                    'high_priority_courses': len([c for c in courses_ml_analysis if c['priority'] == 1])
                },
                'generated_at': timezone.now().isoformat()
            }

            logger.info(f"✅ Insights ML générés avec succès pour {teacher.user.get_full_name()}")
            return Response(ml_insights)

        except Exception as e:
            logger.error(f"❌ Erreur lors de la génération d'insights ML: {e}")
            return Response({
                'error': 'Erreur lors de la génération des insights ML',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CourseViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des cours"""
    queryset = Course.objects.all()
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'name', 'code', 'department', 'teacher', 'course_type', 'level', 'credits', 'hours_per_week', 'total_hours', 'semester', 'academic_year']
    import_fields = ['name', 'code', 'department', 'teacher', 'course_type', 'level', 'credits', 'hours_per_week', 'total_hours', 'semester', 'academic_year']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CourseDetailSerializer
        return CourseSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtres
        department_id = self.request.query_params.get('department')
        if department_id:
            queryset = queryset.filter(department_id=department_id)

        # Filtre par enseignant
        teacher_id = self.request.query_params.get('teacher')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        level = self.request.query_params.get('level')
        if level:
            queryset = queryset.filter(level=level)

        course_type = self.request.query_params.get('type')
        if course_type:
            queryset = queryset.filter(course_type=course_type)

        # Filtre de recherche
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search) |
                Q(teacher__user__first_name__icontains=search) |
                Q(teacher__user__last_name__icontains=search)
            )

        return queryset.filter(is_active=True)

    def perform_create(self, serializer):
        """
        ✨ AUTO-PRÉDICTION ML lors de la création d'un cours
        """
        course = serializer.save()

        # Lancer la prédiction ML en arrière-plan
        try:
            logger.info(f"🤖 Déclenchement de l'auto-prédiction ML pour le cours {course.code}")
            prediction = course.update_ml_predictions(force=True)

            if prediction:
                logger.info(f"✅ Prédiction ML réussie pour {course.code}: {course.ml_complexity_level}")
            else:
                logger.warning(f"⚠️ Prédiction ML échouée pour {course.code}")

        except Exception as e:
            # Ne pas bloquer la création du cours si la prédiction échoue
            logger.error(f"❌ Erreur lors de la prédiction ML pour {course.code}: {e}")

        return course

    def perform_update(self, serializer):
        """
        ✨ AUTO-PRÉDICTION ML lors de la mise à jour d'un cours
        """
        course = serializer.save()

        # Mettre à jour les prédictions si les champs impactants sont modifiés
        impactful_fields = [
            'requires_computer', 'requires_laboratory', 'requires_projector',
            'max_students', 'min_room_capacity', 'level', 'teacher',
            'hours_per_week', 'course_type'
        ]

        # Vérifier si un champ impactant a été modifié
        should_update = any(
            field in serializer.validated_data for field in impactful_fields
        )

        if should_update:
            try:
                logger.info(f"🤖 Mise à jour des prédictions ML pour {course.code}")
                course.update_ml_predictions(force=True)
            except Exception as e:
                logger.error(f"❌ Erreur lors de la mise à jour ML pour {course.code}: {e}")

        return course

    @action(detail=True, methods=['post'])
    def refresh_ml_predictions(self, request, pk=None):
        """
        🔄 Force le rafraîchissement des prédictions ML
        """
        course = self.get_object()

        try:
            prediction = course.update_ml_predictions(force=True)

            if prediction:
                return Response({
                    'success': True,
                    'message': f'Prédictions ML mises à jour pour {course.code}',
                    'prediction': {
                        'difficulty_score': course.ml_difficulty_score,
                        'complexity_level': course.ml_complexity_level,
                        'priority': course.ml_scheduling_priority,
                        'last_updated': course.ml_last_updated,
                        'metadata': course.ml_prediction_metadata
                    }
                })
            else:
                return Response({
                    'success': False,
                    'message': 'Échec de la mise à jour des prédictions ML'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques générales des cours"""
        from django.db.models import Sum

        active_courses = Course.objects.filter(is_active=True)
        all_courses = Course.objects.all()

        total_courses = all_courses.count()
        active_courses_count = active_courses.count()

        # Calculer le total des heures
        total_hours_data = active_courses.aggregate(total=Sum('total_hours'))
        total_hours = total_hours_data['total'] or 0

        # Compter les enseignants uniques
        unique_teachers = active_courses.values('teacher').distinct().count()

        # Répartition par type
        by_type = active_courses.values('course_type').annotate(
            count=Count('id')
        )

        # Répartition par niveau
        by_level = active_courses.values('level').annotate(
            count=Count('id')
        )

        # Répartition par département
        by_department = active_courses.values(
            'department__name', 'department__code'
        ).annotate(count=Count('id'))

        # Moyennes
        avg_hours = active_courses.aggregate(
            avg_hours_per_week=Avg('hours_per_week'),
            avg_total_hours=Avg('total_hours'),
            avg_credits=Avg('credits')
        )

        return Response({
            'total_courses': total_courses,
            'active_courses': active_courses_count,
            'total_hours': total_hours,
            'teachers_count': unique_teachers,
            'by_type': list(by_type),
            'by_level': list(by_level),
            'by_department': list(by_department),
            'averages': avg_hours
        })
    
    @action(detail=True, methods=['get'])
    def enrollments(self, request, pk=None):
        """Inscriptions pour un cours spécifique"""
        course = self.get_object()
        enrollments = CourseEnrollment.objects.filter(
            course=course, 
            is_active=True
        ).select_related('student__user')
        
        data = []
        for enrollment in enrollments:
            data.append({
                'id': enrollment.id,
                'student_id': enrollment.student.student_id,
                'student_name': enrollment.student.user.get_full_name(),
                'enrollment_date': enrollment.enrollment_date,
                'semester': enrollment.semester,
                'academic_year': enrollment.academic_year
            })
        
        return Response({
            'course': course.name,
            'total_enrollments': len(data),
            'enrollments': data
        })
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Dupliquer un cours"""
        original_course = self.get_object()
        
        # Créer une copie du cours
        new_course = Course.objects.create(
            name=f"{original_course.name} (Copie)",
            code=f"{original_course.code}_COPY",
            description=original_course.description,
            department=original_course.department,
            teacher=original_course.teacher,
            course_type=original_course.course_type,
            level=original_course.level,
            credits=original_course.credits,
            hours_per_week=original_course.hours_per_week,
            total_hours=original_course.total_hours,
            max_students=original_course.max_students,
            min_room_capacity=original_course.min_room_capacity,
            requires_computer=original_course.requires_computer,
            requires_projector=original_course.requires_projector,
            requires_laboratory=original_course.requires_laboratory,
            semester=original_course.semester,
            academic_year=original_course.academic_year,
            min_sessions_per_week=original_course.min_sessions_per_week,
            max_sessions_per_week=original_course.max_sessions_per_week,
            preferred_times=original_course.preferred_times,
            unavailable_times=original_course.unavailable_times
        )
        
        serializer = self.get_serializer(new_course)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def toggle_status(self, request, pk=None):
        """Activer/désactiver un cours"""
        course = self.get_object()
        course.is_active = not course.is_active
        course.save()
        
        return Response({
            'id': course.id,
            'is_active': course.is_active,
            'message': f"Cours {'activé' if course.is_active else 'désactivé'} avec succès"
        })
    
    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """Mise à jour en lot de cours"""
        course_ids = request.data.get('course_ids', [])
        update_data = request.data.get('update_data', {})
        
        if not course_ids:
            return Response({'error': 'Aucun cours spécifié'}, status=status.HTTP_400_BAD_REQUEST)
        
        courses = Course.objects.filter(id__in=course_ids)
        updated_count = 0
        
        for course in courses:
            for field, value in update_data.items():
                if hasattr(course, field):
                    setattr(course, field, value)
            course.save()
            updated_count += 1
        
        return Response({
            'updated_count': updated_count,
            'message': f"{updated_count} cours mis à jour avec succès"
        })
    
    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """Suppression en lot de cours"""
        course_ids = request.data.get('course_ids', [])
        
        if not course_ids:
            return Response({'error': 'Aucun cours spécifié'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Soft delete - marquer comme inactif plutôt que supprimer
        updated_count = Course.objects.filter(id__in=course_ids).update(is_active=False)
        
        return Response({
            'deleted_count': updated_count,
            'message': f"{updated_count} cours supprimés avec succès"
        })
    
    @action(detail=True, methods=['get'])
    def conflicts(self, request, pk=None):
        """Détecter les conflits pour un cours spécifique"""
        from schedules.models import ScheduleSession
        course = self.get_object()
        
        # Récupérer les sessions du cours
        sessions = ScheduleSession.objects.filter(
            course=course,
            is_cancelled=False
        ).select_related('time_slot', 'room', 'teacher')
        
        conflicts = []
        
        for session in sessions:
            # Vérifier les conflits de salle
            room_conflicts = ScheduleSession.objects.filter(
                time_slot=session.time_slot,
                room=session.room,
                is_cancelled=False
            ).exclude(id=session.id)
            
            # Vérifier les conflits d'enseignant
            teacher_conflicts = ScheduleSession.objects.filter(
                time_slot=session.time_slot,
                teacher=session.teacher,
                is_cancelled=False
            ).exclude(id=session.id)
            
            if room_conflicts.exists() or teacher_conflicts.exists():
                conflicts.append({
                    'session_id': session.id,
                    'time_slot': {
                        'day': session.time_slot.day_of_week,
                        'start_time': session.time_slot.start_time,
                        'end_time': session.time_slot.end_time
                    },
                    'room_conflicts': [
                        {
                            'course_name': conf.course.name,
                            'teacher': conf.teacher.user.get_full_name()
                        } for conf in room_conflicts
                    ],
                    'teacher_conflicts': [
                        {
                            'course_name': conf.course.name,
                            'room': conf.room.code
                        } for conf in teacher_conflicts
                    ]
                })
        
        return Response({
            'course': course.name,
            'total_conflicts': len(conflicts),
            'conflicts': conflicts
        })

    @action(detail=False, methods=['post'])
    def import_data(self, request):
        """
        Import personnalisé pour les cours acceptant:
        - department_name au lieu de department (ID)
        - teacher_employee_id ou teacher_email au lieu de teacher (ID)
        """
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response(
                {'error': 'Aucun fichier fourni'},
                status=status.HTTP_400_BAD_REQUEST
            )

        format_type = request.data.get('format', 'csv').lower()

        try:
            # Import du fichier selon le format
            if format_type == 'json':
                data = self._import_json(file_obj)
            elif format_type == 'excel':
                data = self._import_excel(file_obj)
            else:  # csv
                data = self._import_csv(file_obj)

            created_count = 0
            updated_count = 0
            errors = []

            for item in data:
                try:
                    # Mapper les noms de colonnes Excel vers les noms de champs attendus
                    field_mapping = {
                        'ID': 'id',
                        'Code': 'code',
                        'Nom du Cours': 'name',
                        'Description': 'description',
                        'Département': 'department_name',
                        'ID Employé Enseignant': 'teacher_employee_id',
                        'Email Enseignant (alternatif)': 'teacher_email',
                        'Type de Cours': 'course_type',
                        'Niveau': 'level',
                        'Crédits': 'credits',
                        'Heures par Semaine': 'hours_per_week',
                        'Heures Totales': 'total_hours',
                        'Max Étudiants': 'max_students',
                        'Capacité Min Salle': 'min_room_capacity',
                        'Nécessite Ordinateur': 'requires_computer',
                        'Nécessite Projecteur': 'requires_projector',
                        'Nécessite Laboratoire': 'requires_laboratory',
                        'Semestre': 'semester',
                        'Année Académique': 'academic_year',
                        'Actif': 'is_active',
                        # Pour le mode auto-génération
                        'Code de Base': 'code',
                        'Nom du Cours de Base': 'name',
                        '% CM': 'cm_percentage',
                        '% TD': 'td_percentage',
                        '% TP': 'tp_percentage',
                        '% TPE': 'tpe_percentage',
                        'Heures par Crédit': 'credit_hours',
                    }

                    # Créer un nouveau dict avec les bons noms de champs
                    normalized_item = {}
                    for key, value in item.items():
                        normalized_key = field_mapping.get(key, key)
                        normalized_item[normalized_key] = value

                    item = normalized_item

                    # Détecter automatiquement le mode en fonction des champs présents
                    auto_generate = 'cm_percentage' in item or 'td_percentage' in item

                    # Extraire les pourcentages et heures par crédit pour le mode auto-génération
                    cm_percentage = float(item.pop('cm_percentage', 40)) if 'cm_percentage' in item else None
                    td_percentage = float(item.pop('td_percentage', 30)) if 'td_percentage' in item else None
                    tp_percentage = float(item.pop('tp_percentage', 20)) if 'tp_percentage' in item else None
                    tpe_percentage = float(item.pop('tpe_percentage', 10)) if 'tpe_percentage' in item else None
                    credit_hours = float(item.pop('credit_hours', 15)) if 'credit_hours' in item else 15

                    # Convertir department_name en department (ID)
                    if 'department_name' in item and item['department_name']:
                        try:
                            dept = Department.objects.get(name=item['department_name'])
                            item['department'] = dept.id
                        except Department.DoesNotExist:
                            errors.append({
                                'data': item,
                                'error': f"Département '{item['department_name']}' introuvable"
                            })
                            continue
                        # Retirer department_name pour éviter les conflits
                        del item['department_name']

                    # Convertir teacher_employee_id ou teacher_email en teacher (ID)
                    teacher_found = False
                    if 'teacher_employee_id' in item and item['teacher_employee_id']:
                        try:
                            teacher = Teacher.objects.get(employee_id=item['teacher_employee_id'])
                            item['teacher'] = teacher.id
                            teacher_found = True
                        except Teacher.DoesNotExist:
                            errors.append({
                                'data': item,
                                'error': f"Enseignant avec employee_id '{item['teacher_employee_id']}' introuvable"
                            })
                            continue
                        del item['teacher_employee_id']

                    if not teacher_found and 'teacher_email' in item and item['teacher_email']:
                        try:
                            from users.models import CustomUser
                            user = CustomUser.objects.get(email=item['teacher_email'])
                            teacher = Teacher.objects.get(user=user)
                            item['teacher'] = teacher.id
                        except (CustomUser.DoesNotExist, Teacher.DoesNotExist):
                            errors.append({
                                'data': item,
                                'error': f"Enseignant avec email '{item['teacher_email']}' introuvable"
                            })
                            continue
                        del item['teacher_email']

                    # Nettoyer le champ course_type (extraire juste le type, ex: "CM (CM, TD...)" -> "CM")
                    if 'course_type' in item and isinstance(item['course_type'], str):
                        # Extraire le premier mot avant l'espace ou la parenthèse
                        course_type_clean = item['course_type'].split()[0].strip()
                        item['course_type'] = course_type_clean

                    # Nettoyer le champ level (extraire juste le niveau, ex: "L1 (L1, L2...)" -> "L1")
                    if 'level' in item and isinstance(item['level'], str):
                        level_clean = item['level'].split()[0].strip()
                        item['level'] = level_clean

                    # Convertir les booléens de string à boolean
                    bool_fields = ['requires_computer', 'requires_projector', 'requires_laboratory', 'is_active']
                    for field in bool_fields:
                        if field in item:
                            if isinstance(item[field], str):
                                item[field] = item[field].lower() in ['true', '1', 'yes', 'oui']

                    # Si mode auto-génération, créer automatiquement CM, TD, TP, TPE
                    if auto_generate:
                        # Calculer le total d'heures basé sur les crédits
                        credits = float(item.get('credits', 6))
                        total_hours = credits * credit_hours

                        # Définir les types de cours à générer avec leurs pourcentages
                        course_types = []
                        if cm_percentage and cm_percentage > 0:
                            course_types.append(('CM', total_hours * cm_percentage / 100))
                        if td_percentage and td_percentage > 0:
                            course_types.append(('TD', total_hours * td_percentage / 100))
                        if tp_percentage and tp_percentage > 0:
                            course_types.append(('TP', total_hours * tp_percentage / 100))
                        if tpe_percentage and tpe_percentage > 0:
                            course_types.append(('TPE', total_hours * tpe_percentage / 100))

                        # Si aucun pourcentage spécifié, utiliser la répartition par défaut
                        if not course_types:
                            course_types = [
                                ('CM', total_hours * 0.40),
                                ('TD', total_hours * 0.30),
                                ('TP', total_hours * 0.20),
                                ('TPE', total_hours * 0.10)
                            ]

                        # Créer chaque type de cours
                        base_code = item.get('code', 'COURS')
                        base_name = item.get('name', 'Cours')

                        for course_type, hours in course_types:
                            course_data = item.copy()
                            course_data['code'] = f"{base_code}_{course_type}"
                            course_data['name'] = f"{base_name} ({course_type})"
                            course_data['course_type'] = course_type
                            course_data['total_hours'] = int(round(hours))  # Arrondir à l'entier
                            course_data['hours_per_week'] = int(round(hours / 14))  # Arrondir à l'entier

                            # Retirer l'ID pour forcer la création
                            if 'id' in course_data:
                                del course_data['id']

                            serializer = self.get_serializer(data=course_data)
                            if serializer.is_valid():
                                serializer.save()
                                created_count += 1
                            else:
                                errors.append({
                                    'data': course_data,
                                    'errors': serializer.errors
                                })

                        # Passer à l'élément suivant
                        continue

                    # Vérifier si on doit créer ou mettre à jour (mode normal, sans auto_generate)
                    course_id = item.get('id')
                    if course_id:
                        try:
                            course = Course.objects.get(id=course_id)
                            serializer = self.get_serializer(course, data=item, partial=True)
                            if serializer.is_valid():
                                serializer.save()
                                updated_count += 1
                            else:
                                errors.append({
                                    'data': item,
                                    'errors': serializer.errors
                                })
                        except Course.DoesNotExist:
                            # Si l'ID n'existe pas, créer un nouveau cours
                            item.pop('id')  # Retirer l'ID pour la création
                            serializer = self.get_serializer(data=item)
                            if serializer.is_valid():
                                serializer.save()
                                created_count += 1
                            else:
                                errors.append({
                                    'data': item,
                                    'errors': serializer.errors
                                })
                    else:
                        # Création d'un nouveau cours
                        serializer = self.get_serializer(data=item)
                        if serializer.is_valid():
                            serializer.save()
                            created_count += 1
                        else:
                            errors.append({
                                'data': item,
                                'errors': serializer.errors
                            })

                except Exception as e:
                    errors.append({
                        'data': item,
                        'error': str(e)
                    })

            return Response({
                'message': f'{created_count} cours créé(s), {updated_count} cours mis à jour',
                'created_count': created_count,
                'updated_count': updated_count,
                'error_count': len(errors),
                'errors': errors[:10]  # Limiter les erreurs retournées
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': f'Erreur lors de l\'import: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


class CurriculumViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des curriculums"""
    queryset = Curriculum.objects.all()
    permission_classes = []  # Temporairement désactivé pour les tests

    export_fields = ['id', 'name', 'code', 'department', 'level', 'total_credits', 'academic_year', 'is_active']
    import_fields = ['name', 'code', 'department', 'level', 'total_credits', 'academic_year']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CurriculumDetailSerializer
        return CurriculumSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        department_id = self.request.query_params.get('department')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        return queryset.filter(is_active=True)


class StudentViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des étudiants"""
    queryset = Student.objects.all()
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'student_id', 'curriculum', 'current_level', 'entry_year', 'is_active']
    import_fields = ['student_id', 'curriculum', 'current_level', 'entry_year']

    def get_serializer_class(self):
        if self.action == 'create':
            return StudentCreateSerializer
        return StudentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        curriculum_id = self.request.query_params.get('curriculum')
        if curriculum_id:
            queryset = queryset.filter(curriculum_id=curriculum_id)
        return queryset.filter(is_active=True)

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Récupérer le profil de l'étudiant connecté"""
        try:
            student = Student.objects.select_related(
                'user', 'curriculum', 'curriculum__department'
            ).get(user=request.user, is_active=True)
            serializer = self.get_serializer(student)
            return Response(serializer.data)
        except Student.DoesNotExist:
            return Response(
                {'error': 'Aucun profil étudiant trouvé pour cet utilisateur'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['patch'])
    def update_me(self, request):
        """Mettre à jour le profil de l'étudiant connecté"""
        try:
            student = Student.objects.get(user=request.user, is_active=True)
            # Seuls certains champs peuvent être mis à jour par l'étudiant
            allowed_fields = ['phone', 'address', 'emergency_contact', 'emergency_phone']
            update_data = {k: v for k, v in request.data.items() if k in allowed_fields}

            for field, value in update_data.items():
                setattr(student, field, value)
            student.save()

            serializer = self.get_serializer(student)
            return Response(serializer.data)
        except Student.DoesNotExist:
            return Response(
                {'error': 'Aucun profil étudiant trouvé pour cet utilisateur'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'])
    def my_stats(self, request):
        """Statistiques de l'étudiant connecté"""
        try:
            student = Student.objects.get(user=request.user, is_active=True)
            enrollments = CourseEnrollment.objects.filter(
                student=student,
                is_active=True
            ).select_related('course')

            total_courses = enrollments.count()
            total_credits = sum(e.course.credits for e in enrollments)
            total_hours = sum(e.course.hours_per_week for e in enrollments)

            # Cours par type
            courses_by_type = {}
            for enrollment in enrollments:
                course_type = enrollment.course.course_type
                courses_by_type[course_type] = courses_by_type.get(course_type, 0) + 1

            return Response({
                'total_courses': total_courses,
                'total_credits': total_credits,
                'total_hours_per_week': total_hours,
                'courses_by_type': courses_by_type,
            })
        except Student.DoesNotExist:
            return Response(
                {'error': 'Aucun profil étudiant trouvé pour cet utilisateur'},
                status=status.HTTP_404_NOT_FOUND
            )


class CourseEnrollmentViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des inscriptions"""
    queryset = CourseEnrollment.objects.all()
    serializer_class = CourseEnrollmentSerializer
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'student', 'course', 'semester', 'academic_year', 'enrollment_date']
    import_fields = ['student', 'course', 'semester', 'academic_year']

    def get_queryset(self):
        queryset = super().get_queryset()

        student_id = self.request.query_params.get('student')
        if student_id:
            queryset = queryset.filter(student_id=student_id)

        course_id = self.request.query_params.get('course')
        if course_id:
            queryset = queryset.filter(course_id=course_id)

        return queryset.filter(is_active=True)

    @action(detail=False, methods=['get'])
    def my_enrollments(self, request):
        """Récupérer les inscriptions de l'étudiant connecté"""
        try:
            student = Student.objects.get(user=request.user, is_active=True)
            enrollments = CourseEnrollment.objects.filter(
                student=student,
                is_active=True
            ).select_related('course', 'course__department').order_by('course__name')

            serializer = self.get_serializer(enrollments, many=True)
            return Response({'results': serializer.data})
        except Student.DoesNotExist:
            return Response(
                {'error': 'Aucun profil étudiant trouvé pour cet utilisateur'},
                status=status.HTTP_404_NOT_FOUND
            )


class CoursePrerequisiteViewSet(ImportExportMixin, viewsets.ModelViewSet):
    """ViewSet pour la gestion des prérequis"""
    queryset = CoursePrerequisite.objects.all()
    serializer_class = CoursePrerequisiteSerializer
    permission_classes = [IsAuthenticated]

    export_fields = ['id', 'course', 'prerequisite_course', 'is_mandatory']
    import_fields = ['course', 'prerequisite_course', 'is_mandatory']


class TeacherPreferenceViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des préférences des enseignants"""
    queryset = TeacherPreference.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return TeacherPreferenceCreateSerializer
        return TeacherPreferenceSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrer par enseignant
        teacher_id = self.request.query_params.get('teacher')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        # Filtrer par type de préférence
        preference_type = self.request.query_params.get('preference_type')
        if preference_type:
            queryset = queryset.filter(preference_type=preference_type)

        # Filtrer par priorité
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)

        # Filtrer par statut actif
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active_bool)

        return queryset.order_by('teacher', 'priority', 'preference_type')

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Active/désactive une préférence"""
        preference = self.get_object()
        preference.is_active = not preference.is_active
        preference.save()

        return Response({
            'message': f'Préférence {"activée" if preference.is_active else "désactivée"}',
            'is_active': preference.is_active
        })

    @action(detail=False, methods=['get'])
    def by_teacher(self, request):
        """Récupère toutes les préférences groupées par enseignant"""
        from django.db.models import Q

        teacher_id = request.query_params.get('teacher_id')
        if not teacher_id:
            return Response({
                'error': 'teacher_id est requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        preferences = TeacherPreference.objects.filter(
            teacher_id=teacher_id,
            is_active=True
        )

        # Grouper par type
        grouped = {}
        for pref in preferences:
            pref_type = pref.get_preference_type_display()
            if pref_type not in grouped:
                grouped[pref_type] = []
            grouped[pref_type].append(TeacherPreferenceSerializer(pref).data)

        return Response({
            'teacher_id': teacher_id,
            'preferences': grouped
        })


class TeacherUnavailabilityViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des indisponibilités des enseignants"""
    queryset = TeacherUnavailability.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return TeacherUnavailabilityCreateSerializer
        return TeacherUnavailabilitySerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrer par enseignant
        teacher_id = self.request.query_params.get('teacher')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        # Filtrer par type d'indisponibilité
        unavailability_type = self.request.query_params.get('unavailability_type')
        if unavailability_type:
            queryset = queryset.filter(unavailability_type=unavailability_type)

        # Filtrer par statut d'approbation
        is_approved = self.request.query_params.get('is_approved')
        if is_approved is not None:
            is_approved_bool = is_approved.lower() == 'true'
            queryset = queryset.filter(is_approved=is_approved_bool)

        return queryset.order_by('-created_at')

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approuve une indisponibilité"""
        unavailability = self.get_object()

        if unavailability.is_approved:
            return Response({
                'message': 'Cette indisponibilité est déjà approuvée'
            }, status=status.HTTP_400_BAD_REQUEST)

        unavailability.is_approved = True
        unavailability.approved_by = request.user
        unavailability.save()

        return Response({
            'message': 'Indisponibilité approuvée avec succès',
            'data': TeacherUnavailabilitySerializer(unavailability).data
        })

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Rejette une indisponibilité"""
        unavailability = self.get_object()

        if unavailability.is_approved:
            return Response({
                'message': 'Cette indisponibilité est déjà approuvée'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Supprimer l'indisponibilité rejetée
        unavailability.delete()

        return Response({
            'message': 'Indisponibilité rejetée et supprimée'
        })

    @action(detail=False, methods=['get'])
    def pending_approvals(self, request):
        """Récupère les indisponibilités en attente d'approbation"""
        pending = TeacherUnavailability.objects.filter(is_approved=False)
        serializer = self.get_serializer(pending, many=True)

        return Response({
            'count': pending.count(),
            'unavailabilities': serializer.data
        })

    @action(detail=False, methods=['get'])
    def by_teacher(self, request):
        """Récupère toutes les indisponibilités d'un enseignant"""
        teacher_id = request.query_params.get('teacher_id')
        if not teacher_id:
            return Response({
                'error': 'teacher_id est requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        unavailabilities = TeacherUnavailability.objects.filter(
            teacher_id=teacher_id,
            is_approved=True
        )

        # Grouper par type
        grouped = {}
        for unavail in unavailabilities:
            unavail_type = unavail.get_unavailability_type_display()
            if unavail_type not in grouped:
                grouped[unavail_type] = []
            grouped[unavail_type].append(TeacherUnavailabilitySerializer(unavail).data)

        return Response({
            'teacher_id': teacher_id,
            'unavailabilities': grouped
        })


class TeacherScheduleRequestViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des demandes de modification d'emploi du temps"""
    queryset = TeacherScheduleRequest.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return TeacherScheduleRequestCreateSerializer
        return TeacherScheduleRequestSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrer par enseignant
        teacher_id = self.request.query_params.get('teacher')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        # Filtrer par type de demande
        request_type = self.request.query_params.get('request_type')
        if request_type:
            queryset = queryset.filter(request_type=request_type)

        # Filtrer par statut
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        # Filtrer par priorité
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)

        return queryset.select_related('teacher__user', 'session', 'reviewed_by')

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approuve une demande de modification"""
        from django.utils import timezone

        schedule_request = self.get_object()

        if schedule_request.status in ['approved', 'completed']:
            return Response({
                'message': 'Cette demande a déjà été approuvée'
            }, status=status.HTTP_400_BAD_REQUEST)

        schedule_request.status = 'approved'
        schedule_request.reviewed_by = request.user
        schedule_request.reviewed_at = timezone.now()
        schedule_request.review_notes = request.data.get('review_notes', '')
        schedule_request.save()

        return Response({
            'message': 'Demande approuvée avec succès',
            'data': TeacherScheduleRequestSerializer(schedule_request).data
        })

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Rejette une demande de modification"""
        from django.utils import timezone

        schedule_request = self.get_object()

        if schedule_request.status in ['approved', 'completed']:
            return Response({
                'message': 'Cette demande a déjà été traitée'
            }, status=status.HTTP_400_BAD_REQUEST)

        schedule_request.status = 'rejected'
        schedule_request.reviewed_by = request.user
        schedule_request.reviewed_at = timezone.now()
        schedule_request.review_notes = request.data.get('review_notes', 'Demande rejetée')
        schedule_request.save()

        return Response({
            'message': 'Demande rejetée',
            'data': TeacherScheduleRequestSerializer(schedule_request).data
        })

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Marque une demande comme complétée après implémentation"""
        schedule_request = self.get_object()

        if schedule_request.status != 'approved':
            return Response({
                'message': 'Seules les demandes approuvées peuvent être marquées comme complétées'
            }, status=status.HTTP_400_BAD_REQUEST)

        schedule_request.status = 'completed'
        schedule_request.save()

        return Response({
            'message': 'Demande marquée comme complétée',
            'data': TeacherScheduleRequestSerializer(schedule_request).data
        })

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Récupère toutes les demandes en attente"""
        pending_requests = TeacherScheduleRequest.objects.filter(status='pending')
        serializer = self.get_serializer(pending_requests, many=True)

        return Response({
            'count': pending_requests.count(),
            'requests': serializer.data
        })

    @action(detail=False, methods=['get'])
    def by_teacher(self, request):
        """Récupère toutes les demandes d'un enseignant"""
        teacher_id = request.query_params.get('teacher_id')
        if not teacher_id:
            return Response({
                'error': 'teacher_id est requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        requests = TeacherScheduleRequest.objects.filter(teacher_id=teacher_id)

        # Grouper par statut
        grouped = {}
        for req in requests:
            req_status = req.get_status_display()
            if req_status not in grouped:
                grouped[req_status] = []
            grouped[req_status].append(TeacherScheduleRequestSerializer(req).data)

        return Response({
            'teacher_id': teacher_id,
            'total_requests': requests.count(),
            'requests_by_status': grouped
        })


class SessionFeedbackViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des retours sur les sessions"""
    queryset = SessionFeedback.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return SessionFeedbackCreateSerializer
        return SessionFeedbackSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrer par enseignant
        teacher_id = self.request.query_params.get('teacher')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        # Filtrer par session
        session_id = self.request.query_params.get('session')
        if session_id:
            queryset = queryset.filter(session_id=session_id)

        # Filtrer par type de retour
        feedback_type = self.request.query_params.get('feedback_type')
        if feedback_type:
            queryset = queryset.filter(feedback_type=feedback_type)

        # Filtrer par statut de résolution
        is_resolved = self.request.query_params.get('is_resolved')
        if is_resolved is not None:
            is_resolved_bool = is_resolved.lower() == 'true'
            queryset = queryset.filter(is_resolved=is_resolved_bool)

        return queryset.select_related('teacher__user', 'session', 'resolved_by')

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Marque un retour comme résolu"""
        from django.utils import timezone

        feedback = self.get_object()

        if feedback.is_resolved:
            return Response({
                'message': 'Ce retour est déjà résolu'
            }, status=status.HTTP_400_BAD_REQUEST)

        feedback.is_resolved = True
        feedback.resolved_by = request.user
        feedback.resolved_at = timezone.now()
        feedback.resolution_notes = request.data.get('resolution_notes', '')
        feedback.save()

        return Response({
            'message': 'Retour marqué comme résolu',
            'data': SessionFeedbackSerializer(feedback).data
        })

    @action(detail=False, methods=['get'])
    def unresolved(self, request):
        """Récupère tous les retours non résolus"""
        unresolved_feedbacks = SessionFeedback.objects.filter(is_resolved=False)

        # Filtrer par sévérité si spécifié
        severity = request.query_params.get('severity')
        if severity:
            unresolved_feedbacks = unresolved_feedbacks.filter(severity=severity)

        # Trier par sévérité critique d'abord
        severity_order = {'critical': 1, 'high': 2, 'medium': 3, 'low': 4}
        unresolved_list = list(unresolved_feedbacks)
        unresolved_list.sort(key=lambda x: severity_order.get(x.severity, 5))

        serializer = self.get_serializer(unresolved_list, many=True)

        return Response({
            'count': len(unresolved_list),
            'feedbacks': serializer.data
        })

    @action(detail=False, methods=['get'])
    def by_teacher(self, request):
        """Récupère tous les retours d'un enseignant"""
        teacher_id = request.query_params.get('teacher_id')
        if not teacher_id:
            return Response({
                'error': 'teacher_id est requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        feedbacks = SessionFeedback.objects.filter(teacher_id=teacher_id)

        # Grouper par type
        grouped = {}
        for feedback in feedbacks:
            fb_type = feedback.get_feedback_type_display()
            if fb_type not in grouped:
                grouped[fb_type] = []
            grouped[fb_type].append(SessionFeedbackSerializer(feedback).data)

        return Response({
            'teacher_id': teacher_id,
            'total_feedbacks': feedbacks.count(),
            'feedbacks_by_type': grouped
        })

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Statistiques sur les retours"""
        total_feedbacks = SessionFeedback.objects.count()
        resolved_count = SessionFeedback.objects.filter(is_resolved=True).count()
        unresolved_count = SessionFeedback.objects.filter(is_resolved=False).count()

        # Par type
        by_type = {}
        for choice in SessionFeedback.FEEDBACK_TYPE_CHOICES:
            type_code = choice[0]
            type_label = choice[1]
            count = SessionFeedback.objects.filter(feedback_type=type_code).count()
            by_type[type_label] = count

        # Par sévérité (pour les problèmes uniquement)
        by_severity = {}
        issues = SessionFeedback.objects.filter(feedback_type='issue')
        for severity_choice in [('low', 'Faible'), ('medium', 'Moyenne'), ('high', 'Élevée'), ('critical', 'Critique')]:
            sev_code = severity_choice[0]
            sev_label = severity_choice[1]
            count = issues.filter(severity=sev_code).count()
            by_severity[sev_label] = count

        return Response({
            'total_feedbacks': total_feedbacks,
            'resolved_count': resolved_count,
            'unresolved_count': unresolved_count,
            'resolution_rate': round((resolved_count / total_feedbacks * 100) if total_feedbacks > 0 else 0, 2),
            'by_type': by_type,
            'by_severity': by_severity
        })
