# Architecture GLaDOS

## Vue d'ensemble

GLaDOS est conçu avec une architecture modulaire et extensible basée sur des design patterns éprouvés. L'objectif est de créer un système flexible où chaque composant peut être développé, testé et déployé indépendamment.

## Principes architecturaux

### 1. Modularité
- Séparation claire entre Input, Processing, Output
- Chaque module est autonome et interchangeable
- Interfaces bien définies entre les composants

### 2. Extensibilité
- Factory patterns pour l'ajout de nouveaux modules
- Système de registres pour la découverte automatique
- Configuration dynamique via YAML

### 3. Robustesse  
- Gestion d'erreurs à tous les niveaux
- Isolation des modules (un crash ne fait pas tomber le système)
- Logging complet et structuré

## Architecture technique

```
┌─────────────────────────────────────────────────────────────┐
│                    GLaDOS Application                        │
├─────────────────────────────────────────────────────────────┤
│                 Configuration Manager                       │
│                   (Singleton Pattern)                       │
├─────────────────────┬───────────────────┬───────────────────┤
│   Input Modules     │   ReAct Engine    │  Output Modules   │
│                     │                   │                   │
│ ┌─────────────────┐ │ ┌───────────────┐ │ ┌─────────────────┐ │
│ │   Wake Word     │ │ │   LlamaIndex  │ │ │   TTS GLaDOS    │ │
│ │   + Vosk STT    │ │ │   ReAct Agent │ │ │   (Piper)       │ │
│ └─────────────────┘ │ └───────────────┘ │ └─────────────────┘ │
│                     │        │          │                   │
│ ┌─────────────────┐ │ ┌───────────────┐ │ ┌─────────────────┐ │
│ │   Terminal      │ │ │   Tools       │ │ │   Terminal      │ │
│ │   Input         │ │ │   Registry    │ │ │   Output        │ │
│ └─────────────────┘ │ └───────────────┘ │ └─────────────────┘ │
│                     │        │          │                   │
│ ┌─────────────────┐ │ ┌───────────────┐ │ ┌─────────────────┐ │
│ │   Discord       │ │ │   Tapo        │ │ │   Discord       │ │
│ │   Bot           │ │ │   Adapter     │ │ │   Output        │ │
│ └─────────────────┘ │ └───────────────┘ │ └─────────────────┘ │
└─────────────────────┴───────────────────┴───────────────────┘
```

## Design Patterns utilisés

### 1. Factory Pattern
**Objectif** : Créer des instances de modules sans connaître leurs classes concrètes.

```python
# Exemple d'utilisation
input_module = InputModuleFactory.create('wake_word', 'wake_word', config)
output_module = OutputModuleFactory.create('tts_glados', 'tts', config)
tool = ToolAdapterFactory.create('tapo', 'tapo_control', config)
```

**Avantages** :
- Ajout facile de nouveaux types de modules
- Découplage entre création et utilisation
- Configuration centralisée

### 2. Command Pattern  
**Objectif** : Encapsuler les actions/outils comme des objets.

```python
class ToolAdapter(ABC):
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        pass
```

**Avantages** :
- Actions paramétrables et réversibles
- Historique des commandes
- Validation des paramètres

### 3. Observer Pattern
**Objectif** : Communication asynchrone entre modules.

```python
# Module Input émet des messages
await self.emit_message(GLaDOSMessage(...))

# Engine s'abonne aux messages
input_module.subscribe_to_messages(self._handle_input_message)
```

**Avantages** :
- Faible couplage entre modules
- Communication event-driven
- Extensibilité pour de nouveaux observateurs

### 4. Strategy Pattern
**Objectif** : Interchanger les algorithmes de TTS/STT.

```python
# Différentes stratégies TTS
class PiperTTSStrategy:
    def synthesize(self, text): ...

class ElevenLabsTTSStrategy:
    def synthesize(self, text): ...
```

### 5. Adapter Pattern
**Objectif** : Intégrer des APIs existantes dans l'architecture GLaDOS.

```python
class TapoAdapter(ToolAdapter):
    # Adapte l'API Tapo au format GLaDOS
    async def execute(self, **kwargs):
        # Conversion des paramètres
        # Appel API Tapo  
        # Conversion du résultat
```

