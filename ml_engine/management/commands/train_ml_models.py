#!/usr/bin/env python3
"""
Commande Django pour entraîner les modèles ML
============================================

Usage:
    python manage.py train_ml_models [options]
    python manage.py train_ml_models --algorithm genetic --generations 1000
    python manage.py train_ml_models --download-datasets --async
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction

from ml_engine.models import TimetableDataset, ModelTrainingTask
from ml_engine.services import TimetableDataProcessor, MLTrainingService
from ml_engine.tasks import train_ml_models_async


class Command(BaseCommand):
    help = 'Entraîne les modèles ML pour la prédiction de difficulté de planification'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dataset',
            type=str,
            help='Nom du dataset à utiliser (par défaut: utilise tous les datasets)'
        )
        
        parser.add_argument(
            '--download-datasets',
            action='store_true',
            help='Télécharger les datasets ITC 2007 avant l\'entraînement'
        )
        
        parser.add_argument(
            '--algorithms',
            nargs='+',
            default=['xgboost', 'random_forest', 'neural_network'],
            help='Algorithmes ML à entraîner (défaut: xgboost random_forest neural_network)'
        )
        
        parser.add_argument(
            '--async',
            action='store_true',
            help='Lancer l\'entraînement en arrière-plan avec Celery'
        )
        
        parser.add_argument(
            '--cross-validation',
            type=int,
            default=5,
            help='Nombre de folds pour la validation croisée (défaut: 5)'
        )
        
        parser.add_argument(
            '--max-features',
            type=int,
            help='Nombre maximum de features à utiliser'
        )
        
        parser.add_argument(
            '--test-size',
            type=float,
            default=0.2,
            help='Proportion du dataset pour les tests (défaut: 0.2)'
        )
        
        parser.add_argument(
            '--random-state',
            type=int,
            default=42,
            help='Graine pour la reproductibilité (défaut: 42)'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Affichage détaillé du processus'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Démarrage de l\'entraînement des modèles ML OAPET')
        )
        
        # Télécharger les datasets si demandé
        if options['download_datasets']:
            self._download_datasets()
        
        # Sélectionner le dataset
        dataset = self._get_dataset(options['dataset'])
        
        # Paramètres d'entraînement
        parameters = {
            'algorithms': options['algorithms'],
            'cross_validation': options['cross_validation'],
            'test_size': options['test_size'],
            'random_state': options['random_state']
        }
        
        if options['max_features']:
            parameters['max_features'] = options['max_features']
        
        # Obtenir l'utilisateur admin pour la tâche
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            raise CommandError("Aucun utilisateur administrateur trouvé")
        
        if options['async']:
            # Lancement asynchrone
            task_result = train_ml_models_async.delay(
                dataset_id=dataset.id,
                model_types=options['algorithms'],
                parameters=parameters,
                user_id=admin_user.id
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Entraînement lancé en arrière-plan\n'
                    f'   Task ID: {task_result.id}\n'
                    f'   Dataset: {dataset.name}\n'
                    f'   Algorithmes: {", ".join(options["algorithms"])}\n'
                    f'   Suivi: python manage.py monitor_ml_task {task_result.id}'
                )
            )
            
        else:
            # Lancement synchrone
            try:
                result = MLTrainingService.start_training(
                    dataset=dataset,
                    model_types=options['algorithms'],
                    parameters=parameters,
                    user=admin_user
                )
                
                if result.status == 'completed':
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ Entraînement terminé avec succès!\n'
                            f'   Meilleur modèle: {result.results.get("best_model", "N/A")}\n'
                            f'   ID du modèle: {result.results.get("model_id", "N/A")}\n'
                            f'   Performance: {result.results.get("performance", {})}'
                        )
                    )
                else:
                    raise CommandError(f"Entraînement échoué: {result.logs}")
                    
            except Exception as e:
                raise CommandError(f"Erreur lors de l'entraînement: {str(e)}")
    
    def _download_datasets(self):
        """Télécharge les datasets ITC 2007"""
        self.stdout.write("📥 Téléchargement des datasets ITC 2007...")
        
        try:
            processor = TimetableDataProcessor()
            downloaded_files = processor.download_datasets()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ {len(downloaded_files)} datasets téléchargés'
                )
            )
            
        except Exception as e:
            raise CommandError(f"Erreur lors du téléchargement: {str(e)}")
    
    def _get_dataset(self, dataset_name):
        """Récupère ou crée un dataset"""
        
        if dataset_name:
            try:
                dataset = TimetableDataset.objects.get(name=dataset_name)
                self.stdout.write(f"📊 Utilisation du dataset: {dataset.name}")
                return dataset
            except TimetableDataset.DoesNotExist:
                raise CommandError(f"Dataset '{dataset_name}' non trouvé")
        else:
            # Utiliser le premier dataset disponible ou en créer un
            dataset = TimetableDataset.objects.first()
            
            if not dataset:
                # Créer un dataset par défaut
                dataset = TimetableDataset.objects.create(
                    name='itc2007_combined',
                    description='Dataset combiné ITC 2007 pour entraînement',
                    metadata={'source': 'ITC 2007', 'auto_created': True}
                )
                self.stdout.write(f"📊 Dataset créé: {dataset.name}")
            else:
                self.stdout.write(f"📊 Utilisation du dataset: {dataset.name}")
            
            return dataset