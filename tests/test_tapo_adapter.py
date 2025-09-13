"""
Tests pour l'adaptateur Tapo
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from glados.tools.tapo.tapo_adapter import TapoAdapter


@pytest.fixture
def tapo_config():
    return {
        'email': 'test@example.com',
        'password': 'test_password',
        'devices': {
            'test_lamp': {
                'type': 'L530',
                'ip': '192.168.1.100',
                'name': 'Test Lamp'
            },
            'test_plug': {
                'type': 'P110', 
                'ip': '192.168.1.101',
                'name': 'Test Plug'
            }
        }
    }


@pytest.fixture
def mock_tapo_client():
    """Mock pour le client Tapo"""
    client = AsyncMock()
    device = AsyncMock()
    
    # Mock pour l'info du device
    device_info = MagicMock()
    device_info.device_on = True
    device_info.brightness = 80
    device.get_device_info.return_value = device_info
    
    client.l530.return_value = device
    client.p110.return_value = device
    
    return client, device


def test_tapo_adapter_initialization(tapo_config):
    """Test l'initialisation de l'adaptateur Tapo"""
    adapter = TapoAdapter('tapo_test', tapo_config)
    
    assert adapter.name == 'tapo_test'
    assert adapter.email == 'test@example.com'
    assert adapter.password == 'test_password'
    assert len(adapter.devices) == 2
    assert 'test_lamp' in adapter.devices


def test_tapo_adapter_initialization_without_credentials():
    """Test l'initialisation sans credentials"""
    config = {'devices': {}}
    
    with pytest.raises(ValueError, match="Email et mot de passe Tapo requis"):
        TapoAdapter('tapo_test', config)


@pytest.mark.asyncio
async def test_tapo_adapter_turn_on_device(tapo_config, mock_tapo_client):
    """Test allumer un appareil"""
    adapter = TapoAdapter('tapo_test', tapo_config)
    client_mock, device_mock = mock_tapo_client
    
    with patch('glados.tools.tapo.tapo_adapter.ApiClient', return_value=client_mock):
        result = await adapter.execute(device_name='test_lamp', action='on')
        
        assert result['success'] is True
        assert 'allumé' in result['action']
        device_mock.on.assert_called_once()


@pytest.mark.asyncio
async def test_tapo_adapter_turn_off_device(tapo_config, mock_tapo_client):
    """Test éteindre un appareil"""
    adapter = TapoAdapter('tapo_test', tapo_config)
    client_mock, device_mock = mock_tapo_client
    
    with patch('glados.tools.tapo.tapo_adapter.ApiClient', return_value=client_mock):
        result = await adapter.execute(device_name='test_plug', action='off')
        
        assert result['success'] is True
        assert 'éteint' in result['action']
        device_mock.off.assert_called_once()


@pytest.mark.asyncio
async def test_tapo_adapter_toggle_device(tapo_config, mock_tapo_client):
    """Test basculer un appareil"""
    adapter = TapoAdapter('tapo_test', tapo_config)
    client_mock, device_mock = mock_tapo_client
    
    with patch('glados.tools.tapo.tapo_adapter.ApiClient', return_value=client_mock):
        result = await adapter.execute(device_name='test_lamp', action='toggle')
        
        assert result['success'] is True
        # Le device est allumé (mock), donc il devrait être éteint
        device_mock.off.assert_called_once()


@pytest.mark.asyncio
async def test_tapo_adapter_set_brightness(tapo_config, mock_tapo_client):
    """Test régler la luminosité"""
    adapter = TapoAdapter('tapo_test', tapo_config)
    client_mock, device_mock = mock_tapo_client
    
    with patch('glados.tools.tapo.tapo_adapter.ApiClient', return_value=client_mock):
        result = await adapter.execute(
            device_name='test_lamp', 
            action='set_brightness', 
            brightness=75
        )
        
        assert result['success'] is True
        assert 'luminosité' in result['action']
        device_mock.set_brightness.assert_called_once_with(75)


@pytest.mark.asyncio
async def test_tapo_adapter_invalid_device(tapo_config):
    """Test avec un appareil inexistant"""
    adapter = TapoAdapter('tapo_test', tapo_config)
    
    result = await adapter.execute(device_name='nonexistent', action='on')
    
    assert result['success'] is False
    assert 'non trouvé' in result['error']
    assert 'available_devices' in result


@pytest.mark.asyncio
async def test_tapo_adapter_invalid_brightness(tapo_config, mock_tapo_client):
    """Test avec une luminosité invalide"""
    adapter = TapoAdapter('tapo_test', tapo_config)
    client_mock, device_mock = mock_tapo_client
    
    with patch('glados.tools.tapo.tapo_adapter.ApiClient', return_value=client_mock):
        result = await adapter.execute(
            device_name='test_lamp',
            action='set_brightness',
            brightness=150  # > 100
        )
        
        assert result['success'] is False
        assert 'entre 1 et 100' in result['error']


def test_tapo_adapter_parameters_schema(tapo_config):
    """Test le schéma des paramètres"""
    adapter = TapoAdapter('tapo_test', tapo_config)
    schema = adapter.get_parameters_schema()
    
    assert schema['type'] == 'function'
    assert 'device_name' in schema['function']['parameters']['properties']
    assert 'action' in schema['function']['parameters']['properties']
    
    # Vérifier les devices dans l'enum
    device_enum = schema['function']['parameters']['properties']['device_name']['enum']
    assert 'test_lamp' in device_enum
    assert 'test_plug' in device_enum


@pytest.mark.asyncio
async def test_tapo_adapter_validate_parameters(tapo_config):
    """Test la validation des paramètres"""
    adapter = TapoAdapter('tapo_test', tapo_config)
    
    # Paramètres valides
    assert await adapter.validate_parameters(device_name='test_lamp', action='on') is True
    
    # Device inexistant
    assert await adapter.validate_parameters(device_name='invalid', action='on') is False
    
    # Action invalide
    assert await adapter.validate_parameters(device_name='test_lamp', action='invalid') is False


def test_hex_to_hs_conversion(tapo_config):
    """Test la conversion couleur hex vers hue/saturation"""
    adapter = TapoAdapter('tapo_test', tapo_config)
    
    # Test rouge pur
    hue, saturation = adapter._hex_to_hs('#FF0000')
    assert hue == 0
    assert saturation == 100
    
    # Test vert pur  
    hue, saturation = adapter._hex_to_hs('#00FF00')
    assert hue == 120
    assert saturation == 100
    
    # Test blanc (pas de saturation)
    hue, saturation = adapter._hex_to_hs('#FFFFFF')
    assert saturation == 0


if __name__ == '__main__':
    pytest.main([__file__])