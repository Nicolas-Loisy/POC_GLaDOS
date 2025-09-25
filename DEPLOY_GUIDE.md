# Documentation : Déploiement GLaDOS sur Raspberry Pi avec Docker et Portainer

## Création de l'image

```bash
# Start Docker Desktop
docker buildx build --platform linux/amd64,linux/arm64 --tag virnes/glados-assistant:1.0.0 --tag virnes/glados-assistant:latest --push .
```

## Étape 0 : Préparation du Raspberry Pi

```bash
# Connexion SSH au Raspberry Pi
ssh pi@[IP_DU_PI]

# Installation de Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker pi

# Redémarrage pour prendre en compte les groupes
sudo reboot

# Reconnexion SSH et installation de Portainer
docker volume create portainer_data
docker run -d -p 8000:8000 -p 9443:9443 --name portainer --restart=always \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v portainer_data:/data \
  portainer/portainer-ce:latest
```

### Vérification des périphériques

```bash
# Vérifier l'accès GPIO
ls -l /dev/gpiomem*

# Vérifier les périphériques audio
aplay -l
speaker-test -D hw:2,0 -c 2 -t sine -f 440 -l 1

arecord -l
arecord -D hw:3,0 -f S16_LE -c 1 -r 16000 -t wav test.wav
aplay -D plughw:3,0 test.wav


# Tester l'accès réseau
ping google.com
```

---

### Transfert des modèles

Création des répertoires sur le Pi

```bash
# Créer la structure des répertoires
mkdir -p /home/pi/glados-data/{models,wake_word_model,wake_words,vosk-model}
```

Transfert des fichiers depuis votre PC

```bash
# Depuis votre PC Windows (PowerShell ou WSL)
# Remplacer [IP_DU_PI] par l'IP de votre Raspberry Pi

# Modèles TTS GLaDOS
scp -r "E:\Nicolas\Workspace\POC_GLaDOS\models\*" pi@[IP_DU_PI]:/home/pi/glados-data/models/

# Modèles Wake Word
scp -r "E:\Nicolas\Workspace\POC_GLaDOS\wake_word_model\*" pi@[IP_DU_PI]:/home/pi/glados-data/wake_word_model/
scp -r "E:\Nicolas\Workspace\POC_GLaDOS\wake_words\*" pi@[IP_DU_PI]:/home/pi/glados-data/wake_words/

# Modèle Vosk STT
scp -r "E:\Nicolas\Workspace\POC_GLaDOS\vosk-model-small-fr-0.22\*" pi@[IP_DU_PI]:/home/pi/glados-data/vosk-model/

# Alternative : utiliser une clé USB
# 1. Copier les modèles sur une clé USB
# 2. Brancher la clé sur le Pi
# 3. Monter et copier :
sudo mkdir /mnt/usb
sudo mount /dev/sda1 /mnt/usb
cp -r /mnt/usb/models/* /home/pi/glados-data/models/
sudo umount /mnt/usb
```

## Étape 1 : Préparation sur votre PC

### 1.1 Sécurisation des variables d'environnement

```bash
# ⚠️ IMPORTANT : Vérifier que .dockerignore existe pour exclure .env
type .dockerignore

# Configurer vos variables d'environnement localement (PAS dans l'image)
copy .env.example .env
notepad .env
```

### 1.2 Configuration pour build multi-architecture

```bash
# Se placer dans le répertoire du projet
cd E:\Nicolas\Workspace\POC_GLaDOS

# 🔐 Vérification SÉCURITAIRE : S'assurer que .env sera exclu
docker build --dry-run -t glados-assistant:latest . 2>&1 | findstr ".env"
# ✅ Aucun résultat = .env correctement exclu

# 🏗️ IMPORTANT : Créer un builder multi-architecture (une seule fois)
docker buildx create --name multiarch-builder --use
docker buildx inspect --bootstrap

# Connexion à Docker Hub
docker login
```

### 1.3 Construction et publication ARM64 pour Raspberry Pi 5

```bash
# 🚀 Construire et publier directement pour ARM64 (Pi5)
# Cette commande build pour ARM64 et pousse automatiquement
docker buildx build \
  --platform linux/arm64 \
  --tag virnes/glados-assistant:latest \
  --push \
  .

# Vérifier que l'image ARM64 est sur Docker Hub
docker buildx imagetools inspect virnes/glados-assistant:latest
```

