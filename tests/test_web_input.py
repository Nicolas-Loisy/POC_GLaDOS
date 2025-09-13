"""
Tests pour le module d'entrée Web
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from glados.inputs.web.web_input import WebInput, MessageRequest
from glados.core.interfaces import GLaDOSMessage, MessageType


@pytest.fixture
def web_config():
    return {
        'host': '127.0.0.1',
        'port': 8081,  # Port différent pour les tests
        'title': 'GLaDOS Test Interface',
        'enable_cors': True
    }


@pytest.fixture
def web_input(web_config):
    return WebInput('test_web', web_config)


def test_web_input_initialization(web_config):
    """Test l'initialisation du module web input"""
    web_input = WebInput('test_web', web_config)
    
    assert web_input.name == 'test_web'
    assert web_input.host == '127.0.0.1'
    assert web_input.port == 8081
    assert web_input.title == 'GLaDOS Test Interface'
    assert web_input.enable_cors is True


@pytest.mark.asyncio
async def test_web_input_initialize(web_input):
    """Test l'initialisation du serveur web"""
    result = await web_input.initialize()
    assert result is True


def test_fastapi_routes_setup(web_input):
    """Test que les routes FastAPI sont correctement configurées"""
    # Les routes sont configurées lors de l'initialisation
    asyncio.run(web_input.initialize())
    
    # Tester avec TestClient
    client = TestClient(web_input.app)
    
    # Test route principale
    response = client.get("/")
    assert response.status_code == 200
    assert "GLaDOS Assistant Web" in response.text
    
    # Test route status
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "connections" in data


def test_api_message_endpoint(web_input):
    """Test l'endpoint API pour envoyer des messages"""
    asyncio.run(web_input.initialize())
    
    # Mock pour capturer les messages émis
    messages_received = []
    
    async def message_handler(message):
        messages_received.append(message)
    
    web_input.subscribe_to_messages(message_handler)
    
    # Tester avec TestClient
    client = TestClient(web_input.app)
    
    response = client.post("/api/message", json={
        "message": "Test message",
        "type": "text"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "Message envoyé" in data["message"]


def test_message_request_model():
    """Test le modèle Pydantic MessageRequest"""
    # Message valide
    request = MessageRequest(message="Test message")
    assert request.message == "Test message"
    assert request.type == "text"
    
    # Message avec type personnalisé
    request = MessageRequest(message="Test", type="command")
    assert request.type == "command"


@pytest.mark.asyncio
async def test_websocket_connections(web_input):
    """Test la gestion des connexions WebSocket"""
    await web_input.initialize()
    
    # Simuler une connexion WebSocket
    mock_websocket = AsyncMock()
    mock_websocket.accept = AsyncMock()
    mock_websocket.send_json = AsyncMock()
    mock_websocket.receive_json = AsyncMock(side_effect=[
        {"type": "message", "content": "Test message"},
        # Simuler une déconnexion après le premier message
        Exception("Connection closed")
    ])
    
    # Mock pour capturer les messages
    messages_received = []
    
    async def message_handler(message):
        messages_received.append(message)
    
    web_input.subscribe_to_messages(message_handler)
    
    # Tester la gestion WebSocket
    try:
        await web_input._handle_websocket(mock_websocket)
    except:
        pass  # La déconnexion est attendue
    
    # Vérifier que la connexion a été acceptée
    mock_websocket.accept.assert_called_once()
    
    # Vérifier qu'au moins un message de bienvenue a été envoyé
    assert mock_websocket.send_json.called


@pytest.mark.asyncio
async def test_broadcast_to_websockets(web_input):
    """Test la diffusion vers les connexions WebSocket"""
    await web_input.initialize()
    
    # Créer des mocks de connexions WebSocket
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    ws_failed = AsyncMock()
    ws_failed.send_json.side_effect = Exception("Connection failed")
    
    # Ajouter les connexions
    web_input.websocket_connections.add(ws1)
    web_input.websocket_connections.add(ws2)
    web_input.websocket_connections.add(ws_failed)
    
    message = {"type": "test", "content": "broadcast message"}
    
    # Tester la diffusion
    await web_input.broadcast_to_websockets(message)
    
    # Vérifier que les messages ont été envoyés aux connexions valides
    ws1.send_json.assert_called_once_with(message)
    ws2.send_json.assert_called_once_with(message)
    
    # Vérifier que la connexion défaillante a été supprimée
    assert ws_failed not in web_input.websocket_connections


def test_html_interface_generation(web_input):
    """Test la génération de l'interface HTML"""
    html = web_input._get_html_interface()
    
    # Vérifier que l'HTML contient les éléments essentiels
    assert "<!DOCTYPE html>" in html
    assert "GLaDOS Assistant Web" in html
    assert "chat-messages" in html
    assert "messageInput" in html
    assert "WebSocket" in html  # JavaScript WebSocket
    assert "sendMessage" in html  # Fonction JavaScript


@pytest.mark.asyncio
async def test_web_input_cleanup(web_input):
    """Test le nettoyage du module web"""
    await web_input.initialize()
    
    # Ajouter une connexion WebSocket mock
    mock_ws = AsyncMock()
    web_input.websocket_connections.add(mock_ws)
    
    # Test cleanup
    await web_input.cleanup()
    
    # Vérifier que les connexions WebSocket ont été fermées
    mock_ws.close.assert_called_once()


def test_message_processing(web_input):
    """Test le traitement des messages WebSocket"""
    asyncio.run(web_input.initialize())
    
    # Mock WebSocket
    mock_websocket = AsyncMock()
    
    # Messages de test
    test_data = {
        "type": "message",
        "content": "Test command"
    }
    
    # Mock pour capturer les messages émis
    messages_received = []
    
    async def message_handler(message):
        messages_received.append(message)
    
    web_input.subscribe_to_messages(message_handler)
    
    # Tester le traitement du message
    asyncio.run(web_input._process_websocket_message(test_data, mock_websocket, "test_client"))
    
    # Vérifier qu'une confirmation a été envoyée
    mock_websocket.send_json.assert_called()


if __name__ == '__main__':
    pytest.main([__file__])