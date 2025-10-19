# Guide de l'Agent Conversationnel OAPET

## Vue d'ensemble

L'agent conversationnel OAPET est maintenant capable d'exécuter des actions sur les emplois du temps en fonction du rôle de l'utilisateur connecté. Il combine les capacités de conversation intelligente avec des actions concrètes sur la base de données.

## Architecture

### Composants principaux

1. **AgentActionService** (`chatbot/agent_service.py`)
   - Gestion des permissions par rôle
   - Détection des intentions d'action
   - Extraction des paramètres
   - Exécution sécurisée des actions

2. **ChatbotService** (`chatbot/services.py`)
   - Intégration de l'agent avec le chatbot existant
   - Gestion du flux conversationnel multi-tours
   - Coordination entre conversation et actions

3. **Vues API** (`chatbot/views.py`)
   - Point d'entrée pour les messages utilisateur
   - Persistance des conversations et messages

## Rôles et Permissions

### Admin
Permissions complètes sur tous les emplois du temps :
- ✅ Créer un emploi du temps
- ✅ Modifier un emploi du temps
- ✅ Supprimer un emploi du temps
- ✅ Créer une session
- ✅ Modifier une session
- ✅ Supprimer une session
- ✅ Assigner un enseignant
- ✅ Assigner une salle
- ✅ Publier un emploi du temps
- ✅ Voir toutes les statistiques

### Enseignant
Permissions limitées à ses propres sessions :
- ✅ Consulter ses emplois du temps
- ✅ Consulter ses sessions
- ✅ Modifier sa session (salle uniquement)
- ✅ Demander une modification de session
- ✅ Voir les salles disponibles
- ✅ Exporter son emploi du temps

### Étudiant
Permissions en lecture seule :
- ✅ Consulter son emploi du temps
- ✅ Consulter l'emploi du temps de sa classe
- ✅ Rechercher une session
- ✅ Exporter son emploi du temps

## Exemples d'utilisation

### Pour les Administrateurs

#### Créer un emploi du temps
```
Utilisateur: Creer un emploi du temps nommé "Emploi du temps L3 Info"
Agent: Pour executer cette action, j'ai besoin de l'annee academique (ex: 2024-2025).
Utilisateur: 2024-2025
Agent: Veuillez fournir le semestre.
Utilisateur: Semestre 1
Agent: Voulez-vous vraiment executer cette action ? (Repondez 'oui' ou 'non')
Utilisateur: oui
Agent: Emploi du temps 'Emploi du temps L3 Info' cree avec succes (ID: 42)
```

#### Créer une session avec tous les paramètres
```
Utilisateur: Creer une session pour le cours #15 dans la salle #3 à 14h30 pendant 2h
Agent: Voulez-vous vraiment executer cette action ? (Repondez 'oui' ou 'non')
Utilisateur: oui
Agent: Session creee avec succes (ID: 123) - Mathematiques dans Salle A101
```

#### Modifier une session
```
Utilisateur: Modifier la session #45
Agent: Pour executer cette action, j'ai besoin de l'ID de la session.
Utilisateur: session #45
Agent: Voulez-vous vraiment executer cette action ? (Repondez 'oui' ou 'non')
Utilisateur: oui
Agent: Session #45 modifiee avec succes.
```

#### Publier un emploi du temps
```
Utilisateur: Publier l'emploi du temps #12
Agent: Voulez-vous vraiment executer cette action ? (Repondez 'oui' ou 'non')
Utilisateur: oui
Agent: Emploi du temps 'L3 Info Semestre 1' publie avec succes
```

#### Supprimer une session
```
Utilisateur: Supprimer la session #78
Agent: Voulez-vous vraiment executer cette action ? (Repondez 'oui' ou 'non')
Utilisateur: oui
Agent: Session supprimee avec succes: Physique - 15/10/2024 14:00
```

### Pour les Enseignants

#### Consulter ses sessions
```
Utilisateur: Montre-moi mes prochaines sessions
Agent: Voici vos prochaines sessions :

- Mathematiques
  Date : 15/10/2024 10:00
  Salle : A101

- Algebre Lineaire
  Date : 16/10/2024 14:30
  Salle : B204
```

#### Modifier une de ses sessions (salle uniquement)
```
Utilisateur: Modifier la session #56
Agent: Pour executer cette action, j'ai besoin de l'ID de la session.
(L'enseignant fournit l'ID de salle)
Utilisateur: Changer pour la salle #8
Agent: Session #56 modifiee avec succes. Champs modifies: salle
```