### 1.4 Alternative : Export local ARM64 (si pas Docker Hub)

```bash
# Si vous préférez ne pas utiliser Docker Hub
# Construire localement pour ARM64 sans pousser
docker buildx build \
  --platform linux/arm64 \
  --tag glados-assistant:arm64 \
  --load \
  .

# Exporter l'image ARM64
docker save glados-assistant:arm64 -o glados-assistant-arm64.tar

# Vérifier la taille du fichier (environ 2-4 GB)
dir glados-assistant-arm64.tar
```

---

## Étape 2 : Déploiement sur le Pi avec Portainer

### 2.1 Méthode A : Via Docker Hub (Recommandée)

```bash
# Le Pi téléchargera automatiquement l'image depuis Docker Hub
# Aucun transfert manuel nécessaire !
```

### 2.2 Méthode B : Via fichier local ARM64 (Alternative)

```bash
# Seulement si vous n'utilisez pas Docker Hub
# Transférer l'image ARM64
scp glados-assistant-arm64.tar pi@[IP_PI]:/home/pi/

# Se connecter au Pi et charger l'image ARM64
ssh pi@[IP_PI]
docker load -i /home/pi/glados-assistant-arm64.tar
docker images | grep glados
```

---

## Étape 3 : Déploiement avec Portainer

### 3.1 Accéder à Portainer

1. Ouvrir `https://[IP_PI]:9443` dans votre navigateur
2. Se connecter à Portainer

### 3.2 Créer un Container

1. **Menu** → **Containers** → **Add container**
2. **Name** : `glados-assistant`
3. **Image** : `virnes/glados-assistant:latest` (ou votre compte Docker Hub)

### 3.3 Configuration du Container

**🔐 Variables d'environnement** (Section "Advanced container settings" → "Env") :

Ajouter une par une (bouton "+ add environment variable") :

```
Nom                      | Valeur
-------------------------|--------------------------------
OPENAI_API_KEY          | sk-votre-vraie-clé-openai
TAPO_EMAIL              | votre@email.com
TAPO_PASSWORD           | votre-mot-de-passe-tapo
OPENWEATHERMAP_API_KEY  | votre-clé-weather-réelle
PORCUPINE_ACCESS_KEY    | votre-clé-porcupine-réelle
DISCORD_BOT_TOKEN       | votre-token-discord-réel
```

**🔧 Configuration réseau** (Section "Network") :

- **Network mode** : `host`
- Avec le mode `host`, le port 8081 est automatiquement accessible

**📁 Volumes** (Section "Volumes") :

- **Container** : `/dev` → **Host** : `/dev` → **Bind**
- **Container** : `/var/run/pulse` → **Host** : `/var/run/pulse` → **Bind** (Read-only ✅)
- **Container** : `/dev/shm` → **Host** : `/dev/shm` → **Bind**

**⚙️ Restart policy** (Section "Restart policy") :

- Sélectionner **"Unless stopped"**

**🛡️ Privileged mode** (Section "Runtime & Resources") :

- **Privileged mode** : ✅ Activé

**🔌 Devices** (Section "Runtime & Resources") :

- **Container path** : `/dev/gpiomem0` → **Host path** : `/dev/gpiomem0`
- **Container path** : `/dev/gpiomem1` → **Host path** : `/dev/gpiomem1`
- **Container path** : `/dev/gpiomem2` → **Host path** : `/dev/gpiomem2`
- **Container path** : `/dev/gpiomem3` → **Host path** : `/dev/gpiomem3`
- **Container path** : `/dev/gpiomem4` → **Host path** : `/dev/gpiomem4`
- **Container path** : `/dev/gpiochip0` → **Host path** : `/dev/gpiochip0`
- **Container path** : `/dev/gpiochip10` → **Host path** : `/dev/gpiochip10`
- **Container path** : `/dev/gpiochip11` → **Host path** : `/dev/gpiochip11`
- **Container path** : `/dev/gpiochip12` → **Host path** : `/dev/gpiochip12`
- **Container path** : `/dev/gpiochip13` → **Host path** : `/dev/gpiochip13`
  (inutile de monter /dev/gpiochip4 car c’est juste un lien vers gpiochip0)

