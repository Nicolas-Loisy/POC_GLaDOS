"""
Adaptateur pour les appareils Tapo (TP-Link)
Basé sur les scripts existants dans MarkIO/Scripts/BT_TAPO
"""

import asyncio
from typing import Dict, Any, List, Optional
from tapo import ApiClient
import logging
from pydantic import BaseModel, Field
from enum import Enum

from ...core.interfaces import ToolAdapter
from ...config.config_manager import ConfigManager


class TapoAction(str, Enum):
    """Actions disponibles pour les appareils TAPO"""
    ON = "on"
    OFF = "off"
    SET_BRIGHTNESS = "set_brightness"
    SET_COLOR = "set_color"


class TapoDeviceName(str, Enum):
    """Noms des appareils TAPO disponibles"""
    LAMPE_CHAMBRE = "lampe_chambre"
    PRISE_CHAMBRE = "prise_chambre"


# Dictionnaire des couleurs supportées (noms anglais → RGB)
TAPO_COLORS = {
    # Couleurs de base
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "white": (255, 255, 255),
    "yellow": (255, 255, 0),
    "orange": (255, 165, 0),
    "purple": (128, 0, 128),
    "pink": (255, 192, 203),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    # Couleurs étendues
    "warm_white": (255, 244, 229),
    "cool_white": (237, 245, 255),
    "lime": (50, 205, 50),
    "navy": (0, 0, 128),
    "teal": (0, 128, 128),
    "maroon": (128, 0, 0)
}


class TapoUnifiedParameters(BaseModel):
    """Paramètres unifiés pour tous les appareils TAPO selon bt_tapo_strict_2.py"""
    device_name: TapoDeviceName = Field(
        description="Nom exact de l'appareil TAPO à contrôler"
    )
    action: TapoAction = Field(
        description="Action à effectuer sur l'appareil"
    )
    # Pour set_brightness - utilise 'value' comme dans le script original
    value: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Valeur de luminosité de 0 à 100 (OBLIGATOIRE pour set_brightness)"
    )
    # Pour set_color - utilise r,g,b comme dans le script original
    r: Optional[int] = Field(
        default=None,
        ge=0,
        le=255,
        description="Rouge de 0 à 255 (OBLIGATOIRE pour set_color)"
    )
    g: Optional[int] = Field(
        default=None,
        ge=0,
        le=255,
        description="Vert de 0 à 255 (OBLIGATOIRE pour set_color)"
    )
    b: Optional[int] = Field(
        default=None,
        ge=0,
        le=255,
        description="Bleu de 0 à 255 (OBLIGATOIRE pour set_color)"
    )
    # Paramètre alternatif: couleur par nom (sera converti en RGB)
    color: Optional[str] = Field(
        default=None,
        description=f"Nom de couleur en anglais: {', '.join(TAPO_COLORS.keys())} (alternatif à r,g,b)"
    )

    def model_validate(self):
        """Validation conditionnelle selon l'action"""
        if self.action == TapoAction.SET_BRIGHTNESS:
            if self.value is None:
                raise ValueError("Paramètre 'value' obligatoire pour l'action 'set_brightness'")

        if self.action == TapoAction.SET_COLOR:
            # Soit r,g,b soit color obligatoire
            has_rgb = self.r is not None and self.g is not None and self.b is not None
            has_color = self.color is not None

            if not has_rgb and not has_color:
                raise ValueError("Pour 'set_color': soit r,g,b soit 'color' est obligatoire")

            if has_color and self.color not in TAPO_COLORS:
                available = ", ".join(TAPO_COLORS.keys())
                raise ValueError(f"Couleur '{self.color}' non supportée. Disponibles: {available}")

        return self

# Alias pour compatibilité
TapoParameters = TapoUnifiedParameters