#### Demander une modification
```
Utilisateur: Demander une modification pour la session #56
Agent: Demande de modification enregistree pour la session #56. Un administrateur sera notifie.
```

#### Voir les salles disponibles
```
Utilisateur: Quelles salles sont disponibles ?
Agent: Salles disponibles :

- A101 (Batiment A)
  Capacite : 50 places
  Equipements : Projecteur, Tableau blanc

- B204 (Batiment B)
  Capacite : 30 places
  Equipements : Ordinateurs, Projecteur
```

### Pour les Étudiants

#### Consulter son emploi du temps
```
Utilisateur: Quel est mon emploi du temps ?
Agent: Emploi du temps de la semaine (14/10 - 20/10) :

** Lundi 14/10 **
- 08:00 - 10:00 : Mathematiques
  Salle : A101, Prof : Dr. Dupont

- 10:15 - 12:15 : Physique
  Salle : B203, Prof : Dr. Martin

** Mardi 15/10 **
- 14:00 - 16:00 : Informatique
  Salle : C301, Prof : Dr. Bernard
```

#### Rechercher une session
```
Utilisateur: Chercher le cours de mathematiques
Agent: J'ai trouve 3 session(s) :

- Mathematiques
  Date : 14/10/2024 08:00
  Salle : A101
  Enseignant : Dr. Dupont

- Mathematiques
  Date : 16/10/2024 10:00
  Salle : A101
  Enseignant : Dr. Dupont
```

#### Exporter son emploi du temps
```
Utilisateur: Exporter mon emploi du temps
Agent: Votre emploi du temps est en cours d'export. Vous recevrez un lien de telechargement par email.
```

## Flux de conversation

### 1. Détection d'intention
L'agent détecte automatiquement si le message contient une intention d'action :
- Patterns regex pour identifier les actions
- Vérification des permissions de l'utilisateur
- Extraction automatique des paramètres du message

### 2. Collecte des paramètres
Si des paramètres sont manquants, l'agent demande chacun séquentiellement :
```
Agent: Pour executer cette action, j'ai besoin de l'ID de l'emploi du temps.
Utilisateur: Emploi du temps #42
Agent: Veuillez fournir le semestre.
Utilisateur: Semestre 1
```

### 3. Confirmation (actions critiques)
Pour les actions destructives ou importantes, l'agent demande confirmation :
```
Agent: Voulez-vous vraiment executer cette action ? (Repondez 'oui' ou 'non')
Utilisateur: oui
```

### 4. Exécution
L'action est exécutée de manière atomique (transaction) :
- Vérifications de sécurité
- Validation des données
- Gestion des conflits
- Retour d'information détaillé

### 5. Annulation
L'utilisateur peut annuler à tout moment :
```
Utilisateur: non
Agent: Action annulee. Comment puis-je vous aider autrement ?
```

## Gestion des erreurs

L'agent gère intelligemment les erreurs :

### Permissions insuffisantes
```
Agent: Vous n'avez pas la permission d'executer l'action: create_schedule
```

### Ressource introuvable
```
Agent: Emploi du temps #999 introuvable
```

### Conflits détectés
```
Agent: Conflit detecte: la salle A101 est deja occupee a cette heure
```

### Session non autorisée
```
Agent: Vous ne pouvez modifier que vos propres sessions
```

## Intégration avec le chatbot existant

L'agent s'intègre transparently avec les fonctionnalités existantes :

1. **Détection prioritaire** : Les actions sont détectées avant les intentions conversationnelles
2. **Contexte préservé** : Le contexte de conversation est maintenu entre les tours
3. **Fallback intelligent** : Si aucune action n'est détectée, le chatbot répond normalement
4. **Multi-tour** : Support complet des conversations multi-tours pour compléter les paramètres

## Patterns de détection

### Actions de création
- `créer un emploi du temps`
- `nouveau emploi du temps`
- `ajouter un emploi du temps`
- `créer une session`
- `planifier une session`

### Actions de modification
- `modifier l'emploi du temps`
- `changer l'emploi du temps`
- `mettre à jour l'emploi du temps`
- `modifier la session`
- `déplacer la session`

### Actions de suppression
- `supprimer l'emploi du temps`
- `effacer l'emploi du temps`
- `supprimer la session`
- `annuler la session`

### Actions d'assignation
- `assigner un enseignant`
- `affecter un enseignant`
- `assigner une salle`
- `attribuer une salle`

