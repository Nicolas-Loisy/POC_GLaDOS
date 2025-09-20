"""
Factory pour créer les modules de sortie
"""

from typing import Dict, List, Any, Tuple
from ..interfaces import OutputModule
import logging


class OutputModuleFactory:
    """
    Factory pour créer les modules de sortie
    Pattern: Factory + Registry
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

    @classmethod
    def get_registry(cls) -> Dict[str, type]:
        """Retourne le registre complet"""
        return cls._registry.copy()

    @classmethod
    async def create_modules_from_config(cls, outputs_config, logger: logging.Logger = None) -> Dict[str, OutputModule]:
        """
        Crée automatiquement tous les modules de sortie depuis la configuration

        Args:
            outputs_config: Configuration des modules de sortie
            logger: Logger optionnel

        Returns:
            Dictionnaire des modules créés et initialisés
        """
        modules = {}

        if logger is None:
            logger = logging.getLogger(__name__)

        # Parcourir tous les attributs de configuration de sortie
        for attr_name in dir(outputs_config):
            # Ignorer les attributs privés et les méthodes
            # 'enabled' est la configuration globale d'activation des sorties et non un module
            if attr_name.startswith('_') or attr_name == 'enabled':
                continue

            module_config = getattr(outputs_config, attr_name, None)

            # Vérifier si c'est une configuration valide et activée
            if isinstance(module_config, dict) and module_config.get('enabled', False):
                # Récupérer le type de module depuis la configuration ou utiliser le nom de l'attribut
                module_type = module_config.get('type', attr_name)

                try:
                    module = cls.create(module_type, attr_name, module_config)
                    await module.initialize()
                    modules[attr_name] = module
                    logger.info(f"Module de sortie '{attr_name}' ({module_type}) initialisé")
                except Exception as e:
                    logger.error(f"Erreur initialisation module '{attr_name}' ({module_type}): {e}")
            else:
                if module_config is not None:
                    logger.debug(f"Module de sortie '{attr_name}' désactivé ou non configuré")

        return modules