# ============================================================================
# Dockerfile pour GLaDOS Assistant Vocal
# Image complète avec tous les modèles inclus pour déploiement simplifié
# ============================================================================

# Image de base Python 3.11 optimisée (sans desktop, plus légère)
FROM python:3.11-slim

# ============================================================================
# VARIABLES D'ENVIRONNEMENT
# ============================================================================

# Empêche les prompts interactifs pendant l'installation des packages
# Essentiel pour l'automatisation Docker
ENV DEBIAN_FRONTEND=noninteractive

# Force l'affichage immédiat des logs Python (pas de mise en buffer)
# Crucial pour voir les logs en temps réel dans Docker
ENV PYTHONUNBUFFERED=1

# Chemin vers PulseAudio pour l'audio dans le container
# Permet la communication avec le système audio de l'hôte
ENV PULSE_RUNTIME_PATH=/var/run/pulse

# ============================================================================
# INSTALLATION DES DÉPENDANCES SYSTÈME
# ============================================================================

RUN apt-get update && apt-get install -y \
    # === DÉPENDANCES AUDIO ===
    # alsa-utils : Outils ALSA pour la gestion audio bas niveau
    alsa-utils \
    # pulseaudio : Serveur audio pour la communication avec l'hôte
    pulseaudio \
    # portaudio19-dev : Bibliothèque audio cross-platform (pour pyaudio)
    portaudio19-dev \
    # libasound2-dev : Headers ALSA pour la compilation de modules audio
    libasound2-dev \
    \
    # === DÉPENDANCES DE COMPILATION ===
    # gcc : Compilateur C nécessaire pour certains packages Python (numpy, etc.)
    gcc \
    # g++ : Compilateur C++ nécessaire pour certaines dépendances
    g++ \
    # python3-dev : Headers Python pour compiler les extensions natives
    python3-dev \
    \
    # === UTILITAIRES ===
    # curl : Pour télécharger des ressources si nécessaire
    curl \
    # wget : Alternative à curl pour le téléchargement
    wget \
    \
    # === NETTOYAGE ===
    # Supprime le cache APT pour réduire la taille de l'image finale
    && rm -rf /var/lib/apt/lists/*

# ============================================================================
# CONFIGURATION AUDIO ET PERMISSIONS
# ============================================================================

# Crée le groupe audio avec l'ID 29 (standard Linux) si il n'existe pas
# || true évite l'erreur si le groupe existe déjà
RUN groupadd -g 29 audio || true && \
    # Ajoute l'utilisateur root au groupe audio pour l'accès aux périphériques
    usermod -a -G audio root || true

# ============================================================================
# PRÉPARATION DE L'ENVIRONNEMENT PYTHON
# ============================================================================

# Définit le répertoire de travail dans le container
WORKDIR /app

# === INSTALLATION DES DÉPENDANCES PYTHON ===
# Copie d'abord requirements.txt pour optimiser le cache Docker
# Si requirements.txt ne change pas, cette étape sera mise en cache
COPY requirements.txt .

# Installe les packages Python sans cache pour économiser l'espace
RUN pip install --no-cache-dir -r requirements.txt

# ============================================================================
# COPIE DU CODE ET DES MODÈLES
# ============================================================================

# Copie TOUT le contenu du projet dans le container
# Inclut : code source, modèles TTS, modèles wake word, modèles STT
# C'est ce qui rend cette image "complète" et autonome
COPY . .

# ============================================================================
# PRÉPARATION DES RÉPERTOIRES
# ============================================================================

# S'assure que tous les répertoires de modèles existent
# Même si COPY . . les a déjà copiés, cela garantit leur existence
RUN mkdir -p \
    /app/models

# ============================================================================
# CONFIGURATION DU POINT D'ENTRÉE
# ============================================================================

# Commande exécutée au démarrage du container
# Lance GLaDOS en mode module Python depuis le répertoire principal
CMD ["python", "-m", "glados.main"]

# ============================================================================
# NOTES IMPORTANTES
# ============================================================================
#
# Cette image contient TOUT :
# - Code source GLaDOS (~50MB)
# - Modèles TTS GLaDOS (~500MB)
# - Modèles Wake Word (~10MB)
# - Modèles STT Vosk (~200MB)
# - Dépendances Python (~500MB)
# - Système de base (~200MB)
#
# Taille finale estimée : ~1.5-2GB
#
# Avantages :
# ✅ Déploiement en une étape
# ✅ Pas de volumes externes à gérer
# ✅ Portable sur n'importe quel système
# ✅ Offline après construction
#
# Inconvénients :
# ❌ Image plus lourde
# ❌ Mise à jour = reconstruction complète
# ❌ Partage de modèles impossible entre containers
# ============================================================================