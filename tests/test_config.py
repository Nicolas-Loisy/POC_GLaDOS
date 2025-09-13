"""
Tests pour le système de configuration
"""

import pytest
import tempfile
import yaml
from pathlib import Path

from glados.config.config_manager import ConfigManager, GLaDOSConfig


@pytest.fixture
def temp_config_file():
    """Crée un fichier de configuration temporaire pour les tests"""
    config_data = {
        'core': {
            'model_name': 'gpt-3.5-turbo',
            'temperature': 0.1,
            'max_iterations': 10
        },
        'inputs': {
            'enabled': True,
            'terminal': {'enabled': True, 'prompt': 'TEST> '}
        },
        'outputs': {
            'enabled': True,
            'terminal_output': {'enabled': True}
        },
        'tools': {
            'test_tool': {'enabled': True, 'param': 'value'}
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        temp_file = Path(f.name)
    
    yield temp_file
    
    # Cleanup
    if temp_file.exists():
        temp_file.unlink()


def test_config_manager_singleton():
    """Test que ConfigManager est un singleton"""
    manager1 = ConfigManager()
    manager2 = ConfigManager()
    assert manager1 is manager2


def test_load_valid_config(temp_config_file):
    """Test le chargement d'une configuration valide"""
    manager = ConfigManager()
    config = manager.load_config(str(temp_config_file))
    
    assert isinstance(config, GLaDOSConfig)
    assert config.core.model_name == 'gpt-3.5-turbo'
    assert config.core.temperature == 0.1
    assert config.inputs.enabled is True
    assert config.outputs.enabled is True


def test_load_nonexistent_config():
    """Test le chargement d'un fichier inexistant"""
    manager = ConfigManager()
    
    with pytest.raises(FileNotFoundError):
        manager.load_config('nonexistent.yaml')


def test_get_config():
    """Test la récupération de la configuration courante"""
    manager = ConfigManager()
    
    # Avant chargement
    assert manager.get_config() is None
    
    # Après chargement (utilise le fixture)
    # Note: Ce test nécessite un fichier de config chargé


def test_config_validation():
    """Test la validation des configurations"""
    manager = ConfigManager()
    
    # Configuration minimale valide
    raw_config = {
        'core': {'model_name': 'test-model'},
        'inputs': {},
        'outputs': {},
        'tools': {}
    }
    
    config = manager._validate_and_create_config(raw_config)
    assert config.core.model_name == 'test-model'
    assert config.core.temperature == 0.1  # valeur par défaut


if __name__ == '__main__':
    pytest.main([__file__])