"""
Adaptateur pour les appareils Tapo (TP-Link)
Basé sur les scripts existants dans MarkIO/Scripts/BT_TAPO
"""

import asyncio
from typing import Dict, Any, List, Optional
from tapo import ApiClient
import logging

from ...core.interfaces import ToolAdapter
from ...config.config_manager import ConfigManager


class TapoAdapter(ToolAdapter):
    """
    Adaptateur pour contrôler les appareils Tapo
    Supporte les prises P110 et les ampoules L530
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.description = "Contrôle les appareils Tapo (prises, ampoules) - allumer, éteindre, changer couleurs"
        self.logger = logging.getLogger(__name__)
        
        # Configuration Tapo
        self.email = config.get('email') or ConfigManager().get_env_var('TAPO_EMAIL')
        self.password = config.get('password') or ConfigManager().get_env_var('TAPO_PASSWORD')
        self.devices = config.get('devices', {})
        
        # Client API
        self.client = None
        
        if not self.email or not self.password:
            raise ValueError("Email et mot de passe Tapo requis")
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Exécute une action sur un appareil Tapo
        
        Paramètres supportés:
        - device_name: nom de l'appareil (ex: "lampe_chambre")
        - action: "on", "off", "toggle", "set_brightness", "set_color"
        - brightness: 1-100 (optionnel)
        - color: nom de couleur ou hex (optionnel)
        - hue: 0-360 (optionnel)
        - saturation: 0-100 (optionnel)
        """
        try:
            device_name = kwargs.get('device_name')
            action = kwargs.get('action', 'toggle').lower()
            
            if not device_name:
                return {
                    "success": False, 
                    "error": "Nom de l'appareil requis",
                    "available_devices": list(self.devices.keys())
                }
            
            if device_name not in self.devices:
                return {
                    "success": False,
                    "error": f"Appareil '{device_name}' non trouvé",
                    "available_devices": list(self.devices.keys())
                }
            
            device_config = self.devices[device_name]
            device_ip = device_config['ip']
            device_type = device_config['type']
            device_display_name = device_config.get('name', device_name)
            
            # Initialiser le client si nécessaire
            if not self.client:
                self.client = ApiClient(self.email, self.password)
            
            # Connecter à l'appareil selon le type
            if device_type.upper() == 'P110':
                device = await self.client.p110(device_ip)
            elif device_type.upper() == 'L530':
                device = await self.client.l530(device_ip)
            else:
                return {
                    "success": False,
                    "error": f"Type d'appareil non supporté: {device_type}"
                }
            
            # Exécuter l'action
            result = await self._execute_action(device, action, device_type, **kwargs)
            result["device_name"] = device_display_name
            result["device_type"] = device_type
            
            self.logger.info(f"Action Tapo: {action} sur {device_display_name} - Succès: {result.get('success', False)}")
            return result
            
        except Exception as e:
            self.logger.error(f"Erreur Tapo: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_action(self, device, action: str, device_type: str, **kwargs) -> Dict[str, Any]:
        """Exécute l'action spécifique sur l'appareil"""
        
        try:
            if action == "on":
                await device.on()
                return {"success": True, "action": "allumé"}
            
            elif action == "off":
                await device.off()
                return {"success": True, "action": "éteint"}
            
            elif action == "toggle":
                # Obtenir l'état actuel et basculer
                info = await device.get_device_info()
                is_on = info.device_on if hasattr(info, 'device_on') else False
                
                if is_on:
                    await device.off()
                    return {"success": True, "action": "éteint (basculé)"}
                else:
                    await device.on()
                    return {"success": True, "action": "allumé (basculé)"}
            
            elif action == "set_brightness" and device_type.upper() == 'L530':
                brightness = kwargs.get('brightness', 50)
                if not (1 <= brightness <= 100):
                    return {"success": False, "error": "Luminosité doit être entre 1 et 100"}
                
                await device.set_brightness(brightness)
                return {"success": True, "action": f"luminosité réglée à {brightness}%"}
            
            elif action == "set_color" and device_type.upper() == 'L530':
                return await self._set_color(device, **kwargs)
            
            elif action == "get_info":
                info = await device.get_device_info()
                return {
                    "success": True,
                    "info": {
                        "device_on": getattr(info, 'device_on', None),
                        "brightness": getattr(info, 'brightness', None),
                        "color_temp": getattr(info, 'color_temp', None),
                        "hue": getattr(info, 'hue', None),
                        "saturation": getattr(info, 'saturation', None)
                    }
                }
            
            else:
                return {
                    "success": False,
                    "error": f"Action non supportée: {action}",
                    "supported_actions": ["on", "off", "toggle", "set_brightness", "set_color", "get_info"]
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _set_color(self, device, **kwargs) -> Dict[str, Any]:
        """Configure la couleur d'une ampoule L530"""
        
        # Couleurs prédéfinies
        predefined_colors = {
            "rouge": (0, 100),
            "vert": (120, 100),
            "bleu": (240, 100),
            "jaune": (60, 100),
            "violet": (270, 100),
            "orange": (30, 100),
            "rose": (300, 100),
            "cyan": (180, 100),
            "blanc": (0, 0)
        }
        
        try:
            color = kwargs.get('color', '').lower()
            hue = kwargs.get('hue')
            saturation = kwargs.get('saturation')
            
            # Couleur prédéfinie
            if color and color in predefined_colors:
                hue, saturation = predefined_colors[color]
            
            # Couleur hex (ex: #FF0000)
            elif color and color.startswith('#'):
                hue, saturation = self._hex_to_hs(color)
            
            # Paramètres manuels
            elif hue is not None:
                hue = max(0, min(360, hue))
                saturation = max(0, min(100, saturation or 100))
            
            else:
                return {
                    "success": False,
                    "error": "Couleur, hue/saturation ou couleur hex requis",
                    "available_colors": list(predefined_colors.keys())
                }
            
            await device.set_hue_saturation(hue, saturation)
            color_name = color if color in predefined_colors else f"hue:{hue}, sat:{saturation}"
            
            return {"success": True, "action": f"couleur changée à {color_name}"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _hex_to_hs(self, hex_color: str) -> tuple:
        """Convertit une couleur hex en hue/saturation"""
        # Implémentation basique de conversion hex vers HSV
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        
        max_val = max(r, g, b)
        min_val = min(r, g, b)
        diff = max_val - min_val
        
        if diff == 0:
            hue = 0
        elif max_val == r:
            hue = (60 * ((g - b) / diff) + 360) % 360
        elif max_val == g:
            hue = (60 * ((b - r) / diff) + 120) % 360
        else:
            hue = (60 * ((r - g) / diff) + 240) % 360
        
        saturation = 0 if max_val == 0 else (diff / max_val) * 100
        
        return int(hue), int(saturation)
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Schéma des paramètres pour OpenAI function calling"""
        return {
            "type": "function",
            "function": {
                "name": "control_tapo_device",
                "description": "Contrôle les appareils Tapo (prises et ampoules intelligentes)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_name": {
                            "type": "string",
                            "description": "Nom de l'appareil Tapo",
                            "enum": list(self.devices.keys())
                        },
                        "action": {
                            "type": "string",
                            "description": "Action à effectuer",
                            "enum": ["on", "off", "toggle", "set_brightness", "set_color", "get_info"]
                        },
                        "brightness": {
                            "type": "integer",
                            "description": "Luminosité (1-100) pour les ampoules",
                            "minimum": 1,
                            "maximum": 100
                        },
                        "color": {
                            "type": "string",
                            "description": "Couleur (rouge, vert, bleu, jaune, etc.) ou hex (#FF0000)"
                        },
                        "hue": {
                            "type": "integer",
                            "description": "Teinte (0-360)",
                            "minimum": 0,
                            "maximum": 360
                        },
                        "saturation": {
                            "type": "integer", 
                            "description": "Saturation (0-100)",
                            "minimum": 0,
                            "maximum": 100
                        }
                    },
                    "required": ["device_name", "action"]
                }
            }
        }
    
    async def validate_parameters(self, **kwargs) -> bool:
        """Valide les paramètres avant exécution"""
        device_name = kwargs.get('device_name')
        action = kwargs.get('action', '').lower()
        
        if not device_name or device_name not in self.devices:
            return False
        
        valid_actions = ["on", "off", "toggle", "set_brightness", "set_color", "get_info"]
        if action not in valid_actions:
            return False
        
        # Validation spécifique pour set_brightness
        if action == "set_brightness":
            brightness = kwargs.get('brightness')
            if brightness is not None and not (1 <= brightness <= 100):
                return False
        
        return True