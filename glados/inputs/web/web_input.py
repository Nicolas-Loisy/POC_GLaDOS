"""
Module d'entrée Web pour GLaDOS
Interface web locale avec FastAPI
"""

import asyncio
import logging
from typing import Dict, Any, Set
from pathlib import Path
from datetime import datetime
from threading import Thread

from ...core.interfaces import InputModule, GLaDOSMessage, MessageType

# Vérification des dépendances
try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse, FileResponse
    from pydantic import BaseModel
    import uvicorn
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    DEPENDENCIES_AVAILABLE = False
    MISSING_DEPENDENCY = str(e)

if DEPENDENCIES_AVAILABLE:
    class MessageRequest(BaseModel):
        message: str
        type: str = "text"


class WebInput(InputModule):
    """Module d'entrée web simplifié"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.logger = logging.getLogger(__name__)

        # Configuration
        self.host = config.get('host', '127.0.0.1')
        self.port = config.get('port', 8080)
        self.title = config.get('title', 'GLaDOS Assistant Web')

        # Ressources
        self.app = None
        self.server_thread = None
        self.uvicorn_server = None
        self.websocket_connections: Set[WebSocket] = set()
        self.templates_dir = Path(__file__).parent / "templates"
        self.static_dir = Path(__file__).parent / "static"

        if DEPENDENCIES_AVAILABLE:
            self.app = FastAPI(title=self.title)
        else:
            self.logger.error(f"Dépendances manquantes: {MISSING_DEPENDENCY}")
    
    async def initialize(self) -> bool:
        """Initialise le serveur web"""
        if not DEPENDENCIES_AVAILABLE:
            self.logger.error("FastAPI non disponible")
            return False

        try:
            self._setup_routes()
            self._setup_cors()
            self.logger.info("Module Web initialisé")
            return True
        except Exception as e:
            self.logger.error(f"Erreur initialisation: {e}")
            return False
    
    def _setup_routes(self):
        """Configure les routes FastAPI"""
        if not self.app:
            return

        @self.app.get("/", response_class=HTMLResponse)
        async def get_interface():
            return FileResponse(self.templates_dir / "index.html")

        @self.app.get("/config", response_class=HTMLResponse)
        async def get_config_page():
            return FileResponse(self.templates_dir / "config.html")

        @self.app.post("/api/message")
        async def send_message(request: MessageRequest):
            await self._send_message(request.message)
            return {"success": True, "timestamp": datetime.now().isoformat()}

        @self.app.get("/api/status")
        async def get_status():
            # Diagnostic GLaDOS
            from glados.main import get_global_instance
            global_instance = get_global_instance()

            return {
                "status": "active" if self.is_active else "inactive",
                "connections": len(self.websocket_connections),
                "glados_instance_available": global_instance is not None,
                "glados_instance_type": type(global_instance).__name__ if global_instance else None,
                "parent_engine_available": hasattr(self, 'parent_engine') and self.parent_engine is not None,
                "diagnostics": self._get_glados_diagnostics()
            }

        @self.app.get("/api/diagnostics")
        async def get_diagnostics():
            """Diagnostic complet de l'état GLaDOS"""
            return {"diagnostics": self._get_glados_diagnostics()}

        @self.app.post("/api/test")
        async def test_message():
            await self._send_message("Test de l'interface web")
            return {"success": True, "message": "Test envoyé"}

        @self.app.get("/api/config")
        async def get_config():
            """Retourne le contenu du fichier de config YAML"""
            config_path = Path("config.yaml")
            if not config_path.exists():
                raise HTTPException(status_code=404, detail="Fichier de configuration introuvable")
            with open(config_path, "r", encoding="utf-8") as f:
                return {"content": f.read()}

        @self.app.post("/api/config")
        async def save_config(data: Dict[str, Any]):
            """Sauvegarde le contenu du fichier de config YAML"""
            config_path = Path("config.yaml")
            content = data.get("content", "")
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"success": True}

        @self.app.post("/api/reload")
        async def reload_project():
            """Déclenche la réinitialisation du projet (reload config + modules)"""
            try:
                self.logger.info("Rechargement du projet demandé via API")

                # Essayer de trouver l'instance GLaDOS
                glados_instance = None

                # Méthode 1: Instance globale
                from glados.main import get_global_instance
                glados_instance = get_global_instance()

                # Méthode 2: Via le parent engine (si disponible)
                if glados_instance is None and hasattr(self, 'parent_engine'):
                    # Chercher l'instance dans le parent engine
                    parent = self.parent_engine
                    while parent and not hasattr(parent, 'application'):
                        parent = getattr(parent, 'parent', None)
                    if parent and hasattr(parent, 'application'):
                        glados_instance = parent.application
                        # L'enregistrer comme instance globale
                        from glados.main import set_global_instance
                        set_global_instance(glados_instance)

                if glados_instance is None:
                    # Solution de secours: redémarrage via signal
                    self.logger.warning("Instance GLaDOS non disponible - tentative de redémarrage via signal")
                    try:
                        import os
                        import signal

                        # Envoyer SIGUSR1 au processus principal pour déclencher un reload
                        # (nécessite d'ajouter un handler dans main.py)
                        if os.path.exists('/.dockerenv'):
                            # Dans Docker, forcer l'arrêt pour que Docker Compose redémarre
                            self.logger.info("Arrêt forcé du container pour redémarrage")

                            # Programmer l'arrêt après avoir envoyé la réponse
                            import asyncio
                            async def delayed_exit():
                                await asyncio.sleep(1)  # Laisser le temps de renvoyer la réponse
                                self.logger.info("Arrêt du processus Python pour redémarrage Docker")
                                os._exit(1)  # Exit code 1 pour déclencher restart policy

                            # Lancer l'arrêt en arrière-plan
                            asyncio.create_task(delayed_exit())

                            return {"success": True, "message": "Redémarrage en cours - GLaDOS va redémarrer dans 1 seconde"}
                        else:
                            raise HTTPException(status_code=503, detail="Service GLaDOS non disponible. Vérifiez que GLaDOS est correctement démarré via main.py")
                    except Exception as fallback_error:
                        self.logger.error(f"Erreur fallback reload: {fallback_error}")
                        raise HTTPException(status_code=503, detail="Service GLaDOS non disponible. Vérifiez que GLaDOS est correctement démarré via main.py")

                # Appel à la méthode de rechargement
                from glados.main import trigger_reload
                await trigger_reload()
                return {"success": True, "message": "Rechargement effectué"}

            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Erreur reload: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self._handle_websocket(websocket)

        # Fichiers statiques
        if self.static_dir.exists():
            self.app.mount("/static", StaticFiles(directory=str(self.static_dir)), name="static")
    
    def _setup_cors(self):
        """Configure CORS"""
        from fastapi.middleware.cors import CORSMiddleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    async def _send_message(self, content: str):
        """Envoie un message vers GLaDOS"""
        message = GLaDOSMessage(
            content=content,
            message_type=MessageType.TEXT,
            source=self.name,
            metadata={"timestamp": datetime.now().isoformat()}
        )
        await self.emit_message(message)
    
    async def _handle_websocket(self, websocket: WebSocket):
        """Gère une connexion WebSocket simplifiée"""
        await websocket.accept()
        self.websocket_connections.add(websocket)

        try:
            # Message de bienvenue
            await websocket.send_json({
                "type": "welcome",
                "message": "Connexion établie avec GLaDOS",
                "client_id": f"client_{len(self.websocket_connections)}",
                "timestamp": datetime.now().isoformat()
            })

            # Écouter les messages
            while True:
                data = await websocket.receive_json()
                message_type = data.get("type", "message")

                if message_type == "message" and data.get("content"):
                    await self._send_message(data["content"])
                    await websocket.send_json({
                        "type": "confirmation",
                        "message": "Message reçu",
                        "timestamp": datetime.now().isoformat()
                    })
                elif message_type == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    })

        except WebSocketDisconnect:
            pass
        except Exception as e:
            self.logger.error(f"Erreur WebSocket: {e}")
        finally:
            self.websocket_connections.discard(websocket)
    
    async def broadcast_to_websockets(self, message: dict):
        """Diffuse un message vers les WebSockets"""
        disconnected = set()
        for websocket in self.websocket_connections:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.add(websocket)
        self.websocket_connections -= disconnected
    
    
    async def start_listening(self) -> None:
        """Démarre le serveur web avec Uvicorn en mode programme"""
        if not self.app:
            return

        if self.uvicorn_server and not self.uvicorn_server.should_exit:
            self.logger.info("Serveur web déjà lancé.")
            return

        import uvicorn
        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="warning")
        self.uvicorn_server = uvicorn.Server(config)
        loop = asyncio.get_event_loop()
        loop.create_task(self.uvicorn_server.serve())
        await asyncio.sleep(1)
        self.logger.info(f"Interface web disponible sur http://{self.host}:{self.port}")

    def _run_server(self):
        pass  # Obsolète avec le mode programme

    async def stop_listening(self) -> None:
        """Arrête le serveur web et Uvicorn proprement"""
        for websocket in list(self.websocket_connections):
            try:
                await websocket.close()
            except:
                pass
        self.websocket_connections.clear()
        if self.uvicorn_server and not self.uvicorn_server.should_exit:
            self.logger.info("Arrêt du serveur Uvicorn...")
            self.uvicorn_server.should_exit = True

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        await self.stop_listening()

    async def send_response(self, response: str, metadata: Dict[str, Any] = None) -> None:
        """Envoie une réponse GLaDOS vers l'interface web"""
        await self.send_response_to_web(response)

    async def send_response_to_web(self, response: str):
        """Envoie une réponse GLaDOS vers l'interface web"""
        if self.websocket_connections:
            message = {
                "type": "response",
                "message": response,
                "timestamp": datetime.now().isoformat()
            }
            await self.broadcast_to_websockets(message)

    def _get_glados_diagnostics(self):
        """Diagnostic complet de GLaDOS"""
        import sys
        import os

        # Vérifier l'instance globale
        from glados.main import get_global_instance
        global_instance = get_global_instance()

        # Vérifier les modules importés
        glados_modules = [name for name in sys.modules.keys() if name.startswith('glados')]

        # Vérifier les variables d'environnement
        env_vars = {k: v for k, v in os.environ.items() if 'GLADOS' in k.upper()}

        # Vérifier si on est dans Docker
        in_docker = os.path.exists('/.dockerenv')

        # Vérifier le fichier de config
        config_exists = os.path.exists('config.yaml')

        diagnostics = {
            "global_instance": {
                "available": global_instance is not None,
                "type": type(global_instance).__name__ if global_instance else None,
                "initialized": global_instance.is_running if global_instance else False
            },
            "module_info": {
                "parent_engine": hasattr(self, 'parent_engine'),
                "parent_engine_type": type(getattr(self, 'parent_engine', None)).__name__ if hasattr(self, 'parent_engine') else None,
                "loaded_glados_modules": len(glados_modules),
                "modules": glados_modules[:10]  # Limiter pour éviter trop de données
            },
            "environment": {
                "in_docker": in_docker,
                "config_exists": config_exists,
                "env_vars": env_vars,
                "python_path": sys.path[:5]  # Premier éléments du path
            },
            "web_input": {
                "name": self.name,
                "is_active": self.is_active,
                "host": self.host,
                "port": self.port
            }
        }

        return diagnostics