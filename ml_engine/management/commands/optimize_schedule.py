#!/usr/bin/env python3
"""
Commande Django pour optimiser les emplois du temps
==================================================

Usage:
    python manage.py optimize_schedule <schedule_id> [options]
    python manage.py optimize_schedule 1 --algorithm genetic --generations 1000
    python manage.py optimize_schedule 2 --algorithm simulated_annealing --async
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from schedules.models import Schedule
from ml_engine.algorithms import TimetableOptimizer, DEFAULT_GA_CONFIG, DEFAULT_SA_CONFIG
from ml_engine.tasks import optimize_schedule_async


class Command(BaseCommand):
    help = 'Optimise un emploi du temps avec les algorithmes métaheuristiques'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'schedule_id',
            type=int,
            help='ID de l\'emploi du temps à optimiser'
        )
        
        parser.add_argument(
            '--algorithm',
            choices=['genetic', 'simulated_annealing'],
            default='genetic',
            help='Algorithme d\'optimisation à utiliser (défaut: genetic)'
        )
        
        parser.add_argument(
            '--async',
            action='store_true',
            help='Lancer l\'optimisation en arrière-plan avec Celery'
        )
        
        # Paramètres algorithme génétique
        parser.add_argument(
            '--population-size',
            type=int,
            default=100,
            help='Taille de la population (GA) (défaut: 100)'
        )
        
        parser.add_argument(
            '--generations',
            type=int,
            default=500,
            help='Nombre de générations (GA) (défaut: 500)'
        )
        
        parser.add_argument(
            '--crossover-rate',
            type=float,
            default=0.8,
            help='Taux de croisement (GA) (défaut: 0.8)'
        )
        
        parser.add_argument(
            '--mutation-rate',
            type=float,
            default=0.1,
            help='Taux de mutation (GA) (défaut: 0.1)'
        )
        
        parser.add_argument(
            '--elite-size',
            type=int,
            default=10,
            help='Taille de l\'élite (GA) (défaut: 10)'
        )
        
        # Paramètres recuit simulé
        parser.add_argument(
            '--initial-temperature',
            type=float,
            default=1000.0,
            help='Température initiale (SA) (défaut: 1000.0)'
        )
        
        parser.add_argument(
            '--cooling-rate',
            type=float,
            default=0.95,
            help='Taux de refroidissement (SA) (défaut: 0.95)'
        )
        
        parser.add_argument(
            '--min-temperature',
            type=float,
            default=0.01,
            help='Température minimale (SA) (défaut: 0.01)'
        )
        
        parser.add_argument(
            '--max-iterations',
            type=int,
            default=10000,
            help='Nombre maximum d\'itérations (SA) (défaut: 10000)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulation sans appliquer les changements'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Affichage détaillé du processus'
        )
    
    def handle(self, *args, **options):
        schedule_id = options['schedule_id']
        algorithm = options['algorithm']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'🔧 Optimisation de l\'emploi du temps #{schedule_id} avec {algorithm}'
            )
        )
        
        # Vérifier que l'emploi du temps existe
        try:
            schedule = Schedule.objects.get(id=schedule_id)
        except Schedule.DoesNotExist:
            raise CommandError(f"Emploi du temps #{schedule_id} non trouvé")
        
        self.stdout.write(f"📅 Emploi du temps: {schedule.name}")
        self.stdout.write(f"🎯 Niveau: {schedule.level}")
        self.stdout.write(f"📊 Sessions: {schedule.sessions.count()}")
        
        # Préparer les paramètres
        algorithm_params = self._prepare_algorithm_params(algorithm, options)
        
        if options['verbose']:
            self.stdout.write(f"⚙️  Paramètres: {algorithm_params}")
        
        # Compter les conflits avant optimisation
        initial_conflicts = self._count_conflicts(schedule)
        self.stdout.write(f"⚠️  Conflits détectés: {initial_conflicts}")
        
        if options['async']:
            # Lancement asynchrone
            admin_user = User.objects.filter(is_superuser=True).first()
            
            task_result = optimize_schedule_async.delay(
                schedule_id=schedule_id,
                algorithm=algorithm,
                algorithm_params=algorithm_params,
                user_id=admin_user.id if admin_user else None
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Optimisation lancée en arrière-plan\n'
                    f'   Task ID: {task_result.id}\n'
                    f'   Algorithme: {algorithm}\n'
                    f'   Suivi: python manage.py monitor_optimization {task_result.id}'
                )
            )
            
        else:
            # Lancement synchrone
            try:
                optimizer = TimetableOptimizer()
                
                # Callback pour afficher le progrès
                def progress_callback(progress, message):
                    if options['verbose']:
                        self.stdout.write(f"📈 {progress:.1f}% - {message}")
                
                result = optimizer.optimize_schedule(
                    schedule=schedule,
                    algorithm=algorithm,
                    algorithm_params=algorithm_params,
                    progress_callback=progress_callback if options['verbose'] else None
                )
                
                if result['success']:
                    final_conflicts = self._count_conflicts(schedule)
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ Optimisation terminée!\n'
                            f'   Conflits: {initial_conflicts} → {final_conflicts}\n'
                            f'   Amélioration: {initial_conflicts - final_conflicts} conflits résolus\n'
                            f'   Score fitness: {result["fitness"]:.4f}\n'
                            f'   Sessions modifiées: {result["assignments_changed"]}'
                        )
                    )
                    
                    if options['verbose']:
                        self.stdout.write("🎯 Objectifs atteints:")
                        for objective, value in result['objectives'].items():
                            self.stdout.write(f"   • {objective}: {value:.4f}")
                
                else:
                    raise CommandError(f"Optimisation échouée: {result.get('error', 'Erreur inconnue')}")
                    
            except Exception as e:
                raise CommandError(f"Erreur lors de l'optimisation: {str(e)}")
    
    def _prepare_algorithm_params(self, algorithm, options):
        """Prépare les paramètres selon l'algorithme"""
        
        if algorithm == 'genetic':
            return {
                'population_size': options['population_size'],
                'generations': options['generations'],
                'crossover_rate': options['crossover_rate'],
                'mutation_rate': options['mutation_rate'],
                'elite_size': options['elite_size']
            }
        
        elif algorithm == 'simulated_annealing':
            return {
                'initial_temperature': options['initial_temperature'],
                'cooling_rate': options['cooling_rate'],
                'min_temperature': options['min_temperature'],
                'max_iterations': options['max_iterations']
            }
        
        return {}
    
    def _count_conflicts(self, schedule):
        """Compte les conflits dans un emploi du temps"""
        conflicts = 0
        
        # Compter les conflits de salle
        time_room_pairs = {}
        for session in schedule.sessions.all():
            if session.time_slot and session.room:
                key = (session.time_slot.id, session.room.id)
                if key in time_room_pairs:
                    conflicts += 1
                else:
                    time_room_pairs[key] = session
        
        # Compter les conflits d'enseignant
        teacher_time_pairs = {}
        for session in schedule.sessions.all():
            if session.time_slot and session.teacher:
                key = (session.teacher.id, session.time_slot.id)
                if key in teacher_time_pairs:
                    conflicts += 1
                else:
                    teacher_time_pairs[key] = session
        
        return conflicts