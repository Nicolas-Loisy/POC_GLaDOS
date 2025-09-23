[![Python](https://img.shields.io/badge/python-3.11.4-blue.svg)](https://www.python.org/downloads/release/python-3114/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-blue.svg)](https://fastapi.tiangolo.com/)
[![LlamaIndex](https://img.shields.io/badge/LlamaIndex-0.13.0%2B-yellow.svg)](https://www.llamaindex.ai/)
[![PyYAML](https://img.shields.io/badge/PyYAML-6.0%2B-orange.svg)](https://pyyaml.org/)

# GLaDOS Assistant Vocal

**Assistant vocal intelligent et entièrement configurable basé sur ReAct de LlamaIndex**

GLaDOS est un assistant vocal modulaire qui peut être contrôlé par wake word, terminal ou Discord, et qui peut répondre via TTS (voix GLaDOS) ou terminal. Il utilise une architecture basée sur des design patterns robustes et peut être étendu facilement avec de nouveaux outils et modules.

## Technologies utilisées

- Python 3.11.4
- FastAPI
- Porcupine (wake word)
- Vosk (STT)
- Piper TTS
- LlamaIndex
- Discord.py (prévu)
- PyYAML
- pytest

## Fonctionnalités

### Modules d'Entrée (Input)

- Wake Word + STT : Détection de wake word avec Porcupine et reconnaissance vocale avec Vosk
- Interface Web : Interface web locale avec FastAPI et WebSockets
- Terminal : Interface en ligne de commande interactive
- Discord : Bot Discord (prévu)

### Modules de Sortie (Output)

- TTS GLaDOS : Synthèse vocale avec la voix GLaDOS via Piper TTS
- Terminal : Affichage formaté dans le terminal

### Outils Intégrés

- Contrôle Tapo : Gestion des appareils TP-Link (prises, ampoules)
- Contrôle IR : Contrôle infrarouge (prévu)

### Architecture

- Moteur ReAct : Intelligence basée sur LlamaIndex
- Design Patterns : Factory, Command, Observer, Strategy, Adapter
- Configuration : Système de configuration YAML flexible
- Modularité : Architecture complètement modulaire et extensible

## Installation

### Prérequis

- Python 3.11.4
- Clé API OpenAI
- Clé d'accès Porcupine (pour le wake word)
- Modèle Vosk FR (pour STT)
- Modèle Piper GLaDOS (pour TTS)

### Installation des dépendances

```bash
# Cloner le projet
git clone <url_du_repo>
cd POC_GLaDOS

# Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\\Scripts\\activate     # Windows

# Installer les dépendances
pip install -r requirements.txt
```

### Configuration

1. Copier le fichier de configuration exemple :

```bash
cp .env.example .env
```

2. Remplir les variables d'environnement dans `.env` :

```bash
OPENAI_API_KEY=your_openai_api_key_here
PORCUPINE_ACCESS_KEY=your_porcupine_access_key_here
TAPO_EMAIL=your_tapo_email@example.com
TAPO_PASSWORD=your_tapo_password_here
```

3. Adapter `config.yaml` selon vos besoins :
   - Configurer les appareils Tapo
   - Ajuster les paramètres audio
   - Activer/désactiver les modules

### Modèles requis

1. Modèle Vosk FR (déjà inclus) :

   - `vosk-model-small-fr-0.22/`

2. Modèle Piper GLaDOS :

   ```bash
   # Télécharger depuis HuggingFace
   mkdir -p models
   # Télécharger fr_FR-glados-medium.onnx dans models/
   ```

3. Wake words Porcupine (déjà inclus) :
   - `wake_words/glados_de_windows_v3_0_0.ppn`

## Utilisation

### Lancement rapide

```bash
# Méthode 1 : Script de lancement
python run_glados.py

# Méthode 2 : Module Python
python -m glados.main

# Méthode 3 : Installation en mode développement
pip install -e .
glados
```

### Modes d'interaction

1. Mode Terminal :

   - Tapez vos commandes après le prompt `GLaDOS> `
   - Commandes spéciales : `help`, `history`, `clear`, `exit`

2. Mode Wake Word :

   - Dites le wake word configuré (par défaut détection du mot clé)
   - Parlez votre commande après le signal
   - GLaDOS répond vocalement

3. Interface Web :
   - Ouvrez http://127.0.0.1:8080 dans votre navigateur
   - Interface moderne avec chat en temps réel
   - Actions rapides pour commandes fréquentes
   - Communication WebSocket bidirectionnelle

### Exemples de commandes

```bash
# Contrôle des appareils
"Allume la lampe de chambre"
"Éteins la prise de chambre"
"Change la couleur de la lampe en rouge"
"Mets la luminosité à 50%"

# Questions générales
"Quelle heure est-il ?"
"Quel temps fait-il ?"
"Raconte-moi une blague"
```

## Architecture

### Structure du projet

```
POC_GLaDOS/
├── glados/                 # Package principal
│   ├── core/              # Moteur ReAct et interfaces
│   ├── config/            # Gestion configuration
│   ├── inputs/            # Modules d'entrée
│   │   ├── wake_word/     # Wake word + STT
│   │   ├── web/           # Interface web FastAPI
│   │   ├── terminal/      # Interface terminal
│   │   └── discord/       # Bot Discord (futur)
│   ├── outputs/           # Modules de sortie
│   │   ├── tts/           # TTS GLaDOS
│   │   └── terminal/      # Sortie terminal
│   ├── tools/             # Adaptateurs d'outils
│   │   ├── tapo/          # Contrôle Tapo
│   │   └── adapters/      # Registre des outils
│   └── main.py            # Application principale
├── config.yaml           # Configuration principale
├── requirements.txt      # Dépendances
└── run_glados.py         # Script de lancement
```

### Design Patterns utilisés

- Factory Pattern : Création des modules Input/Output
- Command Pattern : Encapsulation des actions/outils
- Observer Pattern : Communication entre modules
- Strategy Pattern : Stratégies TTS/STT
- Adapter Pattern : Intégration des outils existants

## Configuration

Le fichier `config.yaml` permet de configurer tous les aspects de GLaDOS :

```yaml
core:
  model_name: "gpt-3.5-turbo"
  temperature: 0.1

inputs:
  wake_word:
    enabled: true
    stt:
      device_id: 1
  web:
    enabled: true
    host: "127.0.0.1"
    port: 8080
  terminal:
    enabled: true

outputs:
  tts_glados:
    enabled: true
    device_id: 5
  terminal:
    enabled: true

tools:
  tapo:
    enabled: true
    devices:
      lampe_chambre:
        type: "L530"
        ip: "192.168.1.186"
```

## Développement

### Ajouter un nouveau module d'entrée

1. Créer la classe héritant de `InputModule`
2. Implémenter les méthodes abstraites
3. Enregistrer dans `input_registry.py`

### Ajouter un nouveau module de sortie

1. Créer la classe héritant de `OutputModule`
2. Implémenter les méthodes abstraites
3. Enregistrer dans `output_registry.py`

### Ajouter un nouvel outil

1. Créer l'adaptateur héritant de `ToolAdapter`
2. Définir le schéma des paramètres
3. Enregistrer dans `tool_registry.py`

## Tests

```bash
# Installer les dépendances de test
pip install pytest pytest-asyncio

# Lancer les tests
pytest tests/

# Tests avec couverture
pytest --cov=glados tests/
```

## TODO

- Module Discord Input/Output
- Contrôle infrarouge (Yamaha, Osram)
- Interface web de configuration
- API REST
- Plugins système
- Mode démon/service
- Docker support

## Contribution

1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/amazing-feature`)
3. Commit les changements (`git commit -m 'Add amazing feature'`)
4. Push sur la branche (`git push origin feature/amazing-feature`)
5. Ouvrir une Pull Request

## Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## Remerciements

- [LlamaIndex](https://www.llamaindex.ai/) pour le moteur ReAct
- [Porcupine](https://picovoice.ai/platform/porcupine/) pour la détection de wake word
- [Vosk](https://alphacephei.com/vosk/) pour la reconnaissance vocale
- [Piper TTS](https://github.com/rhasspy/piper) pour la synthèse vocale
- [python-tapo](https://github.com/fishbigger/TapoP100) pour le contrôle des appareils Tapo