## Flux de données

### 1. Traitement d'une commande vocale

```
Wake Word Detection → STT Processing → Text Message → ReAct Engine → Tool Execution → Response Generation → TTS Output
```

**Détail** :
1. **Porcupine** détecte le wake word
2. **Vosk** convertit la parole en texte
3. **WakeWordInput** émet un `GLaDOSMessage`
4. **ReActEngine** traite le message avec LlamaIndex
5. **Agent ReAct** sélectionne et exécute les outils nécessaires
6. **Engine** génère une réponse
7. **TTS Module** synthétise et joue la réponse

### 2. Traitement d'une commande terminal

```
Terminal Input → Text Message → ReAct Engine → Tool Execution → Terminal Output
```

## Gestion des erreurs

### Stratégie en couches
1. **Module Level** : Chaque module gère ses erreurs internes
2. **Engine Level** : L'engine capture les erreurs des modules
3. **Application Level** : L'application gère les erreurs fatales

### Types d'erreurs
- **Récupérables** : Module indisponible → désactivation temporaire
- **Critiques** : Erreur de configuration → arrêt du système
- **Utilisateur** : Commande invalide → message d'erreur à l'utilisateur

## Configuration système

### Hiérarchie de configuration
1. **Fichier config.yaml** : Configuration principale
2. **Variables d'environnement** : Secrets et paramètres système
3. **Valeurs par défaut** : Configuration de base dans le code

### Configuration dynamique
- Rechargement à chaud possible
- Validation des configurations
- Migration automatique entre versions

## Extensibilité

### Ajouter un nouveau module Input

1. **Créer la classe** :
```python
class MyInput(InputModule):
    async def initialize(self): ...
    async def start_listening(self): ...
    # ...
```

2. **Enregistrer le module** :
```python
InputModuleFactory.register('my_input', MyInput)
```

3. **Configurer** :
```yaml
inputs:
  my_input:
    enabled: true
    # paramètres spécifiques
```

### Ajouter un nouvel outil

1. **Créer l'adaptateur** :
```python
class MyToolAdapter(ToolAdapter):
    async def execute(self, **kwargs): ...
    def get_parameters_schema(self): ...
```

2. **Enregistrer l'outil** :
```python
ToolAdapterFactory.register('my_tool', MyToolAdapter)
```

3. **Configurer** :
```yaml
tools:
  my_tool:
    enabled: true
    # paramètres spécifiques
```

## Performances et optimisations

### Gestion mémoire
- Pools d'objets réutilisables pour l'audio
- Nettoyage automatique des fichiers temporaires
- Limitation de la taille des historiques

### Concurrence
- Modules Input/Output asynchrones
- Parallélisation des traitements non-dépendants
- Queue de messages pour éviter la perte de données

### Mise en cache
- Cache des réponses fréquentes
- Pré-chargement des modèles
- Réutilisation des connexions

## Sécurité

### Gestion des secrets
- Variables d'environnement pour les clés API
- Pas de secrets en dur dans le code
- Validation des paramètres utilisateur

### Isolation
- Validation stricte des entrées
- Timeout sur les opérations externes
- Limitation des ressources par module

## Tests

### Stratégie de test
- **Unit Tests** : Chaque module individuellement
- **Integration Tests** : Communication entre modules
- **E2E Tests** : Scénarios utilisateur complets

### Mocks et fixtures
- Mock des services externes (OpenAI, Tapo, etc.)
- Fixtures audio pour les tests STT/TTS
- Configuration de test isolée

## Monitoring et observabilité

### Logging structuré
- Niveaux : DEBUG, INFO, WARNING, ERROR
- Contexte : module, action, utilisateur
- Format JSON pour l'analyse automatique

### Métriques
- Temps de réponse par module
- Taux de succès des actions
- Utilisation des ressources

### Debugging
- Mode verbose configurable
- Sauvegarde des données audio en debug
- Traçage des messages entre modules

Cette architecture modulaire permet une évolution continue du système tout en maintenant la stabilité et les performances.