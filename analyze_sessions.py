import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oapet_schedule_backend.settings')
django.setup()

from schedules.models import Schedule

schedule = Schedule.objects.get(id=8)
print(f"Schedule: {schedule.name}")
print(f"Student Class: {schedule.student_class}")
print(f"Total sessions: {schedule.sessions.count()}")

# Get first course
from courses.models_class import ClassCourse
class_courses = ClassCourse.objects.filter(
    student_class=schedule.student_class,
    is_active=True
).select_related('course')[:1]

if class_courses:
    class_course = class_courses[0]
    course = class_course.course

    print(f"\n=== Analyzing course: {course.code} - {course.name} ===")
    print(f"Required hours: {course.total_hours}h")

    sessions = schedule.sessions.filter(course=course)
    print(f"Number of sessions: {sessions.count()}")

    # Show first 5 sessions
    print("\nFirst 5 sessions:")
    for i, session in enumerate(sessions[:5]):
        print(f"\nSession {i+1}:")
        print(f"  - Room: {session.room}")
        print(f"  - Teacher: {session.teacher}")
        print(f"  - Start: {session.specific_start_time}")
        print(f"  - End: {session.specific_end_time}")
        if hasattr(session, 'day_of_week'):
            print(f"  - Day: {session.day_of_week}")
        if hasattr(session, 'week_number'):
            print(f"  - Week: {session.week_number}")
        if hasattr(session, 'date'):
            print(f"  - Date: {session.date}")

        # Show all fields
        print(f"  - All fields: {[f.name for f in session._meta.fields]}")
