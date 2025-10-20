import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oapet_schedule_backend.settings')
django.setup()

from schedules.models import Schedule
from courses.models_class import ClassCourse

schedule = Schedule.objects.get(id=8)
class_courses = ClassCourse.objects.filter(
    student_class=schedule.student_class,
    is_active=True
).select_related('course')[:1]

if class_courses:
    course = class_courses[0].course
    sessions = schedule.sessions.filter(course=course)

    print(f"Course: {course.code} - {course.name}")
    print(f"Total sessions: {sessions.count()}")
    print(f"Required hours: {course.total_hours}h")

    # Group by specific_date
    print("\nSessions by date:")
    from collections import Counter
    dates = [s.specific_date for s in sessions if s.specific_date]
    date_counts = Counter(dates)

    for date, count in sorted(date_counts.items())[:10]:
        print(f"  {date}: {count} sessions")

    print(f"\nTotal unique dates: {len(date_counts)}")
    print(f"Sessions without date: {sessions.filter(specific_date__isnull=True).count()}")

    # Check for duplicate sessions (same course, room, time, date)
    print("\nChecking for duplicates...")
    sessions_list = list(sessions.values('specific_date', 'specific_start_time', 'specific_end_time', 'room'))
    unique_sessions = set((s['specific_date'], s['specific_start_time'], s['specific_end_time'], s['room']) for s in sessions_list)
    print(f"Total sessions: {len(sessions_list)}")
    print(f"Unique combinations: {len(unique_sessions)}")
    print(f"Duplicates: {len(sessions_list) - len(unique_sessions)}")
