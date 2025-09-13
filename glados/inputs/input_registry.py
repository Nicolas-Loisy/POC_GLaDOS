"""
Registre des modules d'entrée pour GLaDOS
"""

from ..core.interfaces import InputModuleFactory
from .wake_word.wake_word_input import WakeWordInput
from .terminal.terminal_input import TerminalInput
from .web.web_input import WebInput


def register_input_modules():
    """Enregistre tous les modules d'entrée disponibles"""
    InputModuleFactory.register('wake_word', WakeWordInput)
    InputModuleFactory.register('terminal', TerminalInput)
    InputModuleFactory.register('web', WebInput)
    # TODO: Ajouter Discord input
    # InputModuleFactory.register('discord', DiscordInput)
    
    print(f"Modules d'entrée enregistrés: {InputModuleFactory.get_available_types()}")


# Auto-enregistrement lors de l'import
register_input_modules()