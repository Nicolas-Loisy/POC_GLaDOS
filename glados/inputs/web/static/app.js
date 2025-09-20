// Variables globales
let ws = null;
let isConnected = false;

// Éléments DOM
const messageInput = document.getElementById('messageInput');
const chatMessages = document.getElementById('chatMessages');
const statusDot = document.getElementById('statusDot');
const connectionStatus = document.getElementById('connectionStatus');
const systemInfo = document.getElementById('systemInfo');
const initTime = document.getElementById('initTime');

// Initialisation
document.addEventListener('DOMContentLoaded', function() {
    initTime.textContent = new Date().toLocaleTimeString();
    initWebSocket();
    loadSystemInfo();

    // Événement pour la touche Entrée
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    // Actualiser les infos système toutes les 10 secondes
    setInterval(loadSystemInfo, 10000);

    // Ping périodique pour maintenir la connexion
    setInterval(() => {
        if (isConnected && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
        }
    }, 30000);
});

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

// Tester la connexion
async function testConnection() {
    try {
        addSystemMessage('Test de connexion en cours...');
        const response = await fetch('/api/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (response.ok) {
            const data = await response.json();
            addSystemMessage(`✅ Test réussi: ${data.message}`);
        } else {
            addSystemMessage(`❌ Test échoué: ${response.status}`);
        }
    } catch (error) {
        console.error('Erreur test:', error);
        addSystemMessage(`❌ Erreur test: ${error.message}`);
    }
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