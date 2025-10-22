# users/management/commands/sync_teachers.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from courses.models import Teacher
from users.models import UserProfile


class Command(BaseCommand):
    help = 'Synchronise les utilisateurs avec le rôle teacher et crée les enregistrements Teacher manquants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche ce qui serait fait sans effectuer les changements',
        )

    def handle(self, *args, **options):
        from courses.models import Department

        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('Mode DRY RUN - Aucune modification ne sera effectuée'))

        # Créer ou récupérer un département par défaut si nécessaire
        default_department = None
        try:
            default_department = Department.objects.get(code='DEFAULT')
        except Department.DoesNotExist:
            if not dry_run:
                default_department = Department.objects.create(
                    code='DEFAULT',
                    name='Département par défaut',
                    description='Département par défaut pour les enseignants sans département assigné'
                )
                self.stdout.write(self.style.SUCCESS('Departement par defaut cree'))
            else:
                self.stdout.write(self.style.WARNING('Un departement par defaut sera cree si necessaire'))

        # Récupérer tous les utilisateurs avec le rôle teacher
        teacher_profiles = UserProfile.objects.filter(role='teacher').select_related('user')

        self.stdout.write(f'\nTrouve {teacher_profiles.count()} profils avec le role "teacher"\n')

        created_count = 0
        already_exists_count = 0

        for profile in teacher_profiles:
            user = profile.user

            # Vérifier si un Teacher existe déjà pour cet utilisateur
            try:
                teacher = Teacher.objects.get(user=user)
                already_exists_count += 1
                self.stdout.write(
                    f'  [OK] Teacher existe deja pour: {user.get_full_name()} ({user.username}) - ID: {teacher.id}'
                )
            except Teacher.DoesNotExist:
                if not dry_run:
                    # Utiliser le département du profil ou le département par défaut
                    dept = profile.department or default_department
                    if not dept:
                        self.stdout.write(
                            self.style.ERROR(
                                f'  [ERREUR] Impossible de creer Teacher pour {user.get_full_name()}: aucun departement disponible'
                            )
                        )
                        continue

                    # Créer le Teacher
                    teacher = Teacher.objects.create(
                        user=user,
                        employee_id=profile.employee_id or f'TEACH-{user.id}',
                        department=dept,
                        is_active=user.is_active
                    )
                    created_count += 1
                    dept_info = f" (dept: {dept.name})" if dept == default_department else ""
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  [CREE] Teacher cree pour: {user.get_full_name()} ({user.username}) - ID: {teacher.id}{dept_info}'
                        )
                    )
                else:
                    created_count += 1
                    dept = profile.department or default_department
                    dept_info = f" avec dept par defaut" if (not profile.department and default_department) else ""
                    self.stdout.write(
                        self.style.WARNING(
                            f'  [A CREER] Teacher serait cree pour: {user.get_full_name()} ({user.username}){dept_info}'
                        )
                    )

        # Résumé
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS(f'\nRESUME:'))
        self.stdout.write(f'  - Teachers deja existants: {already_exists_count}')
        if dry_run:
            self.stdout.write(self.style.WARNING(f'  - Teachers a creer: {created_count}'))
            self.stdout.write(f'\n[ATTENTION] Executez sans --dry-run pour creer les enregistrements')
        else:
            self.stdout.write(self.style.SUCCESS(f'  - Teachers crees: {created_count}'))
        self.stdout.write('=' * 60 + '\n')