class TapoAdapter(ToolAdapter):
    """
    Adaptateur pour contrôler les appareils Tapo
    Supporte les prises P110 et les ampoules L530
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.logger = logging.getLogger(__name__)
        
        # Configuration Tapo
        self.email = config.get('email') or ConfigManager().get_env_var('TAPO_EMAIL')
        self.password = config.get('password') or ConfigManager().get_env_var('TAPO_PASSWORD')
        self.devices = config.get('devices', {})
        
        # Client API
        self.client = None
        
        if not self.email or not self.password:
            raise ValueError("Email et mot de passe Tapo requis")

        # Construire la description dynamiquement avec la liste des appareils
        self._build_description()

    def get_pydantic_schema(self):
        """Retourne le schéma Pydantic pour les paramètres de l'outil"""
        return TapoUnifiedParameters

    def _build_description(self) -> None:
        """Construit la description avec la liste des appareils disponibles"""
        base_description = "Contrôle les appareils Tapo (prises, ampoules) - allumer, éteindre, changer couleurs"

        if self.devices:
            device_list = []
            for device_id, device_config in self.devices.items():
                device_name = device_config.get('name', device_id)
                device_type = device_config.get('type', 'unknown')
                device_list.append(f"- {device_id}: {device_name} ({device_type})")

            devices_str = "\n".join(device_list)
            self.description = f"{base_description}\n\nAppareils disponibles:\n{devices_str}\n\nUtilise le nom exact de l'appareil (ex: 'lampe_chambre', 'prise_chambre')"
        else:
            self.description = base_description

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Exécute une action sur un appareil Tapo avec validation Pydantic
        """
        try:
            # Validation stricte avec le modèle unifié
            params = TapoUnifiedParameters(**kwargs)
            params.model_validate()  # Validation conditionnelle

            device_name = params.device_name.value
            action = params.action.value

            # Convertir couleur par nom en RGB si nécessaire
            if action == "set_color" and params.color:
                r, g, b = TAPO_COLORS[params.color]
                params.r, params.g, params.b = r, g, b
            
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
                self.logger.info(f"Initialisation client TAPO avec email: {self.email[:3]}***@{self.email.split('@')[1] if '@' in self.email else 'unknown'}")
                self.logger.info(f"Password length: {len(self.password)} chars")
                self.client = ApiClient(self.email, self.password)

            self.logger.info(f"Connexion à {device_name} ({device_type}) sur {device_ip}")

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
            
            # Passer les paramètres validés à _execute_action
            result = await self._execute_action(device, action, device_type, params)
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
    
    async def _execute_action(self, device, action: str, device_type: str, params: TapoUnifiedParameters) -> Dict[str, Any]:
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
                # Utiliser 'value' comme dans bt_tapo_strict_2.py
                brightness_value = params.value
                await device.set_brightness(brightness_value)
                return {"success": True, "action": f"luminosité réglée à {brightness_value}%"}

            elif action == "set_color" and device_type.upper() == 'L530':
                # Utiliser r,g,b comme dans bt_tapo_strict_2.py
                r, g, b = params.r, params.g, params.b

                # Essayer différentes méthodes d'appel selon la version de l'API
                try:
                    # Méthode 1: Paramètres séparés (comme bt_tapo_strict_2.py)
                    await device.set_color(r, g, b)
                except TypeError as e:
                    self.logger.info(f"Méthode 1 échouée: {e}, essai méthode 2")
                    try:
                        # Méthode 2: Tuple RGB
                        await device.set_color((r, g, b))
                    except TypeError as e2:
                        self.logger.info(f"Méthode 2 échouée: {e2}, essai méthode 3")
                        try:
                            # Méthode 3: Dict RGB
                            await device.set_color({"r": r, "g": g, "b": b})
                        except TypeError as e3:
                            self.logger.info(f"Méthode 3 échouée: {e3}, essai avec hue/saturation")
                            # Méthode 4: Conversion RGB vers HSV
                            hue, saturation = self._rgb_to_hue_sat(r, g, b)
                            await device.set_hue_saturation(hue, saturation)

                return {"success": True, "action": f"couleur réglée à RGB({r},{g},{b})"}
            
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