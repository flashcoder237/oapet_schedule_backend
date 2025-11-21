#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script pour publier l'emploi du temps
"""
import os
import sys
import django

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oapet_schedule_backend.settings')
django.setup()

from schedules.models import Schedule

print("=" * 70)
print("PUBLICATION DE L'EMPLOI DU TEMPS")
print("=" * 70)

# Récupérer l'emploi du temps EM1
schedule = Schedule.objects.get(id=38)

print(f"\n📅 Emploi du temps: {schedule.name}")
print(f"   Classe: {schedule.student_class.code} - {schedule.student_class.name}")
print(f"   Période: {schedule.academic_period}")
print(f"   Statut actuel: {'Publié' if schedule.is_published else 'Non publié'}")

if not schedule.is_published:
    schedule.is_published = True
    schedule.save()
    print(f"\n✅ Emploi du temps publié avec succès!")
else:
    print(f"\n✅ L'emploi du temps est déjà publié")

print("\n" + "=" * 70)
print("🎉 Les étudiants peuvent maintenant voir leur emploi du temps!")
print("=" * 70)
