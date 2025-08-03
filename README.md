# 🎓 OAPET Schedule System Backend

## 📋 Vue d'ensemble

Système complet de gestion d'emplois du temps universitaire avec intelligence artificielle, développé avec Django REST Framework.

### 🌟 Fonctionnalités Principales

- **🤖 Intelligence Artificielle**: Prédiction de difficulté de planification avec algorithmes ML
- **📅 Gestion d'emplois du temps**: Création, optimisation et publication d'emplois du temps
- **🏛️ Gestion académique**: Départements, enseignants, cours, étudiants
- **🏢 Gestion des salles**: Bâtiments, salles, équipements, disponibilités
- **⚡ Détection de conflits**: Identification automatique des conflits de planification
- **📊 Optimisation avancée**: Algorithmes d'optimisation assistés par IA
- **📈 Métriques et analyses**: Tableau de bord avec statistiques détaillées

## 🛠️ Technologies Utilisées

- **Backend**: Django 5.1.7, Django REST Framework
- **Base de données**: SQLite (développement), PostgreSQL (production)
- **Intelligence Artificielle**: scikit-learn, XGBoost, pandas, numpy
- **API**: REST API avec authentification par token
- **Documentation**: Auto-générée avec DRF

## 🚀 Installation et Configuration

### Prérequis

```bash
Python 3.9+
pip
virtualenv (recommandé)
```

### Installation

1. **Cloner le projet**
```bash
git clone <repository-url>
cd oapet_schedule_backend
```

2. **Créer un environnement virtuel**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

3. **Installer les dépendances**
```bash
pip install -r requirements.txt
```

4. **Configurer les variables d'environnement**
```bash
cp .env.example .env
# Éditer .env avec vos configurations
```

5. **Effectuer les migrations**
```bash
python manage.py makemigrations
python manage.py migrate
```

6. **Créer un superutilisateur**
```bash
python manage.py createsuperuser
```

7. **Démarrer le serveur**
```bash
python manage.py runserver
```

## 📁 Structure du Projet

```
oapet_schedule_backend/
├── oapet_schedule_backend/  # Configuration principale
│   ├── settings.py         # Paramètres Django
│   ├── urls.py            # URLs principales
│   └── wsgi.py            # Configuration WSGI
├── courses/               # Gestion des cours
│   ├── models.py         # Modèles de données
│   ├── serializers.py    # Sérialisation API
│   ├── views.py          # Vues API
│   └── urls.py           # URLs de l'app
├── rooms/                # Gestion des salles
│   ├── models.py         # Modèles de données
│   ├── serializers.py    # Sérialisation API
│   ├── views.py          # Vues API
│   └── urls.py           # URLs de l'app
├── schedules/            # Gestion des emplois du temps
│   ├── models.py         # Modèles de données
│   ├── serializers.py    # Sérialisation API
│   ├── views.py          # Vues API
│   └── urls.py           # URLs de l'app
├── ml_engine/            # Moteur d'intelligence artificielle
│   ├── models.py         # Modèles ML
│   ├── services.py       # Services IA
│   ├── serializers.py    # Sérialisation API
│   ├── views.py          # Vues API
│   └── urls.py           # URLs de l'app
├── media/                # Fichiers uploadés
├── ml_models/            # Modèles ML sauvegardés
├── ml_datasets/          # Datasets ITC 2007
└── requirements.txt      # Dépendances Python
```

## 🌐 API Endpoints

### 🔐 Authentification
- `POST /api/auth/token/` - Obtenir un token d'authentification

### 🎓 Gestion des Cours
- `GET /api/courses/departments/` - Liste des départements
- `GET /api/courses/teachers/` - Liste des enseignants
- `GET /api/courses/courses/` - Liste des cours
- `GET /api/courses/curricula/` - Liste des curricula
- `GET /api/courses/students/` - Liste des étudiants

### 🏢 Gestion des Salles
- `GET /api/rooms/buildings/` - Liste des bâtiments
- `GET /api/rooms/rooms/` - Liste des salles
- `POST /api/rooms/rooms/search_available/` - Recherche de salles disponibles
- `GET /api/rooms/availability/` - Disponibilités des salles

