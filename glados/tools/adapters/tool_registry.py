"""
Registre des outils disponibles pour GLaDOS
Enregistre automatiquement tous les adaptateurs d'outils
"""

from ...core.factories import ToolAdapterFactory
from ..tapo.tapo_adapter import TapoAdapter
from ..ir_osram.ir_osram_adapter import IROsramAdapter
from ..ir_yamaha.ir_yamaha_adapter import IRYamahaAdapter
from ..weather.weather_adapter import WeatherAdapter


def register_all_tools():
    """
    Enregistre tous les adaptateurs d'outils disponibles
    Appelé au démarrage de GLaDOS
    """
    # Enregistrer l'adaptateur Tapo
    ToolAdapterFactory.register('tapo', TapoAdapter)

    # Enregistrer l'adaptateur IR OSRAM
    ToolAdapterFactory.register('ir_osram', IROsramAdapter)

    # Enregistrer l'adaptateur IR Yamaha
    ToolAdapterFactory.register('ir_yamaha', IRYamahaAdapter)

    # Enregistrer l'adaptateur météo
    ToolAdapterFactory.register('weather', WeatherAdapter)
    
    print(f"Outils enregistrés: {ToolAdapterFactory.get_available_types()}")


class ToolRegistry:
    """
    Classe utilitaire pour gérer l'enregistrement des outils
    """
    
    @staticmethod
    def initialize():
        """Initialise le registre des outils"""
        register_all_tools()
    
    @staticmethod
    def get_available_tools():
        """Retourne la liste des outils disponibles"""
        return ToolAdapterFactory.get_available_types()
    
    @staticmethod
    def create_tool(tool_type: str, name: str, config: dict):
        """Crée une instance d'outil"""
        return ToolAdapterFactory.create(tool_type, name, config)