"""
Module de sortie TTS GLaDOS
Utilise Piper TTS avec la voix GLaDOS pour la synthèse vocale
"""

import asyncio
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any
import sounddevice as sd
import numpy as np
import wave
import os
import subprocess

from ...core.interfaces import OutputModule, GLaDOSMessage, MessageType


class GLaDOSTTSOutput(OutputModule):
    """
    Module de sortie Text-to-Speech avec voix GLaDOS
    Utilise Piper TTS pour générer l'audio avec la voix GLaDOS
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.logger = logging.getLogger(__name__)
        
        # Configuration TTS
        self.model_path = config.get('model_path', 'models/fr_FR-glados-medium.onnx')
        self.device_id = config.get('device_id', None)
        self.sample_rate = config.get('sample_rate', 22050)
        self.volume = config.get('volume', 0.8)
        
        # État
        self.temp_dir = None
    
    async def initialize(self) -> bool:
        """Initialise le module TTS GLaDOS"""
        try:
            self.logger.info("Initialisation du module TTS GLaDOS...")

            # Vérifier que le modèle existe avec chemin absolu
            model_file = Path(self.model_path)
            if not model_file.is_absolute():
                # Rendre le chemin absolu par rapport au répertoire racine du projet
                project_root = Path(__file__).parent.parent.parent.parent
                model_file = project_root / self.model_path
                self.model_path = str(model_file)
                self.logger.info(f"Chemin modèle converti en absolu: {self.model_path}")

            if not model_file.exists():
                self.logger.error(f"Modèle TTS GLaDOS non trouvé: {self.model_path}")
                self.logger.info("Téléchargez le modèle depuis: https://huggingface.co/rhasspy/piper-voices")

                # Lister les fichiers dans le répertoire parent pour diagnostic
                parent_dir = model_file.parent
                if parent_dir.exists():
                    files = list(parent_dir.glob("*.onnx"))
                    if files:
                        self.logger.info(f"Modèles trouvés dans {parent_dir}: {[f.name for f in files]}")
                    else:
                        self.logger.info(f"Aucun modèle .onnx trouvé dans {parent_dir}")
                else:
                    self.logger.error(f"Répertoire modèle inexistant: {parent_dir}")

                return False

            self.logger.info(f"Modèle TTS trouvé: {self.model_path} ({model_file.stat().st_size} octets)")
            
            # Créer répertoire cache permanent pour les fichiers audio
            cache_base = Path(tempfile.gettempdir()) / "glados_tts_cache"
            cache_base.mkdir(exist_ok=True)
            self.temp_dir = cache_base
            self.logger.info(f"Répertoire cache TTS: {self.temp_dir}")
            
            # Vérifier Piper TTS
            if not await self._check_piper_installation():
                self.logger.error("Piper TTS non disponible")
                return False
            
            self.is_active = True
            self.logger.info("Module TTS GLaDOS initialisé avec succès")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur initialisation TTS GLaDOS: {e}")
            return False
    
    async def _check_piper_installation(self) -> bool:
        """Vérifie que Piper TTS est installé et accessible"""
        try:
            # Essayer d'importer piper
            try:
                import piper
                self.use_piper_library = True
                self.logger.info("Utilisation de la librairie Piper TTS")
                return True
            except ImportError:
                pass
            
            # Essayer la commande piper
            result = subprocess.run(['piper', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.use_piper_library = False
                self.logger.info("Utilisation de la commande piper")
                return True
            
            self.logger.error("Piper TTS non trouvé. Installez avec: pip install piper-tts")
            return False
            
        except Exception as e:
            self.logger.error(f"Erreur vérification Piper: {e}")
            return False
    
    async def send_message(self, message: GLaDOSMessage) -> bool:
        """
        Synthétise et joue un message texte avec la voix GLaDOS
        """
        if not self.is_active:
            self.logger.warning("Module TTS GLaDOS non actif")
            return False
        
        if message.message_type not in [MessageType.TEXT, MessageType.ERROR]:
            # Ce module ne traite que le texte
            return False
        
        try:
            text = message.content.strip()
            if not text:
                return True  # Rien à dire

            # Nettoyer les anciens fichiers temporaires avant la synthèse
            self._cleanup_old_temp_files()

            text = text.replace('GLaDOS', 'Gladoss')
            self.logger.info(f"Synthèse TTS: '{text}'")
            
            # Générer l'audio
            audio_file = await self._synthesize_text(text)
            if not audio_file:
                return False
            
            # Jouer l'audio
            success = await self._play_audio(audio_file)

            # Nettoyer le fichier temporaire immédiatement après lecture
            try:
                if audio_file.exists():
                    audio_file.unlink()
                    self.logger.debug(f"Fichier temporaire supprimé: {audio_file}")

            except Exception as cleanup_error:
                self.logger.warning(f"Impossible de supprimer le fichier temporaire {audio_file}: {cleanup_error}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Erreur envoi message TTS: {e}")
            return False
    
    async def _synthesize_text(self, text: str) -> Path:
        """
        Synthétise le texte en audio GLaDOS

        Returns:
            Chemin vers le fichier audio généré
        """
        try:
            output_file = self.temp_dir / f"glados_output_{asyncio.get_event_loop().time()}.wav"

            self.logger.info(f"Début synthèse: '{text[:50]}...' vers {output_file}")
            self.logger.info(f"Méthode utilisée: {'librairie Piper' if self.use_piper_library else 'commande piper'}")

            if self.use_piper_library:
                # Utiliser la librairie Piper
                success = await self._synthesize_with_library(text, output_file)
            else:
                # Utiliser la commande piper
                success = await self._synthesize_with_command(text, output_file)

            if success and output_file.exists():
                file_size = output_file.stat().st_size
                self.logger.info(f"Synthèse réussie - Fichier: {file_size} octets")

                if file_size <= 44:  # Seulement l'en-tête WAV
                    self.logger.error("DIAGNOSTIC: Fichier audio vide (44 octets = en-tête WAV seulement)")
                    return None

                return output_file
            else:
                self.logger.error("Échec de la synthèse TTS")
                if output_file.exists():
                    self.logger.error(f"Fichier existe mais échec reporté - Taille: {output_file.stat().st_size} octets")
                return None

        except Exception as e:
            self.logger.error(f"Erreur synthèse TTS: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    async def _synthesize_with_library(self, text: str, output_file: Path) -> bool:
        """Synthèse avec la librairie Piper - AVEC AUDIO_INT16_BYTES"""
        try:
            from piper import PiperVoice

            self.logger.info(f"Chargement du modèle: {self.model_path}")
            # Charger le modèle
            voice = PiperVoice.load(str(self.model_path))
            self.logger.info(f"Modèle chargé avec succès - Sample rate: {voice.config.sample_rate}")

            # Synthèse avec extraction correcte des AudioChunk
            self.logger.info(f"Synthèse TTS : '{text[:50]}...'")

            # Collecte des données audio depuis le générateur
            audio_data = b""
            chunk_count = 0

            for chunk in voice.synthesize(text):
                if hasattr(chunk, 'audio_int16_bytes'):
                    audio_data += chunk.audio_int16_bytes
                    chunk_count += 1
                else:
                    self.logger.warning(f"Chunk sans audio_int16_bytes: {type(chunk)}, attributs: {dir(chunk)}")

            self.logger.info(f"Audio collecté: {len(audio_data)} octets en {chunk_count} chunks")

            if not audio_data:
                self.logger.error("Aucune donnée audio générée par Piper")
                return False

            # Écriture du fichier WAV avec les données collectées
            with wave.open(str(output_file), "wb") as wav_file:
                wav_file.setframerate(voice.config.sample_rate)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setnchannels(1)  # mono
                wav_file.writeframes(audio_data)

            # Vérification finale
            file_size = output_file.stat().st_size
            self.logger.info(f"Synthèse terminée - Fichier généré: {file_size} octets")

            if file_size <= 44:
                self.logger.error("PROBLÈME: Fichier audio vide (seulement en-tête WAV)")
                return False

            self.logger.info("Synthèse TTS réussie avec audio_int16_bytes!")
            return True

        except Exception as e:
            self.logger.error(f"Erreur synthèse librairie: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    async def _synthesize_with_command(self, text: str, output_file: Path) -> bool:
        """Synthèse avec la commande piper"""
        try:
            # Préparer la commande
            cmd = [
                'piper',
                '--model', str(self.model_path),
                '--output_file', str(output_file)
            ]
            
            # Exécuter avec le texte en stdin
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate(input=text.encode())
            
            if process.returncode == 0:
                return True
            else:
                self.logger.error(f"Erreur commande piper: {stderr.decode()}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erreur synthèse commande: {e}")
            return False
    
    async def _play_audio(self, audio_file: Path) -> bool:
        """
        Joue un fichier audio
        """
        try:
            # Lire le fichier WAV
            with wave.open(str(audio_file), 'rb') as wf:
                sample_rate = wf.getframerate()
                frames = wf.readframes(wf.getnframes())
                
                # Convertir en numpy array
                audio_data = np.frombuffer(frames, dtype=np.int16)
                
                # Normaliser et ajuster le volume
                audio_data = audio_data.astype(np.float32) / 32768.0
                audio_data *= self.volume

                # Vérifier la validité du device
                device_id = self.device_id
                try:
                    sd.check_output_settings(device=device_id)
                except Exception as e:
                    self.logger.warning(f"Device {device_id} non disponible, utilisation du device par défaut. Erreur: {e}")
                    device_id = None
                # Jouer l'audio
                sd.play(audio_data, samplerate=sample_rate, device=device_id)
                sd.wait()  # Attendre la fin de la lecture
            
            self.logger.info("Audio GLaDOS joué avec succès")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lecture audio: {e}")
            return False
    
    def can_handle_message_type(self, message_type: MessageType) -> bool:
        """Vérifie si ce module peut traiter ce type de message"""
        return message_type in [MessageType.TEXT, MessageType.ERROR]
    
    async def cleanup(self) -> None:
        """Nettoie les ressources (garde le dossier cache permanent)"""
        self.is_active = False

        # Nettoyer seulement les fichiers audio, pas le dossier cache
        if self.temp_dir and self.temp_dir.exists():
            try:
                # Supprimer seulement les fichiers audio temporaires
                temp_files = list(self.temp_dir.glob("*.wav"))
                for temp_file in temp_files:
                    try:
                        temp_file.unlink()
                        self.logger.debug(f"Fichier temporaire supprimé: {temp_file.name}")
                    except Exception as file_error:
                        self.logger.warning(f"Impossible de supprimer {temp_file.name}: {file_error}")

                self.logger.info(f"Fichiers temporaires TTS nettoyés (dossier cache conservé): {self.temp_dir}")

            except Exception as e:
                self.logger.error(f"Erreur nettoyage fichiers temporaires: {e}")

        self.logger.info("Module TTS GLaDOS nettoyé")

    def _cleanup_old_temp_files(self):
        """Nettoie les anciens fichiers audio uniquement (garde le dossier cache)"""
        import time

        current_time = time.time()
        one_hour_ago = current_time - 3600  # 1 heure

        try:
            # Nettoyer seulement les anciens fichiers audio dans le cache
            if self.temp_dir and self.temp_dir.exists():
                for temp_file in self.temp_dir.glob("glados_output_*.wav"):
                    if temp_file.stat().st_mtime < one_hour_ago:
                        try:
                            temp_file.unlink()
                            self.logger.debug(f"Ancien fichier temporaire supprimé: {temp_file.name}")
                        except Exception as e:
                            self.logger.debug(f"Impossible de supprimer l'ancien fichier {temp_file.name}: {e}")

        except Exception as e:
            self.logger.debug(f"Erreur lors du nettoyage des anciens fichiers: {e}")