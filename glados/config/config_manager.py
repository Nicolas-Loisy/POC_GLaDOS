"""
Gestionnaire de configuration pour GLaDOS
Utilise le pattern Singleton pour garantir une seule instance
"""

import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
import os
from dotenv import load_dotenv


@dataclass
class InputConfig:
    """Configuration pour les modules d'entrée"""
    enabled: bool = True
    wake_word: Optional[Dict[str, Any]] = None
    web: Optional[Dict[str, Any]] = None
    discord: Optional[Dict[str, Any]] = None
    terminal: Optional[Dict[str, Any]] = None


@dataclass
class OutputConfig:
    """Configuration pour les modules de sortie"""
    enabled: bool = True
    tts_glados: Optional[Dict[str, Any]] = None
    terminal: Optional[Dict[str, Any]] = None


@dataclass
class CoreConfig:
    """Configuration du moteur ReAct"""
    model_name: str = "gpt-3.5-turbo"
    max_iterations: int = 10
    verbose: bool = True
    temperature: float = 0.1
    system_prompt: Optional[str] = None


@dataclass
class GLaDOSConfig:
    """Configuration principale de GLaDOS"""
    core: CoreConfig
    inputs: InputConfig
    outputs: OutputConfig
    tools: Dict[str, Any]


class ConfigManager:
    """
    Gestionnaire de configuration singleton
    Charge et valide les configurations depuis des fichiers YAML/JSON
    """
    
    _instance: Optional['ConfigManager'] = None
    _config: Optional[GLaDOSConfig] = None
    
    def __new__(cls) -> 'ConfigManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            load_dotenv()  # Charge les variables d'environnement
            self._initialized = True
    
    def load_config(self, config_path: str) -> GLaDOSConfig:
        """
        Charge la configuration depuis un fichier YAML ou JSON
        
        Args:
            config_path: Chemin vers le fichier de configuration
            
        Returns:
            Instance GLaDOSConfig validée
        """
        config_file = Path(config_path)
        
        if not config_file.exists():
            raise FileNotFoundError(f"Fichier de configuration non trouvé: {config_path}")
        
        # Chargement selon l'extension
        if config_file.suffix.lower() == '.yaml' or config_file.suffix.lower() == '.yml':
            with open(config_file, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f)
        elif config_file.suffix.lower() == '.json':
            with open(config_file, 'r', encoding='utf-8') as f:
                raw_config = json.load(f)
        else:
            raise ValueError(f"Format de fichier non supporté: {config_file.suffix}")

        # Substituer les variables d'environnement
        raw_config = self._substitute_env_vars(raw_config)

        # Validation et création de l'objet config
        self._config = self._validate_and_create_config(raw_config)
        return self._config

    def _substitute_env_vars(self, data: Any) -> Any:
        """
        Substitue récursivement les variables d'environnement dans la configuration

        Args:
            data: Données de configuration (dict, list, str, etc.)

        Returns:
            Données avec variables substituées
        """
        import re

        if isinstance(data, dict):
            return {key: self._substitute_env_vars(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._substitute_env_vars(item) for item in data]
        elif isinstance(data, str):
            # Pattern pour ${VAR_NAME}
            pattern = r'\$\{([^}]+)\}'

            def replace_var(match):
                var_name = match.group(1)
                return os.getenv(var_name, match.group(0))  # Garder original si variable non trouvée

            return re.sub(pattern, replace_var, data)
        else:
            return data

    def _validate_and_create_config(self, raw_config: Dict[str, Any]) -> GLaDOSConfig:
        """
        Valide et crée l'objet de configuration
        
        Args:
            raw_config: Configuration brute depuis le fichier
            
        Returns:
            Instance GLaDOSConfig validée
        """
        # Configuration du core (obligatoire)
        core_config = raw_config.get('core', {})
        core = CoreConfig(
            model_name=core_config.get('model_name', 'gpt-3.5-turbo'),
            max_iterations=core_config.get('max_iterations', 10),
            verbose=core_config.get('verbose', True),
            temperature=core_config.get('temperature', 0.1),
            system_prompt=core_config.get('system_prompt', None)
        )
        
        # Configuration des inputs
        inputs_config = raw_config.get('inputs', {})
        inputs = InputConfig(
            enabled=inputs_config.get('enabled', True),
            wake_word=inputs_config.get('wake_word'),
            web=inputs_config.get('web'),
            discord=inputs_config.get('discord'),
            terminal=inputs_config.get('terminal')
        )
        
        # Configuration des outputs
        outputs_config = raw_config.get('outputs', {})
        outputs = OutputConfig(
            enabled=outputs_config.get('enabled', True),
            tts_glados=outputs_config.get('tts_glados'),
            terminal=outputs_config.get('terminal')
        )
        
        # Configuration des tools
        tools = raw_config.get('tools', {})
        
        return GLaDOSConfig(
            core=core,
            inputs=inputs,
            outputs=outputs,
            tools=tools
        )
    
    def get_config(self) -> Optional[GLaDOSConfig]:
        """Retourne la configuration actuelle"""
        return self._config
    
    def get_env_var(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Récupère une variable d'environnement"""
        return os.getenv(key, default)
    
    def reload_config(self, config_path: str) -> GLaDOSConfig:
        """Recharge la configuration depuis le fichier"""
        return self.load_config(config_path)


# Instance globale du gestionnaire de configuration
config_manager = ConfigManager()