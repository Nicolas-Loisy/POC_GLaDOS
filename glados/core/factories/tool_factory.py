"""
Factory pour créer les adaptateurs d'outils
"""

from typing import Dict, List, Any
from ..interfaces import ToolAdapter


class ToolAdapterFactory:
    """
    Factory pour créer les adaptateurs d'outils
    Pattern: Factory + Registry
    """

    _registry: Dict[str, type] = {}

    @classmethod
    def register(cls, tool_type: str, adapter_class: type) -> None:
        """Enregistre un type d'adaptateur d'outil"""
        cls._registry[tool_type] = adapter_class

    @classmethod
    def create(cls, tool_type: str, name: str, config: Dict[str, Any]) -> ToolAdapter:
        """Crée une instance d'adaptateur d'outil"""
        if tool_type not in cls._registry:
            raise ValueError(f"Type d'adaptateur d'outil inconnu: {tool_type}")

        adapter_class = cls._registry[tool_type]
        return adapter_class(name, config)

    @classmethod
    def get_available_types(cls) -> List[str]:
        """Retourne la liste des types disponibles"""
        return list(cls._registry.keys())

    @classmethod
    def get_registry(cls) -> Dict[str, type]:
        """Retourne le registre complet"""
        return cls._registry.copy()