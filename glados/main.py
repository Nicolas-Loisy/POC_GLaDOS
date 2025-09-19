"""
Application principale GLaDOS
Point d'entrée principal pour l'assistant vocal
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

from .config.config_manager import ConfigManager
from .core.react_engine import GLaDOSReActEngine
from .tools.adapters import ToolRegistry
from .inputs import input_registry  # Import pour auto-enregistrement
from .outputs import output_registry  # Import pour auto-enregistrement


class GLaDOSApplication:
    """
    Application principale GLaDOS
    Orchestrateur de haut niveau qui gère le cycle de vie complet
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config_manager = ConfigManager()
        self.engine: Optional[GLaDOSReActEngine] = None
        self.is_running = False
        self._shutdown_event = asyncio.Event()
    
    async def initialize(self, config_path: str = "config.yaml") -> bool:
        """
        Initialise l'application GLaDOS
        
        Args:
            config_path: Chemin vers le fichier de configuration
        """
        try:
            self.logger.info("=== Démarrage de GLaDOS Assistant Vocal ===")
            
            # 1. Charger la configuration
            self.logger.info("Chargement de la configuration...")
            config = self.config_manager.load_config(config_path)
            
            # 2. Initialiser les registres
            self.logger.info("Initialisation des registres de modules...")
            ToolRegistry.initialize()
            # Les registres input/output sont auto-initialisés par les imports
            
            # 3. Créer et initialiser le moteur ReAct
            self.logger.info("Initialisation du moteur ReAct...")
            self.engine = GLaDOSReActEngine(config)
            
            if not await self.engine.initialize():
                self.logger.error("Échec de l'initialisation du moteur")
                return False
            
            # 4. Configurer les gestionnaires de signaux
            self._setup_signal_handlers()
            
            self.logger.info("GLaDOS initialisé avec succès!")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'initialisation: {e}", exc_info=True)
            return False
    
    def _setup_signal_handlers(self):
        """Configure les gestionnaires de signaux pour un arrêt propre"""
        def signal_handler(signum, frame):
            self.logger.info(f"Signal {signum} reçu, arrêt de GLaDOS...")
            # Déclencher l'événement d'arrêt au lieu de créer une task
            self._shutdown_event.set()

        # Gérer Ctrl+C et autres signaux d'arrêt
        if sys.platform != 'win32':
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        else:
            # Windows ne supporte que SIGINT
            signal.signal(signal.SIGINT, signal_handler)
    
    async def run(self) -> None:
        """
        Lance GLaDOS et maintient l'exécution
        """
        if not self.engine:
            self.logger.error("GLaDOS non initialisé")
            return
        
        try:
            self.logger.info("Démarrage de GLaDOS...")
            self.is_running = True
            
            # Démarrer le moteur
            await self.engine.start()
            
            self.logger.info("GLaDOS est maintenant actif!")
            self.logger.info("Utilisez Ctrl+C pour arrêter")
            
            # Attendre le signal d'arrêt avec un timeout pour éviter les blocages
            try:
                await self._shutdown_event.wait()
            except KeyboardInterrupt:
                self.logger.info("KeyboardInterrupt dans la boucle principale")
                self._shutdown_event.set()
            
        except KeyboardInterrupt:
            self.logger.info("Interruption clavier détectée")
        except Exception as e:
            self.logger.error(f"Erreur durant l'exécution: {e}", exc_info=True)
        finally:
            await self.shutdown()
    
    async def shutdown(self) -> None:
        """
        Arrêt propre de GLaDOS
        """
        if not self.is_running:
            return

        self.logger.info("Arrêt de GLaDOS en cours...")
        self.is_running = False

        try:
            if self.engine:
                # Arrêter avec un timeout pour éviter les blocages
                await asyncio.wait_for(self.engine.stop(), timeout=5.0)

            self.logger.info("GLaDOS arrêté proprement")

        except asyncio.TimeoutError:
            self.logger.warning("Timeout lors de l'arrêt, forçage de l'arrêt")
        except Exception as e:
            self.logger.error(f"Erreur durant l'arrêt: {e}")
        finally:
            self._shutdown_event.set()

            # Forcer l'arrêt des tâches asyncio restantes
            tasks = [task for task in asyncio.all_tasks() if not task.done()]
            if tasks:
                self.logger.info(f"Annulation de {len(tasks)} tâches restantes...")
                for task in tasks:
                    task.cancel()

                try:
                    await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=2.0)
                except asyncio.TimeoutError:
                    self.logger.warning("Timeout lors de l'arrêt des tâches")
    
    def is_active(self) -> bool:
        """Retourne l'état de l'application"""
        return self.is_running


def setup_logging(level: str = "INFO") -> None:
    """
    Configure le système de logging
    """
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("glados.log")
        ]
    )
    
    # Réduire le niveau de logging pour certains modules externes
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("llama_index").setLevel(logging.WARNING)


async def main():
    """
    Point d'entrée principal asynchrone
    """
    # Configuration du logging
    setup_logging("INFO")
    
    # Créer et lancer l'application
    app = GLaDOSApplication()
    
    # Chercher le fichier de configuration
    config_file = "config.yaml"
    if not Path(config_file).exists():
        print(f"Fichier de configuration non trouvé: {config_file}")
        print("Copiez config.yaml.example vers config.yaml et configurez-le")
        return 1
    
    # Initialiser et lancer
    if await app.initialize(config_file):
        await app.run()
        return 0
    else:
        print("Échec de l'initialisation de GLaDOS")
        return 1


def cli_main():
    """
    Point d'entrée pour la ligne de commande
    """
    import sys

    def force_exit_handler(signum, frame):
        print(f"\n!!! Arrêt forcé (signal {signum}) !!!")
        sys.exit(1)

    # Gestionnaire d'arrêt forcé pour double Ctrl+C
    signal.signal(signal.SIGINT, force_exit_handler)

    try:
        return asyncio.run(main())
    except KeyboardInterrupt:
        print("\nArrêt demandé par l'utilisateur")
        return 0
    except Exception as e:
        print(f"Erreur fatale: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(cli_main())