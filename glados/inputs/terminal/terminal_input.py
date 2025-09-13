"""
Module d'entrée Terminal pour GLaDOS
Interface en ligne de commande avec historique
"""

import asyncio
import sys
import logging
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

from ...core.interfaces import InputModule, GLaDOSMessage, MessageType, GLaDOSEvent


class TerminalInput(InputModule):
    """
    Module d'entrée pour interface terminal
    Permet d'interagir avec GLaDOS via ligne de commande
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.logger = logging.getLogger(__name__)
        
        # Configuration terminal
        self.prompt = config.get('prompt', 'GLaDOS> ')
        self.history_size = config.get('history_size', 100)
        
        # État
        self.history: List[str] = []
        self.listening_task = None
        self.executor = ThreadPoolExecutor(max_workers=1)
    
    async def initialize(self) -> bool:
        """Initialise le module terminal"""
        try:
            self.logger.info("Initialisation du module Terminal...")
            self.logger.info("Module Terminal initialisé avec succès")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur initialisation Terminal: {e}")
            return False
    
    async def start_listening(self) -> None:
        """Démarre l'écoute des entrées terminal"""
        if self.listening_task and not self.listening_task.done():
            self.logger.warning("Terminal déjà en écoute")
            return
        
        try:
            self.logger.info("Démarrage de l'interface terminal...")
            print(f"\n=== GLaDOS Assistant Vocal ===")
            print(f"Tapez 'exit' ou 'quit' pour quitter")
            print(f"Tapez 'help' pour voir les commandes disponibles\n")
            
            self.listening_task = asyncio.create_task(self._terminal_loop())
            await self.emit_event(GLaDOSEvent('terminal_listening_started', source=self.name))
            
        except Exception as e:
            self.logger.error(f"Erreur démarrage terminal: {e}")
    
    async def stop_listening(self) -> None:
        """Arrête l'écoute terminal"""
        if self.listening_task and not self.listening_task.done():
            self.listening_task.cancel()
            try:
                await self.listening_task
            except asyncio.CancelledError:
                pass
        
        await self.emit_event(GLaDOSEvent('terminal_listening_stopped', source=self.name))
        self.logger.info("Terminal arrêté")
    
    async def _terminal_loop(self) -> None:
        """Boucle principale d'écoute terminal"""
        try:
            while self.is_active:
                try:
                    # Utiliser l'executor pour éviter de bloquer
                    loop = asyncio.get_event_loop()
                    user_input = await loop.run_in_executor(
                        self.executor, 
                        self._get_input
                    )
                    
                    if user_input is None:  # EOF ou interruption
                        break
                    
                    user_input = user_input.strip()
                    
                    if not user_input:
                        continue
                    
                    # Commandes spéciales
                    if user_input.lower() in ['exit', 'quit', 'q']:
                        print("Au revoir!")
                        await self.emit_event(GLaDOSEvent(
                            'terminal_exit_requested',
                            source=self.name
                        ))
                        break
                    
                    elif user_input.lower() in ['help', '?']:
                        await self._show_help()
                        continue
                    
                    elif user_input.lower() == 'history':
                        await self._show_history()
                        continue
                    
                    elif user_input.lower() == 'clear':
                        self._clear_screen()
                        continue
                    
                    # Ajouter à l'historique
                    self._add_to_history(user_input)
                    
                    # Traiter comme message normal
                    await self._process_input(user_input)
                    
                except KeyboardInterrupt:
                    print("\n\nInterruption détectée. Tapez 'exit' pour quitter.")
                    continue
                except EOFError:
                    print("\nEOF détecté. Arrêt du terminal.")
                    break
                except Exception as e:
                    self.logger.error(f"Erreur dans la boucle terminal: {e}")
                    continue
                    
        except asyncio.CancelledError:
            self.logger.info("Boucle terminal annulée")
        except Exception as e:
            self.logger.error(f"Erreur fatale dans le terminal: {e}")
    
    def _get_input(self) -> str:
        """Récupère l'entrée utilisateur (méthode synchrone)"""
        try:
            return input(self.prompt)
        except (EOFError, KeyboardInterrupt):
            return None
    
    async def _process_input(self, user_input: str) -> None:
        """Traite l'entrée utilisateur comme message GLaDOS"""
        try:
            message = GLaDOSMessage(
                content=user_input,
                message_type=MessageType.TEXT,
                source=self.name,
                metadata={
                    "method": "terminal_input",
                    "timestamp": asyncio.get_event_loop().time()
                }
            )
            
            await self.emit_message(message)
            
            await self.emit_event(GLaDOSEvent(
                'terminal_message_sent',
                data={'text': user_input},
                source=self.name
            ))
            
        except Exception as e:
            self.logger.error(f"Erreur traitement entrée terminal: {e}")
    
    def _add_to_history(self, command: str) -> None:
        """Ajoute une commande à l'historique"""
        if command and command not in ['history', 'clear', 'help']:
            self.history.append(command)
            # Limiter la taille de l'historique
            if len(self.history) > self.history_size:
                self.history.pop(0)
    
    async def _show_help(self) -> None:
        """Affiche l'aide des commandes"""
        help_text = f"""
=== Commandes GLaDOS Terminal ===

Commandes système:
  help, ?     - Affiche cette aide
  history     - Affiche l'historique des commandes
  clear       - Efface l'écran
  exit, quit  - Quitte GLaDOS

Exemples d'interactions:
  "Allume la lampe de chambre"
  "Quelle heure est-il ?"
  "Éteins toutes les lumières"
  "Raconte-moi une blague"

Tapez simplement vos questions ou commandes après le prompt '{self.prompt}'
"""
        print(help_text)
    
    async def _show_history(self) -> None:
        """Affiche l'historique des commandes"""
        if not self.history:
            print("Aucune commande dans l'historique.")
            return
        
        print("\n=== Historique des commandes ===")
        for i, cmd in enumerate(self.history[-10:], 1):  # 10 dernières commandes
            print(f"{i:2d}. {cmd}")
        
        if len(self.history) > 10:
            print(f"... et {len(self.history) - 10} autres commandes")
        print()
    
    def _clear_screen(self) -> None:
        """Efface l'écran"""
        import os
        if os.name == 'nt':  # Windows
            os.system('cls')
        else:  # Unix/Linux/Mac
            os.system('clear')
    
    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        await self.stop_listening()
        
        if self.executor:
            self.executor.shutdown(wait=True)
            self.executor = None
        
        self.logger.info("Module Terminal nettoyé")