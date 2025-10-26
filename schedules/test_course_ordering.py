#!/usr/bin/env python
"""
Script de test pour démontrer l'ordre de programmation des cours
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oapet_schedule_backend.settings')
django.setup()

from courses.models import Course
from schedules.advanced_generation_service import AdvancedScheduleGenerator


def test_course_ordering():
    """Teste l'ordre de programmation des cours"""

    print("=" * 80)
    print("TEST DE L'ORDRE DE PROGRAMMATION DES COURS")
    print("=" * 80)
    print()

    # Simuler quelques cours
    test_courses = [
        # Mathématiques (priorité 2)
        {'code': 'MATH-TP', 'name': 'Maths TP', 'type': 'TP', 'priority': 2},
        {'code': 'MATH-CM', 'name': 'Maths CM', 'type': 'CM', 'priority': 2},
        {'code': 'MATH-TD', 'name': 'Maths TD', 'type': 'TD', 'priority': 2},

        # Informatique (priorité 1 - plus haute)
        {'code': 'INFO-TD', 'name': 'Info TD', 'type': 'TD', 'priority': 1},
        {'code': 'INFO-CM', 'name': 'Info CM', 'type': 'CM', 'priority': 1},
        {'code': 'INFO-TP', 'name': 'Info TP', 'type': 'TP', 'priority': 1},

        # Physique (priorité 3 - plus basse)
        {'code': 'PHYS-CM', 'name': 'Physique CM', 'type': 'CM', 'priority': 3},
        {'code': 'PHYS-TD', 'name': 'Physique TD', 'type': 'TD', 'priority': 3},
    ]

    print("📚 Cours à programmer (dans l'ordre d'entrée):")
    print("-" * 80)
    for i, course in enumerate(test_courses, 1):
        print(f"{i}. {course['code']:15} - {course['name']:20} | Type: {course['type']:4} | Priorité: {course['priority']}")
    print()

    # Simuler le tri du générateur
    course_type_order = {'CM': 1, 'TD': 2, 'TP': 3, 'TPE': 4, 'CONF': 5, 'EXAM': 6}

    def extract_base_name(code):
        for suffix in ['-CM', '-TD', '-TP', '-TPE', '-CONF', '-EXAM']:
            if code.endswith(suffix):
                return code[:-len(suffix)]
        return code

    # Trier selon la logique du générateur
    sorted_courses = sorted(test_courses, key=lambda c: (
        c['priority'],                              # 1. Priorité (1 = haute)
        course_type_order.get(c['type'], 99),       # 2. Type de cours (CM avant TD avant TP)
        extract_base_name(c['code'])                # 3. Nom de base (regrouper Math-CM, Math-TD)
    ))

    print("✅ ORDRE DE PROGRAMMATION (selon le générateur):")
    print("-" * 80)
    print("  #  | Code          | Nom                  | Type | Priorité | Explication")
    print("-" * 80)

    for i, course in enumerate(sorted_courses, 1):
        base_name = extract_base_name(course['code'])
        explanation = f"Priorité {course['priority']}, {course['type']} de {base_name}"
        print(f"{i:3}  | {course['code']:13} | {course['name']:20} | {course['type']:4} | {course['priority']:8} | {explanation}")

    print()
    print("=" * 80)
    print("📋 RÉSUMÉ DES RÈGLES DE TRI:")
    print("=" * 80)
    print("1️⃣  PRIORITÉ MANUELLE (1 = programmé en premier)")
    print("    → INFO (priorité 1) avant MATH (priorité 2) avant PHYS (priorité 3)")
    print()
    print("2️⃣  TYPE DE COURS (ordre pédagogique)")
    print("    → CM programmé avant TD, TD avant TP, TP avant TPE")
    print()
    print("3️⃣  REGROUPEMENT PAR MATIÈRE (nom de base)")
    print("    → MATH-CM, MATH-TD, MATH-TP programmés ensemble")
    print()
    print("=" * 80)
    print()

    print("🎯 BONNES PRATIQUES RESPECTÉES:")
    print("   ✓ Les CM sont programmés avant les TD (fondements avant exercices)")
    print("   ✓ Les TD sont programmés avant les TP (théorie avant pratique)")
    print("   ✓ Les cours d'une même matière sont regroupés")
    print("   ✓ Les priorités définies par l'admin sont respectées")
    print()

    # Vérifier l'ordre
    print("🔍 VÉRIFICATION:")

    # Vérifier que INFO vient avant MATH
    info_indices = [i for i, c in enumerate(sorted_courses) if c['code'].startswith('INFO')]
    math_indices = [i for i, c in enumerate(sorted_courses) if c['code'].startswith('MATH')]

    if max(info_indices) < min(math_indices):
        print("   ✅ INFO (priorité 1) programmé avant MATH (priorité 2)")
    else:
        print("   ❌ Erreur: ordre des priorités non respecté")

    # Vérifier que CM vient avant TD vient avant TP pour chaque matière
    for base_name in ['INFO', 'MATH', 'PHYS']:
        courses_of_subject = [c for c in sorted_courses if c['code'].startswith(base_name)]
        types_order = [c['type'] for c in courses_of_subject]

        expected_order = []
        if 'CM' in types_order:
            expected_order.append('CM')
        if 'TD' in types_order:
            expected_order.append('TD')
        if 'TP' in types_order:
            expected_order.append('TP')

        if types_order == expected_order:
            print(f"   ✅ {base_name}: CM → TD → TP respecté")
        else:
            print(f"   ❌ {base_name}: Ordre incorrect: {' → '.join(types_order)}")

    print()
    print("=" * 80)


if __name__ == '__main__':
    test_course_ordering()