- **Container path** : `/dev/snd` → **Host path** : `/dev/snd`
- **Container path** : `/run/user/1000/pulse` → **Host path** : `/run/user/1000/pulse`

### 3.4 Déploiement

1. Cliquer sur **"Deploy the container"**
2. Le déploiement sera **instantané** (image ARM64 déjà construite)
3. Vérifier les logs dans Portainer

---

## Étape 4 : Vérification

### 4.1 Vérifier le statut

```bash
# Statut du container
docker ps | grep glados

# Logs en temps réel
docker logs -f glados-assistant
```

### 4.2 Vérification audio dans le container

**Tester le microphone :**

```bash
# Entrer dans le container
docker exec -it glados-assistant bash

# Lister les périphériques audio
arecord -l

# Tester l'enregistrement (Ctrl+C pour arrêter)
arecord -D plughw:0,0 -f cd test.wav
```

**Tester la sortie audio :**

```bash
# Dans le container
aplay -l

# Tester la lecture
aplay test.wav

# Test direct avec speaker-test
speaker-test -t wav -c 2
```

**Vérifier PulseAudio :**

```bash
# Dans le container
pulseaudio --check -v
pactl info
pactl list sources short    # Microphones
pactl list sinks short      # Sorties audio
```

**Vérifier le Wake Word :**

Exécutez le script suivant dans le container pour identifier le numéro du périphérique microphone :

```bash
touch testd.py
```

```bash
cat > testd.py << 'EOF'
# test_devices.py
from pvrecorder import PvRecorder
import numpy as np

def test_all_devices():
    devices = PvRecorder.get_available_devices()
    print(f"Périphériques PvRecorder disponibles: {len(devices)}")

    for i, device in enumerate(devices):
        print(f"\n🎤 Test device {i}: {device}")
        try:
            recorder = PvRecorder(device_index=i, frame_length=512)
            recorder.start()

            # Test 2 secondes
            max_level = 0
            for _ in range(32):  # ~2 secondes à 16kHz
                pcm = recorder.read()
                level = np.abs(pcm).max()
                max_level = max(max_level, level)

            recorder.stop()
            recorder.delete()

            print(f"   ✅ Fonctionne - Niveau max: {max_level}")
            if max_level > 100:  # Seuil arbitraire
                print(f"   🔊 Device {i} semble actif!")

        except Exception as e:
            print(f"   ❌ Erreur: {e}")

if __name__ == "__main__":
    test_all_devices()

EOF
```

### 4.3 Test GLaDOS

1. Dire "GLaDOS" près du microphone
2. Vérifier la réponse vocale
3. Vérifier les logs : `docker logs glados-assistant | grep -i wake`

---

## Avantages de cette méthode

✅ **Build cross-platform** : Windows → ARM64 pour Raspberry Pi 5
✅ **Construction sur PC** : Plus rapide et plus fiable que sur Pi
✅ **Image complète** : Tous les modèles inclus, pas de volumes externes
✅ **Déploiement instantané** : Pas de compilation sur le Pi
✅ **Architecture native** : Image ARM64 optimisée pour Pi5
✅ **Simplicité** : Build et deploy en une commande

---

## Commandes utiles

```bash
# Sur votre PC - Reconstruire et publier l'image ARM64
docker buildx build --no-cache \
  --platform linux/arm64 \
  --tag votre-compte-dockerhub/glados-assistant:latest \
  --push \
  .

# Sur le Pi - Recharger une nouvelle image depuis Docker Hub
docker stop glados-assistant
docker rm glados-assistant
docker rmi votre-compte-dockerhub/glados-assistant:latest
docker pull votre-compte-dockerhub/glados-assistant:latest

# Redémarrer via Portainer ou directement
docker compose up -d
```

---

## Taille approximative des fichiers

- **Image Docker ARM64** : 2-4 GB (selon les modèles)
- **Build time** : 10-20 minutes (émulation ARM64 sur Windows)
- **Push time** : 5-15 minutes selon votre connexion
- **Déploiement Pi5** : < 30 secondes

**🎯 Cette méthode cross-platform est optimale :**

- Build Windows → Deploy Pi5 en architecture native
- Plus rapide que build natif sur Pi5
- Image ARM64 optimisée pour performances Pi5
