"""
Interfaces pour les modules Input/Output de GLaDOS
Pattern: Strategy + Observer pour une architecture modulaire
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import asyncio


class MessageType(Enum):
    """Types de messages dans le système"""
    TEXT = "text"
    VOICE = "voice" 
    COMMAND = "command"
    ERROR = "error"
    STATUS = "status"


@dataclass
class GLaDOSMessage:
    """Structure standardisée des messages dans GLaDOS"""
    content: str
    message_type: MessageType
    source: str  # Nom du module source
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None


class GLaDOSEvent:
    """Événement dans le système GLaDOS"""
    
    def __init__(self, event_type: str, data: Any = None, source: str = None):
        self.event_type = event_type
        self.data = data
        self.source = source
        self.timestamp = asyncio.get_event_loop().time()


# =====================================
# INTERFACES PRINCIPALES
# =====================================

class InputModule(ABC):
    """
    Interface abstraite pour tous les modules d'entrée
    Pattern: Strategy + Observer
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.is_active = False
        self._message_handlers: List[Callable[[GLaDOSMessage], None]] = []
        self._event_handlers: List[Callable[[GLaDOSEvent], None]] = []
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialise le module d'entrée
        Returns: True si l'initialisation réussit
        """
        pass
    
    @abstractmethod
    async def start_listening(self) -> None:
        """Démarre l'écoute des entrées"""
        pass
    
    @abstractmethod
    async def stop_listening(self) -> None:
        """Arrête l'écoute des entrées"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Nettoie les ressources du module"""
        pass
    
    def subscribe_to_messages(self, handler: Callable[[GLaDOSMessage], None]) -> None:
        """S'abonne aux messages de ce module"""
        self._message_handlers.append(handler)
    
    def subscribe_to_events(self, handler: Callable[[GLaDOSEvent], None]) -> None:
        """S'abonne aux événements de ce module"""
        self._event_handlers.append(handler)
    
    async def emit_message(self, message: GLaDOSMessage) -> None:
        """Émet un message vers les abonnés"""
        for handler in self._message_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                print(f"Erreur dans le handler de message: {e}")
    
    async def emit_event(self, event: GLaDOSEvent) -> None:
        """Émet un événement vers les abonnés"""
        for handler in self._event_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                print(f"Erreur dans le handler d'événement: {e}")


class OutputModule(ABC):
    """
    Interface abstraite pour tous les modules de sortie
    Pattern: Strategy
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.is_active = False
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialise le module de sortie
        Returns: True si l'initialisation réussit
        """
        pass
    
    @abstractmethod
    async def send_message(self, message: GLaDOSMessage) -> bool:
        """
        Envoie un message via ce module de sortie
        Args:
            message: Message à envoyer
        Returns: True si l'envoi réussit
        """
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Nettoie les ressources du module"""
        pass
    
    def can_handle_message_type(self, message_type: MessageType) -> bool:
        """Vérifie si ce module peut traiter ce type de message"""
        return True  # Par défaut, accepte tous les types


class ToolAdapter(ABC):
    """
    Interface pour les adaptateurs d'outils/actions
    Pattern: Adapter + Command
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.description = ""
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Exécute l'action de l'outil
        Args:
            **kwargs: Paramètres pour l'exécution
        Returns: Résultat de l'exécution
        """
        pass
    
    @abstractmethod
    def get_parameters_schema(self) -> Dict[str, Any]:
        """
        Retourne le schéma des paramètres attendus
        Format OpenAI function calling
        """
        pass
    
    async def validate_parameters(self, **kwargs) -> bool:
        """Valide les paramètres avant exécution"""
        return True


# =====================================
# FACTORY PATTERNS
# =====================================

class InputModuleFactory:
    """
    Factory pour créer les modules d'entrée
    Pattern: Factory
    """
    
    _registry: Dict[str, type] = {}
    
    @classmethod
    def register(cls, module_type: str, module_class: type) -> None:
        """Enregistre un type de module d'entrée"""
        cls._registry[module_type] = module_class
    
    @classmethod
    def create(cls, module_type: str, name: str, config: Dict[str, Any]) -> InputModule:
        """Crée une instance de module d'entrée"""
        if module_type not in cls._registry:
            raise ValueError(f"Type de module d'entrée inconnu: {module_type}")
        
        module_class = cls._registry[module_type]
        return module_class(name, config)
    
    @classmethod
    def get_available_types(cls) -> List[str]:
        """Retourne la liste des types disponibles"""
        return list(cls._registry.keys())


class OutputModuleFactory:
    """
    Factory pour créer les modules de sortie
    Pattern: Factory
    """
    
    _registry: Dict[str, type] = {}
    
    @classmethod
    def register(cls, module_type: str, module_class: type) -> None:
        """Enregistre un type de module de sortie"""
        cls._registry[module_type] = module_class
    
    @classmethod
    def create(cls, module_type: str, name: str, config: Dict[str, Any]) -> OutputModule:
        """Crée une instance de module de sortie"""
        if module_type not in cls._registry:
            raise ValueError(f"Type de module de sortie inconnu: {module_type}")
        
        module_class = cls._registry[module_type]
        return module_class(name, config)
    
    @classmethod
    def get_available_types(cls) -> List[str]:
        """Retourne la liste des types disponibles"""
        return list(cls._registry.keys())


class ToolAdapterFactory:
    """
    Factory pour créer les adaptateurs d'outils
    Pattern: Factory
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