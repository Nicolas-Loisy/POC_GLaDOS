"""
Registre des outils disponibles pour GLaDOS
Enregistre automatiquement tous les adaptateurs d'outils
"""

from ...core.factories import ToolAdapterFactory
from ..tapo.tapo_adapter import TapoAdapter


def register_all_tools():
    """
    Enregistre tous les adaptateurs d'outils disponibles
    Appelé au démarrage de GLaDOS
    """
    # Enregistrer l'adaptateur Tapo
    ToolAdapterFactory.register('tapo', TapoAdapter)
    
    # TODO: Ajouter d'autres adaptateurs ici
    # ToolAdapterFactory.register('ir_yamaha', YamahaIRAdapter)
    # ToolAdapterFactory.register('ir_osram', OsramIRAdapter)
    
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