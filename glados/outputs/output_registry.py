"""
Registre des modules de sortie pour GLaDOS
"""

from ..core.factories import OutputModuleFactory
from .tts.glados_tts import GLaDOSTTSOutput
from .terminal.terminal_output import TerminalOutput


def register_output_modules():
    """Enregistre tous les modules de sortie disponibles"""
    OutputModuleFactory.register('tts_glados', GLaDOSTTSOutput)
    OutputModuleFactory.register('terminal', TerminalOutput)
    # TODO: Ajouter Discord output
    # OutputModuleFactory.register('discord', DiscordOutput)

    print(f"Modules de sortie enregistrés: {OutputModuleFactory.get_available_types()}")


# Auto-enregistrement lors de l'import
register_output_modules()