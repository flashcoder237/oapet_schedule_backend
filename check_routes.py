import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oapet_schedule_backend.settings')
django.setup()

from rest_framework.routers import DefaultRouter
from schedules.views import ScheduleViewSet

# Create a router and register the viewset
router = DefaultRouter()
router.register(r'schedules', ScheduleViewSet)

print("=" * 60)
print("REGISTERED ROUTES FOR ScheduleViewSet")
print("=" * 60)

# Get all URL patterns
for pattern in router.urls:
    print(f"\nPattern: {pattern.pattern}")
    print(f"Name: {pattern.name}")
    if hasattr(pattern, 'callback'):
        print(f"View: {pattern.callback}")

print("\n" + "=" * 60)
print("CHECKING FOR course_coverage ACTION")
print("=" * 60)

# Check if course_coverage method exists
if hasattr(ScheduleViewSet, 'course_coverage'):
    method = getattr(ScheduleViewSet, 'course_coverage')
    print(f"✅ course_coverage method exists: {method}")

    # Check if it has the action decorator
    if hasattr(method, 'mapping'):
        print(f"✅ Has mapping: {method.mapping}")
    if hasattr(method, 'detail'):
        print(f"✅ Detail action: {method.detail}")
    if hasattr(method, 'url_path'):
        print(f"✅ URL path: {method.url_path}")
    if hasattr(method, 'url_name'):
        print(f"✅ URL name: {method.url_name}")
else:
    print("❌ course_coverage method NOT found")

print("\n" + "=" * 60)
print("ALL CUSTOM ACTIONS IN ScheduleViewSet")
print("=" * 60)

for attr_name in dir(ScheduleViewSet):
    attr = getattr(ScheduleViewSet, attr_name)
    if hasattr(attr, 'mapping') and hasattr(attr, 'detail'):
        print(f"\n📍 {attr_name}:")
        print(f"   - Detail: {attr.detail}")
        print(f"   - Methods: {attr.mapping}")
        if hasattr(attr, 'url_path'):
            print(f"   - URL path: {attr.url_path}")