### Actions de consultation
- `mes sessions`
- `mon emploi du temps`
- `emploi du temps de ma classe`
- `salles disponibles`

## Extraction de paramètres

L'agent extrait automatiquement :

- **IDs numériques** : `emploi du temps #42`, `session n°15`
- **Noms entre guillemets** : `nommé "L3 Info"`, `appelé "Semestre 1"`
- **Années académiques** : `2024-2025`, `2023/2024`
- **Semestres** : `semestre 1`, `semestre I`
- **Heures** : `14h30`, `08:00`, `10h00`
- **Durées** : `pendant 2h`, `durant 3 heures`
- **Salles** : `salle A101`, `salle #5`

## Sécurité

### Vérifications de permissions
- Chaque action vérifie les permissions de l'utilisateur
- Les enseignants ne peuvent modifier que leurs propres sessions
- Les étudiants ont un accès en lecture seule

### Transactions atomiques
- Toutes les modifications utilisent `@transaction.atomic`
- En cas d'erreur, aucun changement n'est persisté

### Validation des données
- Vérification des conflits de salles
- Validation des horaires
- Contrôle de la disponibilité des ressources

### Confirmation obligatoire
- Actions critiques nécessitent une confirmation explicite
- Création, modification, suppression d'emplois du temps
- Création, modification, suppression de sessions
- Publication d'emplois du temps

## Extension du système

### Ajouter une nouvelle action

1. **Définir l'action dans `ACTION_INTENTS`** :
```python
'nouvelle_action': {
    'patterns': [r'pattern1', r'pattern2'],
    'required_params': ['param1', 'param2'],
    'confirmation_required': True
}
```

2. **Ajouter les permissions dans `ROLE_PERMISSIONS`** :
```python
'admin': [..., 'nouvelle_action'],
'teacher': [..., 'nouvelle_action'],
```

3. **Implémenter la méthode d'exécution** :
```python
def _execute_nouvelle_action(self, params, conversation):
    # Implementation
    return (success, message, data)
```

### Personnaliser les patterns
Modifier les regex dans `ACTION_INTENTS` pour adapter la détection à votre contexte.

### Ajouter des paramètres personnalisés
Étendre `extract_parameters()` pour extraire de nouveaux types de paramètres.

## Tests recommandés

1. **Test des permissions**
   - Vérifier qu'un étudiant ne peut pas créer de sessions
   - Vérifier qu'un enseignant ne peut modifier que ses sessions
   - Vérifier que l'admin a toutes les permissions

2. **Test du flux multi-tour**
   - Créer une session sans fournir tous les paramètres
   - Vérifier que l'agent demande chaque paramètre manquant
   - Confirmer l'exécution finale

3. **Test de confirmation**
   - Tenter une action critique
   - Répondre "non" à la confirmation
   - Vérifier que l'action est annulée

4. **Test de conflits**
   - Créer une session dans une salle déjà occupée
   - Vérifier que le conflit est détecté
   - Vérifier qu'aucune modification n'est faite

5. **Test d'erreurs**
   - Référencer un ID inexistant
   - Vérifier le message d'erreur approprié

## API Endpoint

### Envoyer un message

**POST** `/api/chatbot/send_message/`

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Body:**
```json
{
  "message": "Créer un emploi du temps nommé \"L3 Info\"",
  "conversation_id": 42  // Optionnel
}
```

**Response:**
```json
{
  "conversation_id": 42,
  "user_message": {
    "id": 123,
    "content": "Créer un emploi du temps nommé \"L3 Info\"",
    "sender": "user",
    "timestamp": "2024-10-14T10:30:00Z"
  },
  "bot_response": {
    "id": 124,
    "content": "Pour executer cette action, j'ai besoin de l'annee academique...",
    "sender": "bot",
    "intent": "agent_param_request",
    "confidence": 100,
    "timestamp": "2024-10-14T10:30:01Z"
  }
}
```

## Conclusion

L'agent conversationnel OAPET offre une interface naturelle et sécurisée pour gérer les emplois du temps. Il combine :

- ✅ Détection d'intentions intelligente
- ✅ Extraction automatique de paramètres
- ✅ Gestion des permissions par rôle
- ✅ Flux conversationnel multi-tours
- ✅ Confirmations pour actions critiques
- ✅ Gestion robuste des erreurs
- ✅ Transactions atomiques

Le système est extensible et peut être adapté pour supporter de nouvelles actions et rôles selon vos besoins.
