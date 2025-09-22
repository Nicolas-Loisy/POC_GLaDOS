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

        @self.app.post("/api/message")
        async def send_message(request: MessageRequest):
            await self._send_message(request.message)
            return {"success": True, "timestamp": datetime.now().isoformat()}

        @self.app.get("/api/status")
        async def get_status():
            return {
                "status": "active" if self.is_active else "inactive",
                "connections": len(self.websocket_connections)
            }

        @self.app.post("/api/test")
        async def test_message():
            await self._send_message("Test de l'interface web")
            return {"success": True, "message": "Test envoyé"}

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
        """Démarre le serveur web"""
        if not self.app:
            return

        try:
            self.server_thread = Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            await asyncio.sleep(1)
            self.logger.info(f"Interface web disponible sur http://{self.host}:{self.port}")
        except Exception as e:
            self.logger.error(f"Erreur démarrage serveur: {e}")

    def _run_server(self):
        """Exécute le serveur Uvicorn"""
        try:
            uvicorn.run(self.app, host=self.host, port=self.port, log_level="warning")
        except Exception as e:
            self.logger.error(f"Erreur serveur: {e}")

    async def stop_listening(self) -> None:
        """Arrête le serveur web"""
        for websocket in list(self.websocket_connections):
            try:
                await websocket.close()
            except:
                pass
        self.websocket_connections.clear()

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