### 📅 Emplois du Temps
- `GET /api/schedules/schedules/` - Liste des emplois du temps
- `POST /api/schedules/schedules/{id}/publish/` - Publier un emploi du temps
- `GET /api/schedules/schedules/{id}/weekly_view/` - Vue hebdomadaire
- `POST /api/schedules/schedules/{id}/detect_conflicts/` - Détecter les conflits

### 🤖 Intelligence Artificielle
- `POST /api/ml/datasets/download_itc_datasets/` - Télécharger datasets ITC 2007
- `POST /api/ml/training-tasks/start_training/` - Démarrer l'entraînement ML
- `POST /api/ml/predictions/predict_course_difficulty/` - Prédire la difficulté
- `GET /api/ml/models/` - Liste des modèles ML

## 🔬 Modèles d'Intelligence Artificielle

### Algorithmes Supportés
- **XGBoost**: Gradient boosting optimisé
- **Random Forest**: Forêts aléatoires
- **Neural Networks**: Réseaux de neurones (MLPRegressor)
- **Gradient Boosting**: Gradient boosting classique

### Features Extraites
- Densité de cours
- Conflits de curriculum
- Contraintes d'indisponibilité
- Pression d'utilisation des salles
- Centralité dans le graphe de conflits
- Clustering coefficient

### Prédictions Disponibles
- **Difficulté de planification**: Score de 0 à 1
- **Niveau de complexité**: Faible, Moyenne, Élevée
- **Priorité de planification**: 1 (haute) à 3 (basse)
- **Recommandations**: Conseils personnalisés

## 🎯 Utilisation de l'API

### Authentification
```bash
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

### Prédiction de difficulté d'un cours
```bash
curl -X POST http://localhost:8000/api/ml/predictions/predict_course_difficulty/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "course_name": "Anatomie Générale",
    "lectures": 3,
    "min_days": 2,
    "students": 120,
    "teacher": "Dr_Kamga",
    "conflict_degree": 4,
    "unavailability_count": 2
  }'
```

### Recherche de salles disponibles
```bash
curl -X POST http://localhost:8000/api/rooms/rooms/search_available/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "min_capacity": 50,
    "has_projector": true,
    "day_of_week": "monday",
    "period": "08:00-09:30"
  }'
```

## 📊 Configuration ML

### Variables d'environnement
```env
ML_MODELS_DIR=./ml_models
ML_DATASETS_DIR=./ml_datasets
DEBUG=True
SECRET_KEY=your-secret-key
```

### Paramètres d'entraînement
```python
TRAINING_PARAMETERS = {
    'test_size': 0.2,
    'random_state': 42,
    'cross_validation_folds': 5,
    'models': ['xgboost', 'random_forest', 'neural_network']
}
```

## 🔧 Administration

### Interface d'administration Django
Accédez à `http://localhost:8000/admin/` avec les identifiants de superutilisateur.

### Gestion des modèles ML
1. Télécharger les datasets ITC 2007
2. Démarrer l'entraînement des modèles
3. Activer le meilleur modèle
4. Surveiller les performances

## 📈 Monitoring et Performance

### Métriques disponibles
- **R² Score**: Coefficient de détermination
- **MAE**: Erreur absolue moyenne
- **MSE**: Erreur quadratique moyenne
- **Temps de traitement**: Performance des prédictions

### Logs
```bash
tail -f logs/django.log  # Logs généraux
tail -f logs/ml_engine.log  # Logs IA
```

## 🛡️ Sécurité

### Authentification
- Token-based authentication
- Permissions par utilisateur
- Protection CSRF

### Données sensibles
- Variables d'environnement pour les secrets
- Hashage des mots de passe
- Validation des entrées

## 🚀 Déploiement en Production

### Configuration PostgreSQL
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'oapet_schedule',
        'USER': 'postgres',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### Docker
```dockerfile
FROM python:3.11
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

## 🤝 Contribution

1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/AmazingFeature`)
3. Commit les changements (`git commit -m 'Add AmazingFeature'`)
4. Push sur la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

## 📝 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 👥 Équipe

- **Développement Backend**: Django REST Framework
- **Intelligence Artificielle**: Machine Learning avec scikit-learn
- **Architecture**: Microservices et API REST

## 📞 Support

Pour le support technique, ouvrir une issue sur GitHub ou contacter l'équipe de développement.

---

**🎓 OAPET Schedule System - Optimisation intelligente des emplois du temps universitaires**