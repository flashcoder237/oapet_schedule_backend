# oapet_schedule_backend/dashboard_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Avg

from courses.models import Course, Teacher, Student, Department
from schedules.models import Schedule, ScheduleSession, Conflict
from rooms.models import Room


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """Endpoint pour les statistiques du tableau de bord"""
    
    # Statistiques générales
    total_students = Student.objects.filter(is_active=True).count()
    total_courses = Course.objects.filter(is_active=True).count()
    total_teachers = Teacher.objects.filter(is_active=True).count()
    total_rooms = Room.objects.filter(is_active=True).count()
    active_schedules = Schedule.objects.filter(is_published=True).count()
    weekly_events = ScheduleSession.objects.filter(is_cancelled=False).count()
    
    # Conflits non résolus
    unresolved_conflicts = Conflict.objects.filter(is_resolved=False).count()
    critical_conflicts = Conflict.objects.filter(
        is_resolved=False, 
        severity='critical'
    ).count()
    
    # Taux d'occupation des salles (estimation)
    total_sessions = ScheduleSession.objects.filter(is_cancelled=False).count()
    total_possible_slots = total_rooms * 50  # 50 créneaux par semaine par salle
    occupancy_rate = (total_sessions / total_possible_slots * 100) if total_possible_slots > 0 else 0
    
    # Répartition des cours par niveau
    courses_by_level = Course.objects.filter(is_active=True).values('level').annotate(
        count=Count('id')
    )
    
    # Répartition des enseignants par département
    teachers_by_department = Teacher.objects.filter(is_active=True).values(
        'department__name', 'department__code'
    ).annotate(count=Count('id'))
    
    # Sessions par type
    sessions_by_type = ScheduleSession.objects.filter(is_cancelled=False).values('session_type').annotate(
        count=Count('id')
    )
    
    return Response({
        'overview': {
            'total_students': total_students,
            'total_courses': total_courses,
            'total_teachers': total_teachers,
            'total_rooms': total_rooms,
            'active_schedules': active_schedules,
            'weekly_events': weekly_events,
            'unresolved_conflicts': unresolved_conflicts,
            'critical_conflicts': critical_conflicts,
            'occupancy_rate': round(occupancy_rate, 2)
        },
        'distributions': {
            'courses_by_level': list(courses_by_level),
            'teachers_by_department': list(teachers_by_department),
            'sessions_by_type': list(sessions_by_type)
        },
        'alerts': {
            'conflicts_needing_attention': unresolved_conflicts,
            'rooms_over_capacity': 0,  # À implémenter selon la logique métier
            'schedules_pending_approval': Schedule.objects.filter(is_published=False).count()
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_health(request):
    """Endpoint pour vérifier la santé du système"""
    
    # Vérifications de base
    total_departments = Department.objects.filter(is_active=True).count()
    departments_with_teachers = Department.objects.filter(
        is_active=True,
        teachers__is_active=True
    ).distinct().count()
    
    # Pourcentage de départements avec des enseignants
    dept_coverage = (departments_with_teachers / total_departments * 100) if total_departments > 0 else 0
    
    # Vérification des conflits
    total_sessions = ScheduleSession.objects.filter(is_cancelled=False).count()
    sessions_with_conflicts = ScheduleSession.objects.filter(
        conflicts_as_conflicting__is_resolved=False
    ).distinct().count()
    
    conflict_rate = (sessions_with_conflicts / total_sessions * 100) if total_sessions > 0 else 0
    
    # Score de santé global (simple heuristique)
    health_score = 100
    if conflict_rate > 10:
        health_score -= 30
    elif conflict_rate > 5:
        health_score -= 15
    
    if dept_coverage < 80:
        health_score -= 20
    elif dept_coverage < 90:
        health_score -= 10
    
    return Response({
        'health_score': max(0, health_score),
        'metrics': {
            'department_coverage': round(dept_coverage, 2),
            'conflict_rate': round(conflict_rate, 2),
            'total_sessions': total_sessions,
            'sessions_with_conflicts': sessions_with_conflicts
        },
        'status': 'healthy' if health_score >= 80 else 'warning' if health_score >= 60 else 'critical'
    })