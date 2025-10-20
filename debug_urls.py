import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oapet_schedule_backend.settings')
django.setup()

from schedules.models import Schedule
from schedules.views import ScheduleViewSet
from rest_framework.test import APIRequestFactory
from django.contrib.auth.models import User

# Create a fake request
factory = APIRequestFactory()
request = factory.get('/api/schedules/8/course_coverage/')

# Get or create a user for the request
user, _ = User.objects.get_or_create(username='test', defaults={'is_staff': True, 'is_superuser': True})
request.user = user

# Create viewset instance
viewset = ScheduleViewSet()
viewset.request = request
viewset.format_kwarg = None
viewset.kwargs = {'pk': '8'}

print("=" * 60)
print("TESTING course_coverage ACTION DIRECTLY")
print("=" * 60)

try:
    # Check if schedule exists
    schedule = Schedule.objects.get(pk=8)
    print(f"Schedule exists: {schedule.name}")
    print(f"Student class: {schedule.student_class}")

    # Call the action
    print("\nCalling course_coverage action...")
    response = viewset.course_coverage(request, pk=8)

    print(f"\nStatus Code: {response.status_code}")
    print(f"Response Data:")
    print(response.data)

except Schedule.DoesNotExist:
    print("ERROR: Schedule with pk=8 does not exist!")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
