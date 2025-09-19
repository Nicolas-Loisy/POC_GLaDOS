"""
Module d'entrée Terminal pour GLaDOS
Interface en ligne de commande avec historique
"""

import asyncio
import sys
import logging
from typing import Dict, Any, List

try:
    import aioconsole
    HAS_AIOCONSOLE = True
except ImportError:
    HAS_AIOCONSOLE = False

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
    
    async def initialize(self) -> bool:
        """Initialise le module terminal"""
        try:
            self.logger.info("Initialisation du module Terminal...")
            self.is_active = True
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
        print(f"\n=== Terminal GLaDOS démarré ===")
        print(f"Commandes disponibles: help, test, exit")
        print(f"Tapez une commande après le prompt (Ctrl+C pour quitter):\n")

        try:
            while self.is_active:
                try:
                    # Utiliser aioconsole si disponible, sinon fallback
                    if HAS_AIOCONSOLE:
                        user_input = await aioconsole.ainput(self.prompt)
                    else:
                        # Fallback avec run_in_executor
                        print(self.prompt, end='', flush=True)
                        loop = asyncio.get_event_loop()
                        user_input = await loop.run_in_executor(None, input)

                    user_input = user_input.strip()
                    print(f"[DEBUG] Entrée reçue: '{user_input}'")

                    if not user_input:
                        continue

                    # Commandes spéciales
                    if user_input.lower() in ['exit', 'quit', 'q']:
                        print("Au revoir!")
                        self.is_active = False
                        await self.emit_event(GLaDOSEvent(
                            'terminal_exit_requested',
                            source=self.name
                        ))
                        break

                    elif user_input.lower() in ['help', '?']:
                        print("=== Aide GLaDOS ===")
                        print("test - Test du terminal")
                        print("help - Afficher cette aide")
                        print("exit - Quitter GLaDOS")
                        print("Ctrl+C - Arrêt d'urgence")
                        print("==================")
                        continue

                    elif user_input.lower() == 'test':
                        print("✓ Test réussi - Le terminal fonctionne correctement!")
                        continue

                    elif user_input.lower() == 'clear':
                        import os
                        os.system('cls' if os.name == 'nt' else 'clear')
                        continue

                    # Ajouter à l'historique
                    self._add_to_history(user_input)

                    # Traiter comme message normal
                    print(f"[DEBUG] Envoi vers GLaDOS: '{user_input}'")
                    await self._process_input(user_input)
                    print(f"[DEBUG] Message envoyé")

                except asyncio.CancelledError:
                    print("\nAnnulation détectée...")
                    self.is_active = False
                    break
                except (EOFError, KeyboardInterrupt):
                    print("\nArrêt demandé (Ctrl+C détecté)...")
                    self.is_active = False
                    await self.emit_event(GLaDOSEvent(
                        'terminal_exit_requested',
                        source=self.name
                    ))
                    break
                except Exception as e:
                    print(f"Erreur: {e}")
                    self.logger.error(f"Erreur dans la boucle terminal: {e}")
                    continue

        except asyncio.CancelledError:
            self.logger.info("Boucle terminal annulée")
        except Exception as e:
            self.logger.error(f"Erreur fatale dans le terminal: {e}")

        print("Terminal fermé.")
    
    def _get_input(self) -> str:
        """Récupère l'entrée utilisateur (méthode synchrone) - DEPRECATED"""
        # Cette méthode n'est plus utilisée depuis la refactorisation
        pass
    
    async def _process_input(self, user_input: str) -> None:
        """Traite l'entrée utilisateur comme message GLaDOS"""
        try:
            self.logger.info(f"Traitement de l'entrée: '{user_input}'")

            message = GLaDOSMessage(
                content=user_input,
                message_type=MessageType.TEXT,
                source=self.name,
                metadata={
                    "method": "terminal_input",
                    "timestamp": asyncio.get_event_loop().time()
                }
            )

            self.logger.info(f"Émission du message avec {len(self._message_handlers)} handlers")
            await self.emit_message(message)

            await self.emit_event(GLaDOSEvent(
                'terminal_message_sent',
                data={'text': user_input},
                source=self.name
            ))

        except Exception as e:
            self.logger.error(f"Erreur traitement entrée terminal: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
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
        self.logger.info("Module Terminal nettoyé")