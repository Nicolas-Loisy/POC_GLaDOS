"""
Factory pour créer les modèles de langage (LLM)
"""

from typing import Dict, Any
from llama_index.core.llms.llm import LLM
import logging


class LLMFactory:
    """
    Factory pour créer les modèles de langage
    Pattern: Factory + Registry
    """

    _registry: Dict[str, type] = {}

    @classmethod
    def register(cls, llm_type: str, llm_class: type) -> None:
        """Enregistre un type de LLM"""
        cls._registry[llm_type] = llm_class

    @classmethod
    def create(cls, llm_config: Dict[str, Any]) -> LLM:
        """
        Crée une instance de LLM depuis la configuration

        Args:
            llm_config: Configuration du LLM

        Returns:
            Instance du LLM configuré
        """
        llm_type = llm_config.get('type', 'openai')

        if llm_type not in cls._registry:
            raise ValueError(f"Type de LLM inconnu: {llm_type}")

        llm_class = cls._registry[llm_type]

        # Extraire les paramètres de configuration pour ce LLM
        llm_params = llm_config.get('params', {})

        # Créer l'instance du LLM
        return llm_class(**llm_params)

    @classmethod
    def get_available_types(cls) -> list:
        """Retourne la liste des types de LLM disponibles"""
        return list(cls._registry.keys())

    @classmethod
    def get_registry(cls) -> Dict[str, type]:
        """Retourne le registre complet"""
        return cls._registry.copy()


def register_llm_providers():
    """Enregistre tous les providers de LLM disponibles"""
    logger = logging.getLogger(__name__)

    # OpenAI
    try:
        from llama_index.llms.openai import OpenAI
        LLMFactory.register('openai', OpenAI)
        logger.debug("Provider OpenAI enregistré")
    except ImportError:
        logger.warning("Provider OpenAI non disponible (llama-index-llms-openai non installé)")

    # Anthropic Claude
    try:
        from llama_index.llms.anthropic import Anthropic
        LLMFactory.register('anthropic', Anthropic)
        logger.debug("Provider Anthropic enregistré")
    except ImportError:
        logger.warning("Provider Anthropic non disponible (llama-index-llms-anthropic non installé)")

    # Ollama
    try:
        from llama_index.llms.ollama import Ollama
        LLMFactory.register('ollama', Ollama)
        logger.debug("Provider Ollama enregistré")
    except ImportError:
        logger.warning("Provider Ollama non disponible (llama-index-llms-ollama non installé)")

    # HuggingFace
    try:
        from llama_index.llms.huggingface import HuggingFaceLLM
        LLMFactory.register('huggingface', HuggingFaceLLM)
        logger.debug("Provider HuggingFace enregistré")
    except ImportError:
        logger.warning("Provider HuggingFace non disponible (llama-index-llms-huggingface non installé)")

    # Azure OpenAI
    try:
        from llama_index.llms.azure_openai import AzureOpenAI
        LLMFactory.register('azure_openai', AzureOpenAI)
        logger.debug("Provider Azure OpenAI enregistré")
    except ImportError:
        logger.warning("Provider Azure OpenAI non disponible (llama-index-llms-azure-openai non installé)")

    logger.info(f"Providers LLM enregistrés: {LLMFactory.get_available_types()}")


# Auto-enregistrement lors de l'import
register_llm_providers()