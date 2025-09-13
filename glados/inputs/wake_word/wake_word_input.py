"""
Module d'entrée Wake Word + Speech-to-Text pour GLaDOS
Basé sur les POCs existants avec Porcupine et Vosk
"""

import asyncio
import queue
import json
import numpy as np
import sounddevice as sd
import pvporcupine
from vosk import Model, KaldiRecognizer
import logging
from typing import Dict, Any
import time

from ...core.interfaces import InputModule, GLaDOSMessage, MessageType, GLaDOSEvent


class WakeWordInput(InputModule):
    """
    Module d'entrée pour la détection de wake word et reconnaissance vocale
    Utilise Porcupine pour la détection de wake word et Vosk pour STT
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.logger = logging.getLogger(__name__)
        
        # Configuration wake word
        self.porcupine_access_key = config.get('porcupine_access_key')
        self.model_path = config.get('model_path', 'wake_word_model/porcupine_params_de.pv')
        self.keyword_paths = config.get('keyword_paths', ['wake_words/glados_de_windows_v3_0_0.ppn'])
        
        # Configuration STT
        self.stt_config = config.get('stt', {})
        self.stt_model_path = self.stt_config.get('model_path', 'vosk-model-small-fr-0.22')
        self.sample_rate = self.stt_config.get('sample_rate', 16000)
        self.device_id = self.stt_config.get('device_id', None)
        self.max_recording_duration = self.stt_config.get('max_recording_duration', 8)
        self.silence_threshold = self.stt_config.get('silence_threshold', 500)
        self.min_silence_duration = self.stt_config.get('min_silence_duration', 1.0)
        
        # Composants audio
        self.porcupine = None
        self.vosk_model = None
        self.recognizer = None
        self.audio_queue = None
        self.stream = None
        
        # État
        self.listening_for_wake_word = False
        self.recording_speech = False
        self.audio_task = None
        
        if not self.porcupine_access_key:
            raise ValueError("Clé d'accès Porcupine requise")
    
    async def initialize(self) -> bool:
        """Initialise les composants de reconnaissance vocale"""
        try:
            self.logger.info("Initialisation du module Wake Word...")
            
            # Initialiser Porcupine
            self.porcupine = pvporcupine.create(
                access_key=self.porcupine_access_key,
                model_path=self.model_path,
                keyword_paths=self.keyword_paths
            )
            self.logger.info(f"Porcupine initialisé avec {len(self.keyword_paths)} wake words")
            
            # Initialiser Vosk
            self.vosk_model = Model(self.stt_model_path)
            self.recognizer = KaldiRecognizer(self.vosk_model, self.sample_rate)
            self.logger.info("Vosk STT initialisé")
            
            # Initialiser la queue audio
            self.audio_queue = queue.Queue()
            
            self.logger.info("Module Wake Word initialisé avec succès")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur initialisation Wake Word: {e}")
            return False
    
    def _audio_callback(self, indata, frames, time, status):
        """Callback pour le stream audio"""
        if status:
            self.logger.warning(f"Audio callback status: {status}")
        self.audio_queue.put(indata.copy())
    
    async def start_listening(self) -> None:
        """Démarre l'écoute du wake word"""
        if self.listening_for_wake_word:
            self.logger.warning("Wake Word déjà en écoute")
            return
        
        try:
            self.logger.info("Démarrage de l'écoute wake word...")
            self.listening_for_wake_word = True
            
            # Démarrer le stream audio
            self.stream = sd.InputStream(
                channels=1,
                samplerate=self.sample_rate,
                callback=self._audio_callback,
                blocksize=512,
                device=self.device_id
            )
            self.stream.start()
            
            # Démarrer la tâche de traitement audio
            self.audio_task = asyncio.create_task(self._process_audio())
            
            await self.emit_event(GLaDOSEvent('wake_word_listening_started', source=self.name))
            self.logger.info("Wake Word en écoute")
            
        except Exception as e:
            self.logger.error(f"Erreur démarrage wake word: {e}")
            self.listening_for_wake_word = False
    
    async def stop_listening(self) -> None:
        """Arrête l'écoute du wake word"""
        if not self.listening_for_wake_word:
            return
        
        self.logger.info("Arrêt de l'écoute wake word...")
        self.listening_for_wake_word = False
        self.recording_speech = False
        
        if self.audio_task:
            self.audio_task.cancel()
            try:
                await self.audio_task
            except asyncio.CancelledError:
                pass
        
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        await self.emit_event(GLaDOSEvent('wake_word_listening_stopped', source=self.name))
        self.logger.info("Wake Word arrêté")
    
    async def _process_audio(self) -> None:
        """Traite l'audio en continu pour détecter wake words et STT"""
        try:
            while self.listening_for_wake_word:
                if self.audio_queue.empty():
                    await asyncio.sleep(0.01)
                    continue
                
                # Récupérer les données audio
                try:
                    audio_data = self.audio_queue.get_nowait()
                except queue.Empty:
                    continue
                
                pcm = (audio_data.flatten() * 32767).astype(np.int16)
                
                if not self.recording_speech:
                    # Mode détection wake word
                    await self._process_wake_word_detection(pcm)
                else:
                    # Mode enregistrement vocal
                    await self._process_speech_recording(pcm)
                    
        except asyncio.CancelledError:
            self.logger.info("Tâche de traitement audio annulée")
        except Exception as e:
            self.logger.error(f"Erreur traitement audio: {e}")
    
    async def _process_wake_word_detection(self, pcm: np.ndarray) -> None:
        """Traite l'audio pour détecter le wake word"""
        try:
            # Découper en frames pour Porcupine
            for i in range(0, len(pcm), self.porcupine.frame_length):
                frame = pcm[i:i + self.porcupine.frame_length]
                if len(frame) == self.porcupine.frame_length:
                    keyword_index = self.porcupine.process(frame)
                    if keyword_index >= 0:
                        self.logger.info(f"Wake word détecté (index: {keyword_index})")
                        await self.emit_event(GLaDOSEvent(
                            'wake_word_detected', 
                            data={'keyword_index': keyword_index},
                            source=self.name
                        ))
                        
                        # Passer en mode enregistrement
                        await self._start_speech_recording()
                        break
                        
        except Exception as e:
            self.logger.error(f"Erreur détection wake word: {e}")
    
    async def _start_speech_recording(self) -> None:
        """Démarre l'enregistrement de la parole après wake word"""
        self.logger.info("Début d'enregistrement vocal...")
        self.recording_speech = True
        self.speech_frames = []
        self.recording_start_time = time.time()
        self.silence_frame_count = 0
        
        # Réinitialiser le recognizer
        self.recognizer = KaldiRecognizer(self.vosk_model, self.sample_rate)
        
        await self.emit_event(GLaDOSEvent('speech_recording_started', source=self.name))
    
    async def _process_speech_recording(self, pcm: np.ndarray) -> None:
        """Traite l'audio en mode enregistrement vocal"""
        try:
            # Ajouter les frames à l'enregistrement
            self.speech_frames.append(pcm)
            
            # Traiter avec Vosk
            if self.recognizer.AcceptWaveform(pcm.tobytes()):
                result = json.loads(self.recognizer.Result())
                text = result.get("text", "").strip()
                
                if text:
                    await self._handle_speech_result(text, final=True)
                    return
            
            # Vérifier conditions d'arrêt
            await self._check_recording_stop_conditions(pcm)
            
        except Exception as e:
            self.logger.error(f"Erreur enregistrement vocal: {e}")
            await self._stop_speech_recording()
    
    async def _check_recording_stop_conditions(self, pcm: np.ndarray) -> None:
        """Vérifie si l'enregistrement doit s'arrêter"""
        current_time = time.time()
        recording_duration = current_time - self.recording_start_time
        
        # Arrêt par durée maximale
        if recording_duration > self.max_recording_duration:
            self.logger.info("Durée maximale d'enregistrement atteinte")
            await self._finalize_speech_recording()
            return
        
        # Détection de silence
        if self._detect_silence(pcm):
            self.silence_frame_count += 1
        else:
            self.silence_frame_count = 0
        
        # Arrêt par silence prolongé
        silence_frames_threshold = int(self.min_silence_duration * self.sample_rate / len(pcm))
        if self.silence_frame_count >= silence_frames_threshold:
            self.logger.info("Silence détecté, fin d'enregistrement")
            await self._finalize_speech_recording()
    
    def _detect_silence(self, pcm: np.ndarray) -> bool:
        """Détecte le silence dans un frame audio"""
        energy = np.abs(pcm).mean()
        return energy < self.silence_threshold
    
    async def _finalize_speech_recording(self) -> None:
        """Finalise l'enregistrement et traite le résultat"""
        try:
            # Obtenir le résultat final de Vosk
            final_result = json.loads(self.recognizer.FinalResult())
            text = final_result.get("text", "").strip()
            
            if text:
                await self._handle_speech_result(text, final=True)
            else:
                # Pas de texte reconnu
                self.logger.info("Aucun texte reconnu")
                await self.emit_event(GLaDOSEvent(
                    'speech_no_text_detected',
                    source=self.name
                ))
            
        except Exception as e:
            self.logger.error(f"Erreur finalisation enregistrement: {e}")
        
        finally:
            await self._stop_speech_recording()
    
    async def _handle_speech_result(self, text: str, final: bool = False) -> None:
        """Traite le résultat de reconnaissance vocale"""
        self.logger.info(f"Texte reconnu: '{text}' (final: {final})")
        
        if text and final:
            # Créer le message GLaDOS
            message = GLaDOSMessage(
                content=text,
                message_type=MessageType.VOICE,
                source=self.name,
                metadata={
                    "confidence": "high",  # Vosk ne fournit pas de score de confiance
                    "language": "fr",
                    "method": "wake_word_stt"
                }
            )
            
            # Émettre le message
            await self.emit_message(message)
            
            # Émettre l'événement
            await self.emit_event(GLaDOSEvent(
                'speech_text_recognized',
                data={'text': text},
                source=self.name
            ))
    
    async def _stop_speech_recording(self) -> None:
        """Arrête l'enregistrement vocal et retourne en mode wake word"""
        self.recording_speech = False
        self.speech_frames = []
        
        await self.emit_event(GLaDOSEvent('speech_recording_stopped', source=self.name))
        self.logger.info("Retour en mode écoute wake word")
    
    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        await self.stop_listening()
        
        if self.porcupine:
            self.porcupine.delete()
            self.porcupine = None
        
        self.vosk_model = None
        self.recognizer = None
        
        if self.audio_queue:
            # Vider la queue
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break
            self.audio_queue = None
        
        self.logger.info("Module Wake Word nettoyé")