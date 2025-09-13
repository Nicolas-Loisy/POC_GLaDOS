"""
Tests pour les modules terminal (input et output)
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from glados.inputs.terminal.terminal_input import TerminalInput
from glados.outputs.terminal.terminal_output import TerminalOutput
from glados.core.interfaces import GLaDOSMessage, MessageType


@pytest.fixture
def terminal_input_config():
    return {
        'prompt': 'TEST> ',
        'history_size': 50
    }


@pytest.fixture
def terminal_output_config():
    return {
        'color_scheme': 'green',
        'prefix': '[TEST] ',
        'show_timestamp': False
    }


@pytest.mark.asyncio
async def test_terminal_input_initialization(terminal_input_config):
    """Test l'initialisation du module terminal input"""
    terminal = TerminalInput('test_terminal', terminal_input_config)
    
    assert terminal.name == 'test_terminal'
    assert terminal.prompt == 'TEST> '
    assert terminal.history_size == 50
    
    # Test initialisation
    result = await terminal.initialize()
    assert result is True


@pytest.mark.asyncio  
async def test_terminal_output_initialization(terminal_output_config):
    """Test l'initialisation du module terminal output"""
    terminal = TerminalOutput('test_output', terminal_output_config)
    
    assert terminal.name == 'test_output'
    assert terminal.color_scheme == 'green'
    assert terminal.prefix == '[TEST] '
    
    # Test initialisation
    result = await terminal.initialize()
    assert result is True
    assert terminal.is_active is True


@pytest.mark.asyncio
async def test_terminal_output_send_message(terminal_output_config):
    """Test l'envoi de messages via terminal output"""
    terminal = TerminalOutput('test_output', terminal_output_config)
    await terminal.initialize()
    
    # Créer un message test
    message = GLaDOSMessage(
        content="Test message",
        message_type=MessageType.TEXT,
        source="test"
    )
    
    # Mock print pour capturer la sortie
    with patch('builtins.print') as mock_print:
        result = await terminal.send_message(message)
        
        assert result is True
        mock_print.assert_called_once()
        # Vérifier que le message contient le texte
        call_args = mock_print.call_args[0][0]
        assert "Test message" in call_args


@pytest.mark.asyncio
async def test_terminal_input_message_processing(terminal_input_config):
    """Test le traitement des messages d'entrée"""
    terminal = TerminalInput('test_terminal', terminal_input_config)
    await terminal.initialize()
    
    # Mock pour capturer les messages émis
    messages_received = []
    
    async def message_handler(message):
        messages_received.append(message)
    
    terminal.subscribe_to_messages(message_handler)
    
    # Simuler le traitement d'une entrée
    await terminal._process_input("test command")
    
    # Vérifier qu'un message a été émis
    assert len(messages_received) == 1
    message = messages_received[0]
    assert message.content == "test command"
    assert message.message_type == MessageType.TEXT
    assert message.source == "test_terminal"


def test_terminal_output_message_formatting(terminal_output_config):
    """Test le formatage des messages"""
    terminal = TerminalOutput('test_output', terminal_output_config)
    
    # Test avec différents types de messages
    text_message = GLaDOSMessage("Hello", MessageType.TEXT, "test")
    error_message = GLaDOSMessage("Error occurred", MessageType.ERROR, "test")
    
    text_formatted = terminal._format_message(text_message)
    error_formatted = terminal._format_message(error_message)
    
    assert "[TEST]" in text_formatted
    assert "Hello" in text_formatted
    assert "Erreur:" in error_formatted
    assert "Error occurred" in error_formatted


def test_terminal_input_history_management(terminal_input_config):
    """Test la gestion de l'historique des commandes"""
    terminal = TerminalInput('test_terminal', terminal_input_config)
    
    # Ajouter des commandes à l'historique
    terminal._add_to_history("command1")
    terminal._add_to_history("command2")
    terminal._add_to_history("command3")
    
    assert len(terminal.history) == 3
    assert terminal.history[-1] == "command3"
    
    # Test que les commandes système ne sont pas ajoutées
    terminal._add_to_history("history")
    terminal._add_to_history("help")
    
    assert len(terminal.history) == 3  # Pas d'ajout


@pytest.mark.asyncio
async def test_terminal_modules_cleanup(terminal_input_config, terminal_output_config):
    """Test le nettoyage des modules"""
    input_module = TerminalInput('test_input', terminal_input_config)
    output_module = TerminalOutput('test_output', terminal_output_config)
    
    await input_module.initialize()
    await output_module.initialize()
    
    # Test cleanup
    await input_module.cleanup()
    await output_module.cleanup()
    
    assert output_module.is_active is False


if __name__ == '__main__':
    pytest.main([__file__])