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
            
            # Vérifier que le modèle existe
            model_file = Path(self.model_path)
            if not model_file.exists():
                self.logger.error(f"Modèle TTS GLaDOS non trouvé: {self.model_path}")
                self.logger.info("Téléchargez le modèle depuis: https://huggingface.co/rhasspy/piper-voices")
                return False
            
            # Créer répertoire temporaire pour les fichiers audio
            self.temp_dir = Path(tempfile.mkdtemp(prefix="glados_tts_"))
            self.logger.info(f"Répertoire temporaire TTS: {self.temp_dir}")
            
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
            
            self.logger.info(f"Synthèse TTS: '{text}'")
            
            # Générer l'audio
            audio_file = await self._synthesize_text(text)
            if not audio_file:
                return False
            
            # Jouer l'audio
            success = await self._play_audio(audio_file)
            
            # Nettoyer le fichier temporaire
            try:
                audio_file.unlink()
            except:
                pass
            
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
            
            if self.use_piper_library:
                # Utiliser la librairie Piper
                success = await self._synthesize_with_library(text, output_file)
            else:
                # Utiliser la commande piper
                success = await self._synthesize_with_command(text, output_file)
            
            if success and output_file.exists():
                return output_file
            else:
                self.logger.error("Échec de la synthèse TTS")
                return None
                
        except Exception as e:
            self.logger.error(f"Erreur synthèse TTS: {e}")
            return None
    
    async def _synthesize_with_library(self, text: str, output_file: Path) -> bool:
        """Synthèse avec la librairie Piper"""
        try:
            from piper import PiperVoice
            
            # Charger le modèle
            voice = PiperVoice.load(str(self.model_path))
            
            # Synthétiser
            with wave.open(str(output_file), "wb") as wav_file:
                wav_file.setframerate(voice.config.sample_rate)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setnchannels(1)  # mono
                
                voice.synthesize(text, wav_file)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur synthèse librairie: {e}")
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
                
                # Jouer l'audio
                sd.play(audio_data, samplerate=sample_rate, device=self.device_id)
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
        """Nettoie les ressources"""
        self.is_active = False
        
        # Nettoyer le répertoire temporaire
        if self.temp_dir and self.temp_dir.exists():
            try:
                import shutil
                shutil.rmtree(self.temp_dir)
                self.logger.info("Répertoire temporaire TTS nettoyé")
            except Exception as e:
                self.logger.error(f"Erreur nettoyage répertoire temporaire: {e}")
        
        self.logger.info("Module TTS GLaDOS nettoyé")