"""
Configuration pytest et fixtures communes
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path

# Configuration pour les tests asynchrones
@pytest.fixture(scope="session")
def event_loop():
    """Crée un event loop pour toute la session de test"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Crée un répertoire temporaire pour les tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_env_vars():
    """Mock des variables d'environnement pour les tests"""
    original_env = dict(os.environ)
    
    # Variables de test
    test_env = {
        'OPENAI_API_KEY': 'test_openai_key',
        'PORCUPINE_ACCESS_KEY': 'test_porcupine_key',
        'TAPO_EMAIL': 'test@example.com',
        'TAPO_PASSWORD': 'test_password'
    }
    
    # Appliquer les variables de test
    os.environ.update(test_env)
    
    yield test_env
    
    # Restaurer l'environnement original
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def sample_audio_data():
    """Données audio simulées pour les tests"""
    import numpy as np
    
    # Générer un signal audio simple (sinusoïde)
    sample_rate = 16000
    duration = 1.0  # 1 seconde
    frequency = 440  # La
    
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    audio_data = np.sin(frequency * 2 * np.pi * t).astype(np.float32)
    
    return audio_data, sample_rate