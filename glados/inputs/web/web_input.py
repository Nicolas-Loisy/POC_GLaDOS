"""
Module d'entrée Web pour GLaDOS
Interface web locale avec FastAPI pour contrôler l'assistant
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import json
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
from threading import Thread

from ...core.interfaces import InputModule, GLaDOSMessage, MessageType, GLaDOSEvent


class MessageRequest(BaseModel):
    """Modèle pour les requêtes de messages via HTTP"""
    message: str
    type: str = "text"


class WebInput(InputModule):
    """
    Module d'entrée pour interface web
    Utilise FastAPI pour servir une interface web locale
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.logger = logging.getLogger(__name__)
        
        # Configuration web
        self.host = config.get('host', '127.0.0.1')
        self.port = config.get('port', 8080)
        self.title = config.get('title', 'GLaDOS Assistant Web Interface')
        self.enable_cors = config.get('enable_cors', True)
        
        # FastAPI app
        self.app = FastAPI(title=self.title)
        self.server = None
        self.server_thread = None
        
        # WebSocket connections
        self.websocket_connections = set()
        
        # Répertoire des fichiers statiques
        self.static_dir = Path(__file__).parent / "static"
        
        # État des connexions
        self.connection_count = 0
    
    async def initialize(self) -> bool:
        """Initialise le serveur web"""
        try:
            self.logger.info("Initialisation du module Web...")
            
            # Créer le répertoire static s'il n'existe pas
            self.static_dir.mkdir(exist_ok=True)
            
            # Configurer les routes
            self._setup_routes()
            
            # Configurer CORS si activé
            if self.enable_cors:
                self._setup_cors()
            
            self.logger.info("Module Web initialisé avec succès")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur initialisation Web: {e}")
            return False
    
    def _setup_routes(self):
        """Configure les routes FastAPI"""
        
        # Route principale - interface HTML
        @self.app.get("/", response_class=HTMLResponse)
        async def get_interface():
            """Sert l'interface web principale"""
            return self._get_html_interface()
        
        # API REST pour envoyer des messages
        @self.app.post("/api/message")
        async def send_message(request: MessageRequest):
            """Envoie un message via l'API REST"""
            try:
                message = GLaDOSMessage(
                    content=request.message,
                    message_type=MessageType.TEXT,
                    source=self.name,
                    metadata={
                        "method": "web_api",
                        "timestamp": datetime.now().isoformat(),
                        "type": request.type
                    }
                )
                
                await self.emit_message(message)
                
                return {
                    "success": True,
                    "message": "Message envoyé avec succès",
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                self.logger.error(f"Erreur envoi message API: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # WebSocket pour communication temps réel
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """Gère les connexions WebSocket"""
            await self._handle_websocket(websocket)
        
        # API pour obtenir l'état du système
        @self.app.get("/api/status")
        async def get_status():
            """Retourne l'état du système"""
            return {
                "status": "active" if self.is_active else "inactive",
                "connections": len(self.websocket_connections),
                "uptime": self._get_uptime(),
                "server": f"{self.host}:{self.port}"
            }
        
        # Servir les fichiers statiques
        if self.static_dir.exists():
            self.app.mount("/static", StaticFiles(directory=str(self.static_dir)), name="static")
    
    def _setup_cors(self):
        """Configure CORS pour le développement"""
        from fastapi.middleware.cors import CORSMiddleware
        
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    async def _handle_websocket(self, websocket: WebSocket):
        """Gère une connexion WebSocket"""
        await websocket.accept()
        self.websocket_connections.add(websocket)
        self.connection_count += 1
        
        client_id = f"client_{self.connection_count}"
        self.logger.info(f"Nouvelle connexion WebSocket: {client_id}")
        
        try:
            # Envoyer un message de bienvenue
            await websocket.send_json({
                "type": "welcome",
                "message": "Connexion établie avec GLaDOS",
                "client_id": client_id,
                "timestamp": datetime.now().isoformat()
            })
            
            # Écouter les messages
            while True:
                data = await websocket.receive_json()
                await self._process_websocket_message(data, websocket, client_id)
                
        except WebSocketDisconnect:
            self.logger.info(f"Connexion WebSocket fermée: {client_id}")
        except Exception as e:
            self.logger.error(f"Erreur WebSocket {client_id}: {e}")
        finally:
            self.websocket_connections.discard(websocket)
    
    async def _process_websocket_message(self, data: dict, websocket: WebSocket, client_id: str):
        """Traite un message reçu via WebSocket"""
        try:
            message_type = data.get("type", "message")
            content = data.get("content", "")
            
            if message_type == "message" and content:
                # Créer le message GLaDOS
                message = GLaDOSMessage(
                    content=content,
                    message_type=MessageType.TEXT,
                    source=self.name,
                    metadata={
                        "method": "websocket",
                        "client_id": client_id,
                        "timestamp": datetime.now().isoformat()
                    }
                )
                
                # Émettre le message
                await self.emit_message(message)
                
                # Confirmer la réception
                await websocket.send_json({
                    "type": "confirmation",
                    "message": "Message reçu",
                    "original": content,
                    "timestamp": datetime.now().isoformat()
                })
                
            elif message_type == "ping":
                # Répondre au ping
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            self.logger.error(f"Erreur traitement message WebSocket: {e}")
            await websocket.send_json({
                "type": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    async def broadcast_to_websockets(self, message: dict):
        """Diffuse un message à toutes les connexions WebSocket"""
        if not self.websocket_connections:
            return
        
        disconnected = set()
        for websocket in self.websocket_connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                self.logger.warning(f"Erreur envoi WebSocket: {e}")
                disconnected.add(websocket)
        
        # Nettoyer les connexions fermées
        self.websocket_connections -= disconnected
    
    def _get_html_interface(self) -> str:
        """Génère l'interface HTML principale"""
        return """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GLaDOS Assistant Web</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: #fff;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        .header {
            background: rgba(0, 0, 0, 0.3);
            padding: 1rem 2rem;
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .header h1 {
            font-size: 2rem;
            font-weight: 300;
            color: #00d4ff;
            text-shadow: 0 0 20px rgba(0, 212, 255, 0.5);
        }
        
        .status {
            font-size: 0.9rem;
            opacity: 0.8;
            margin-top: 0.5rem;
        }
        
        .container {
            flex: 1;
            display: flex;
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
            gap: 2rem;
            width: 100%;
        }
        
        .chat-section {
            flex: 2;
            display: flex;
            flex-direction: column;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            overflow: hidden;
        }
        
        .chat-header {
            padding: 1rem 1.5rem;
            background: rgba(0, 0, 0, 0.2);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .chat-messages {
            flex: 1;
            padding: 1rem;
            overflow-y: auto;
            max-height: 400px;
            min-height: 300px;
        }
        
        .message {
            margin-bottom: 1rem;
            padding: 0.75rem 1rem;
            border-radius: 10px;
            max-width: 80%;
            word-wrap: break-word;
        }
        
        .message.user {
            background: rgba(0, 212, 255, 0.3);
            border: 1px solid rgba(0, 212, 255, 0.5);
            margin-left: auto;
            text-align: right;
        }
        
        .message.glados {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.3);
        }
        
        .message.system {
            background: rgba(255, 193, 7, 0.2);
            border: 1px solid rgba(255, 193, 7, 0.4);
            text-align: center;
            font-style: italic;
            font-size: 0.9rem;
            margin: 0.5rem auto;
            max-width: 60%;
        }
        
        .message-time {
            font-size: 0.7rem;
            opacity: 0.7;
            margin-top: 0.25rem;
        }
        
        .chat-input {
            padding: 1rem 1.5rem;
            background: rgba(0, 0, 0, 0.2);
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .input-group {
            display: flex;
            gap: 0.5rem;
        }
        
        .input-group input {
            flex: 1;
            padding: 0.75rem 1rem;
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 25px;
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
            font-size: 1rem;
            outline: none;
            backdrop-filter: blur(5px);
        }
        
        .input-group input::placeholder {
            color: rgba(255, 255, 255, 0.6);
        }
        
        .input-group input:focus {
            border-color: #00d4ff;
            box-shadow: 0 0 10px rgba(0, 212, 255, 0.3);
        }
        
        .btn {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 25px;
            background: linear-gradient(45deg, #00d4ff, #0099cc);
            color: #fff;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 1rem;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 212, 255, 0.4);
        }
        
        .btn:active {
            transform: translateY(0);
        }
        
        .controls-section {
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }
        
        .control-panel {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            padding: 1.5rem;
        }
        
        .control-panel h3 {
            margin-bottom: 1rem;
            color: #00d4ff;
            font-weight: 400;
        }
        
        .quick-actions {
            display: grid;
            gap: 0.5rem;
        }
        
        .quick-btn {
            padding: 0.5rem 1rem;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            color: #fff;
            cursor: pointer;
            transition: all 0.2s ease;
            text-align: left;
            font-size: 0.9rem;
        }
        
        .quick-btn:hover {
            background: rgba(255, 255, 255, 0.2);
            border-color: #00d4ff;
        }
        
        .connection-status {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.9rem;
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #28a745;
            animation: pulse 2s infinite;
        }
        
        .status-dot.disconnected {
            background: #dc3545;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        @media (max-width: 768px) {
            .container {
                flex-direction: column;
                padding: 1rem;
            }
            
            .header {
                padding: 1rem;
            }
            
            .header h1 {
                font-size: 1.5rem;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 GLaDOS Assistant</h1>
        <div class="status">
            <div class="connection-status">
                <div class="status-dot" id="statusDot"></div>
                <span id="connectionStatus">Connexion...</span>
            </div>
        </div>
    </div>

    <div class="container">
        <div class="chat-section">
            <div class="chat-header">
                <h3>💬 Conversation</h3>
            </div>
            <div class="chat-messages" id="chatMessages">
                <div class="message system">
                    <div>Interface GLaDOS chargée</div>
                    <div class="message-time" id="initTime"></div>
                </div>
            </div>
            <div class="chat-input">
                <div class="input-group">
                    <input type="text" id="messageInput" placeholder="Tapez votre message à GLaDOS..." />
                    <button class="btn" onclick="sendMessage()">Envoyer</button>
                </div>
            </div>
        </div>

        <div class="controls-section">
            <div class="control-panel">
                <h3>⚡ Actions rapides</h3>
                <div class="quick-actions">
                    <button class="quick-btn" onclick="sendQuickMessage('Allume la lampe de chambre')">
                        💡 Allumer la lampe
                    </button>
                    <button class="quick-btn" onclick="sendQuickMessage('Éteins toutes les lumières')">
                        🌙 Éteindre les lumières
                    </button>
                    <button class="quick-btn" onclick="sendQuickMessage('Quelle heure est-il ?')">
                        🕐 Quelle heure ?
                    </button>
                    <button class="quick-btn" onclick="sendQuickMessage('Quel temps fait-il ?')">
                        🌤️ Météo
                    </button>
                    <button class="quick-btn" onclick="sendQuickMessage('Raconte-moi une blague')">
                        😄 Blague
                    </button>
                </div>
            </div>

            <div class="control-panel">
                <h3>📊 Informations</h3>
                <div id="systemInfo">
                    <p>Chargement...</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        let ws = null;
        let isConnected = false;

        // Éléments DOM
        const messageInput = document.getElementById('messageInput');
        const chatMessages = document.getElementById('chatMessages');
        const statusDot = document.getElementById('statusDot');
        const connectionStatus = document.getElementById('connectionStatus');
        const systemInfo = document.getElementById('systemInfo');
        const initTime = document.getElementById('initTime');

        // Initialiser l'heure de chargement
        initTime.textContent = new Date().toLocaleTimeString();

        // Initialiser la connexion WebSocket
        function initWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            ws = new WebSocket(wsUrl);
            
            ws.onopen = function() {
                isConnected = true;
                updateConnectionStatus('Connecté', true);
                addSystemMessage('Connexion WebSocket établie');
            };
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            };
            
            ws.onclose = function() {
                isConnected = false;
                updateConnectionStatus('Déconnecté', false);
                addSystemMessage('Connexion WebSocket fermée');
                
                // Tentative de reconnexion après 3 secondes
                setTimeout(initWebSocket, 3000);
            };
            
            ws.onerror = function(error) {
                console.error('Erreur WebSocket:', error);
                addSystemMessage('Erreur de connexion');
            };
        }

        // Mettre à jour le statut de connexion
        function updateConnectionStatus(status, connected) {
            connectionStatus.textContent = status;
            statusDot.className = connected ? 'status-dot' : 'status-dot disconnected';
        }

        // Gérer les messages WebSocket reçus
        function handleWebSocketMessage(data) {
            switch(data.type) {
                case 'welcome':
                    addSystemMessage(data.message);
                    break;
                case 'confirmation':
                    // Message de confirmation reçu
                    break;
                case 'response':
                    addGladosMessage(data.message);
                    break;
                case 'pong':
                    // Réponse au ping
                    break;
                default:
                    console.log('Message WebSocket reçu:', data);
            }
        }

        // Envoyer un message
        function sendMessage() {
            const message = messageInput.value.trim();
            if (!message) return;

            if (isConnected && ws.readyState === WebSocket.OPEN) {
                // Envoyer via WebSocket
                ws.send(JSON.stringify({
                    type: 'message',
                    content: message
                }));
                
                addUserMessage(message);
                messageInput.value = '';
            } else {
                // Fallback vers l'API REST
                sendMessageViaAPI(message);
            }
        }

        // Envoyer via l'API REST
        async function sendMessageViaAPI(message) {
            try {
                const response = await fetch('/api/message', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        message: message,
                        type: 'text'
                    })
                });

                if (response.ok) {
                    addUserMessage(message);
                    messageInput.value = '';
                    addSystemMessage('Message envoyé via API');
                } else {
                    addSystemMessage('Erreur lors de l\'envoi du message');
                }
            } catch (error) {
                console.error('Erreur API:', error);
                addSystemMessage('Erreur de connexion API');
            }
        }

        // Envoyer un message rapide
        function sendQuickMessage(message) {
            messageInput.value = message;
            sendMessage();
        }

        // Ajouter un message utilisateur
        function addUserMessage(text) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message user';
            messageDiv.innerHTML = `
                <div>${escapeHtml(text)}</div>
                <div class="message-time">${new Date().toLocaleTimeString()}</div>
            `;
            chatMessages.appendChild(messageDiv);
            scrollToBottom();
        }

        // Ajouter un message GLaDOS
        function addGladosMessage(text) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message glados';
            messageDiv.innerHTML = `
                <div><strong>GLaDOS:</strong> ${escapeHtml(text)}</div>
                <div class="message-time">${new Date().toLocaleTimeString()}</div>
            `;
            chatMessages.appendChild(messageDiv);
            scrollToBottom();
        }

        // Ajouter un message système
        function addSystemMessage(text) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message system';
            messageDiv.innerHTML = `
                <div>${escapeHtml(text)}</div>
                <div class="message-time">${new Date().toLocaleTimeString()}</div>
            `;
            chatMessages.appendChild(messageDiv);
            scrollToBottom();
        }

        // Faire défiler vers le bas
        function scrollToBottom() {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        // Échapper le HTML
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // Charger les informations système
        async function loadSystemInfo() {
            try {
                const response = await fetch('/api/status');
                if (response.ok) {
                    const data = await response.json();
                    systemInfo.innerHTML = `
                        <p><strong>Statut:</strong> ${data.status}</p>
                        <p><strong>Connexions:</strong> ${data.connections}</p>
                        <p><strong>Serveur:</strong> ${data.server}</p>
                    `;
                }
            } catch (error) {
                systemInfo.innerHTML = '<p>Erreur de chargement</p>';
            }
        }

        // Gestion des événements
        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });

        // Ping périodique pour maintenir la connexion
        setInterval(() => {
            if (isConnected && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000);

        // Initialisation
        initWebSocket();
        loadSystemInfo();
        
        // Actualiser les infos système toutes les 10 secondes
        setInterval(loadSystemInfo, 10000);
    </script>
</body>
</html>
        """
    
    def _get_uptime(self) -> str:
        """Retourne le temps de fonctionnement"""
        # Implémentation simple - peut être améliorée
        return "Active"
    
    async def start_listening(self) -> None:
        """Démarre le serveur web"""
        if self.server_thread and self.server_thread.is_alive():
            self.logger.warning("Serveur web déjà en cours d'exécution")
            return
        
        try:
            self.logger.info(f"Démarrage du serveur web sur {self.host}:{self.port}")
            
            # Démarrer le serveur dans un thread séparé
            self.server_thread = Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            
            # Attendre un peu pour que le serveur démarre
            await asyncio.sleep(1)
            
            await self.emit_event(GLaDOSEvent('web_server_started', source=self.name))
            self.logger.info(f"Interface web disponible sur http://{self.host}:{self.port}")
            
        except Exception as e:
            self.logger.error(f"Erreur démarrage serveur web: {e}")
    
    def _run_server(self):
        """Exécute le serveur Uvicorn"""
        try:
            uvicorn.run(
                self.app,
                host=self.host,
                port=self.port,
                log_level="warning",  # Réduire les logs
                access_log=False
            )
        except Exception as e:
            self.logger.error(f"Erreur serveur Uvicorn: {e}")
    
    async def stop_listening(self) -> None:
        """Arrête le serveur web"""
        try:
            # Fermer toutes les connexions WebSocket
            for websocket in list(self.websocket_connections):
                try:
                    await websocket.close()
                except:
                    pass
            self.websocket_connections.clear()
            
            await self.emit_event(GLaDOSEvent('web_server_stopped', source=self.name))
            self.logger.info("Serveur web arrêté")
            
        except Exception as e:
            self.logger.error(f"Erreur arrêt serveur web: {e}")
    
    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        await self.stop_listening()
        self.logger.info("Module Web nettoyé")
    
    # Méthode pour recevoir les réponses de GLaDOS et les diffuser
    async def send_response_to_web(self, response: str):
        """Envoie une réponse GLaDOS vers l'interface web"""
        if self.websocket_connections:
            message = {
                "type": "response",
                "message": response,
                "timestamp": datetime.now().isoformat()
            }
            await self.broadcast_to_websockets(message)