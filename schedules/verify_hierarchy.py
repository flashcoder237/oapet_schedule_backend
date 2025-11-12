"""
Script de vérification de la hiérarchie pédagogique CM → TD → TP → TPE

Usage:
    python manage.py shell < schedules/verify_hierarchy.py

Ou depuis le shell:
    from schedules.verify_hierarchy import verify_schedule_hierarchy
    verify_schedule_hierarchy(schedule_id=1)
"""

from datetime import timedelta
from collections import defaultdict
from schedules.models import Schedule, ScheduleSession


def verify_schedule_hierarchy(schedule_id: int):
    """
    Vérifie qu'un emploi du temps respecte la hiérarchie pédagogique

    Args:
        schedule_id: ID de l'emploi du temps à vérifier

    Returns:
        Dict avec résultats de la vérification
    """
    try:
        schedule = Schedule.objects.get(id=schedule_id)
    except Schedule.DoesNotExist:
        print(f"❌ Emploi du temps {schedule_id} non trouvé")
        return None

    print(f"\n{'='*70}")
    print(f"🔍 VÉRIFICATION HIÉRARCHIE PÉDAGOGIQUE")
    print(f"{'='*70}")
    print(f"Emploi du temps : {schedule.name}")
    print(f"Classe          : {schedule.class_instance.name}")
    print(f"{'='*70}\n")

    # Récupérer toutes les sessions par cours
    sessions = ScheduleSession.objects.filter(
        schedule=schedule
    ).select_related('course').order_by('course_id', 'specific_date', 'specific_start_time')

    if not sessions.exists():
        print("⚠️  Aucune session trouvée dans cet emploi du temps")
        return None

    # Grouper par cours
    course_sessions = defaultdict(list)
    for session in sessions:
        course_sessions[session.course].append(session)

    print(f"📊 ANALYSE PAR COURS ({len(course_sessions)} cours)\n")

    violations = []
    stats = {
        'total_courses': len(course_sessions),
        'courses_with_violations': 0,
        'total_violations': 0,
        'courses_respecting_hierarchy': 0,
    }

    for course, course_sessions_list in course_sessions.items():
        print(f"📚 Cours : {course.code} - {course.name}")
        print(f"   Sessions : {len(course_sessions_list)}")

        # Analyser la séquence
        sequence = []
        types_dates = defaultdict(list)

        for session in course_sessions_list:
            sequence.append({
                'type': session.session_type,
                'date': session.specific_date,
                'time': session.specific_start_time
            })
            types_dates[session.session_type].append(session.specific_date)

        # Compter les types
        type_counts = defaultdict(int)
        for s in sequence:
            type_counts[s['type']] += 1

        print(f"   Types     : CM={type_counts.get('CM', 0)}, "
              f"TD={type_counts.get('TD', 0)}, "
              f"TP={type_counts.get('TP', 0)}, "
              f"TPE={type_counts.get('TPE', 0)}")

        # Vérifier hiérarchie
        course_violations = []

        # Règle 1: Premier cours doit être CM
        if sequence and sequence[0]['type'] != 'CM':
            violation = f"❌ Premier cours n'est pas un CM (c'est un {sequence[0]['type']})"
            course_violations.append(violation)

        # Règle 2: TD ne peut pas arriver avant CM
        if types_dates.get('TD') and types_dates.get('CM'):
            first_cm_date = min(types_dates['CM'])
            first_td_date = min(types_dates['TD'])

            if first_td_date < first_cm_date:
                violation = f"❌ TD avant CM (TD: {first_td_date}, CM: {first_cm_date})"
                course_violations.append(violation)

        # Règle 3: TP ne peut pas arriver avant TD (si TD existe)
        if types_dates.get('TP') and types_dates.get('TD'):
            first_td_date = min(types_dates['TD'])
            first_tp_date = min(types_dates['TP'])

            if first_tp_date < first_td_date:
                violation = f"❌ TP avant TD (TP: {first_tp_date}, TD: {first_td_date})"
                course_violations.append(violation)

        # Règle 4: Vérifier délais minimums entre types
        for i in range(len(sequence) - 1):
            current = sequence[i]
            next_session = sequence[i + 1]

            if current['date'] and next_session['date']:
                days_diff = (next_session['date'] - current['date']).days

                # CM → TD : minimum 1 jour
                if current['type'] == 'CM' and next_session['type'] == 'TD' and days_diff < 1:
                    violation = f"❌ TD trop tôt après CM ({days_diff} jour(s))"
                    course_violations.append(violation)

                # CM → TP : minimum 2 jours
                if current['type'] == 'CM' and next_session['type'] == 'TP' and days_diff < 2:
                    violation = f"❌ TP trop tôt après CM ({days_diff} jour(s))"
                    course_violations.append(violation)

                # TD → TP : minimum 1 jour
                if current['type'] == 'TD' and next_session['type'] == 'TP' and days_diff < 1:
                    violation = f"❌ TP trop tôt après TD ({days_diff} jour(s))"
                    course_violations.append(violation)

                # CM → TPE : minimum 3 jours
                if current['type'] == 'CM' and next_session['type'] == 'TPE' and days_diff < 3:
                    violation = f"❌ TPE trop tôt après CM ({days_diff} jour(s))"
                    course_violations.append(violation)

        # Afficher résultat pour ce cours
        if course_violations:
            print(f"   ❌ VIOLATIONS DÉTECTÉES :")
            for v in course_violations:
                print(f"      {v}")
            violations.extend([(course.code, v) for v in course_violations])
            stats['courses_with_violations'] += 1
            stats['total_violations'] += len(course_violations)
        else:
            print(f"   ✅ Hiérarchie respectée")
            stats['courses_respecting_hierarchy'] += 1

        # Afficher la séquence chronologique
        print(f"   Séquence  : ", end="")
        for i, s in enumerate(sequence[:10]):  # Limiter à 10 pour lisibilité
            print(f"{s['type']}", end="")
            if i < len(sequence) - 1:
                print(" → ", end="")
        if len(sequence) > 10:
            print(f" ... (+{len(sequence) - 10} sessions)")
        else:
            print()

        print()

    # Résumé global
    print(f"\n{'='*70}")
    print(f"📊 RÉSUMÉ GLOBAL")
    print(f"{'='*70}")
    print(f"Total cours analysés       : {stats['total_courses']}")
    print(f"Cours conformes            : {stats['courses_respecting_hierarchy']} "
          f"({stats['courses_respecting_hierarchy']/stats['total_courses']*100:.1f}%)")
    print(f"Cours avec violations      : {stats['courses_with_violations']}")
    print(f"Total violations détectées : {stats['total_violations']}")
    print(f"{'='*70}\n")

    if stats['total_violations'] == 0:
        print("✅ ✅ ✅ HIÉRARCHIE PÉDAGOGIQUE PARFAITEMENT RESPECTÉE ✅ ✅ ✅\n")
        print("Tous les cours suivent la progression : CM → TD → TP → TPE")
        print("Tous les délais minimums sont respectés")
    else:
        print("⚠️  VIOLATIONS DÉTECTÉES\n")
        print("Certains cours ne respectent pas la hiérarchie pédagogique.")
        print("Veuillez vérifier les détails ci-dessus.\n")

    return stats


def verify_all_schedules():
    """Vérifie TOUS les emplois du temps de la base"""
    schedules = Schedule.objects.all()

    print(f"\n{'='*70}")
    print(f"🔍 VÉRIFICATION DE TOUS LES EMPLOIS DU TEMPS")
    print(f"{'='*70}")
    print(f"Total : {schedules.count()} emplois du temps\n")

    global_stats = {
        'total_schedules': schedules.count(),
        'valid_schedules': 0,
        'invalid_schedules': 0,
    }

    for schedule in schedules:
        print(f"Analyse : {schedule.name}...", end=" ")
        stats = verify_schedule_hierarchy(schedule.id)

        if stats and stats['total_violations'] == 0:
            print("✅")
            global_stats['valid_schedules'] += 1
        else:
            print("❌")
            global_stats['invalid_schedules'] += 1

    print(f"\n{'='*70}")
    print(f"📊 RÉSUMÉ GLOBAL TOUS EMPLOIS DU TEMPS")
    print(f"{'='*70}")
    print(f"Total analysés : {global_stats['total_schedules']}")
    print(f"Valides        : {global_stats['valid_schedules']} "
          f"({global_stats['valid_schedules']/max(global_stats['total_schedules'],1)*100:.1f}%)")
    print(f"Invalides      : {global_stats['invalid_schedules']}")
    print(f"{'='*70}\n")


# Pour utilisation directe
if __name__ == "__main__":
    # Vérifier le premier emploi du temps
    schedule = Schedule.objects.first()
    if schedule:
        verify_schedule_hierarchy(schedule.id)
    else:
        print("❌ Aucun emploi du temps trouvé dans la base de données")
