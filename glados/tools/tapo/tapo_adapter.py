"""
Adaptateur pour les appareils Tapo (TP-Link)
Basé sur les scripts existants dans MarkIO/Scripts/BT_TAPO
"""

import asyncio
from typing import Dict, Any, List, Optional, Union
from tapo import ApiClient
import logging
from pydantic import BaseModel, Field, model_validator, Discriminator
from enum import Enum

from ...core.interfaces import ToolAdapter
from ...config.config_manager import ConfigManager


class TapoDeviceType(str, Enum):
    """Types d'appareils TAPO supportés"""
    P110 = "P110"  # Prise intelligente
    L530 = "L530"  # Ampoule couleur


class TapoAction(str, Enum):
    """Actions disponibles pour les appareils TAPO"""
    ON = "on"
    OFF = "off"
    TOGGLE = "toggle"
    GET_INFO = "get_info"
    SET_BRIGHTNESS = "set_brightness"  # L530 seulement
    SET_COLOR = "set_color"  # L530 seulement


# Actions autorisées par type d'appareil
DEVICE_ACTIONS = {
    TapoDeviceType.P110: [TapoAction.ON, TapoAction.OFF, TapoAction.TOGGLE, TapoAction.GET_INFO],
    TapoDeviceType.L530: [TapoAction.ON, TapoAction.OFF, TapoAction.TOGGLE, TapoAction.GET_INFO,
                          TapoAction.SET_BRIGHTNESS, TapoAction.SET_COLOR]
}

# Mappage dynamique des appareils vers leur type (rempli depuis la config)
DEVICE_TYPE_MAPPING: Dict[str, TapoDeviceType] = {}


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


# Modèles Pydantic spécifiques par action
class TapoBaseParameters(BaseModel):
    """Paramètres de base pour toutes les actions TAPO"""
    device_name: str = Field(
        description="Nom exact de l'appareil TAPO à contrôler (défini dans la configuration)"
    )

    @model_validator(mode='after')
    def validate_device_exists(self):
        """Valide que l'appareil existe dans la configuration"""
        if self.device_name not in DEVICE_TYPE_MAPPING:
            available_devices = list(DEVICE_TYPE_MAPPING.keys())
            raise ValueError(
                f"Appareil '{self.device_name}' non configuré. "
                f"Appareils disponibles: {available_devices}"
            )
        return self


class TapoOnParameters(TapoBaseParameters):
    """Paramètres pour l'action ON"""
    action: TapoAction = Field(default=TapoAction.ON, description="Allumer l'appareil")


class TapoOffParameters(TapoBaseParameters):
    """Paramètres pour l'action OFF"""
    action: TapoAction = Field(default=TapoAction.OFF, description="Éteindre l'appareil")


class TapoToggleParameters(TapoBaseParameters):
    """Paramètres pour l'action TOGGLE"""
    action: TapoAction = Field(default=TapoAction.TOGGLE, description="Basculer l'état de l'appareil")


class TapoGetInfoParameters(TapoBaseParameters):
    """Paramètres pour l'action GET_INFO"""
    action: TapoAction = Field(default=TapoAction.GET_INFO, description="Obtenir les informations de l'appareil")


class TapoSetBrightnessParameters(TapoBaseParameters):
    """Paramètres pour l'action SET_BRIGHTNESS (L530 seulement)"""
    action: TapoAction = Field(default=TapoAction.SET_BRIGHTNESS, description="Régler la luminosité")
    value: int = Field(
        ge=0,
        le=100,
        description="Valeur de luminosité de 0 à 100"
    )

    @model_validator(mode='after')
    def validate_device_supports_brightness(self):
        """Valide que l'appareil supporte le réglage de luminosité"""
        super().validate_device_exists()
        device_type = DEVICE_TYPE_MAPPING.get(self.device_name)
        if device_type and TapoAction.SET_BRIGHTNESS not in DEVICE_ACTIONS[device_type]:
            supported = [action.value for action in DEVICE_ACTIONS[device_type]]
            raise ValueError(
                f"Action 'set_brightness' non supportée pour {self.device_name} "
                f"(type {device_type.value}). Actions supportées: {supported}"
            )
        return self


class TapoSetColorRGBParameters(TapoBaseParameters):
    """Paramètres pour l'action SET_COLOR avec valeurs RGB (L530 seulement)"""
    action: TapoAction = Field(default=TapoAction.SET_COLOR, description="Changer la couleur")
    r: int = Field(ge=0, le=255, description="Rouge de 0 à 255")
    g: int = Field(ge=0, le=255, description="Vert de 0 à 255")
    b: int = Field(ge=0, le=255, description="Bleu de 0 à 255")

    @model_validator(mode='after')
    def validate_device_supports_color(self):
        """Valide que l'appareil supporte le changement de couleur"""
        super().validate_device_exists()
        device_type = DEVICE_TYPE_MAPPING.get(self.device_name)
        if device_type and TapoAction.SET_COLOR not in DEVICE_ACTIONS[device_type]:
            supported = [action.value for action in DEVICE_ACTIONS[device_type]]
            raise ValueError(
                f"Action 'set_color' non supportée pour {self.device_name} "
                f"(type {device_type.value}). Actions supportées: {supported}"
            )
        return self


class TapoSetColorNamedParameters(TapoBaseParameters):
    """Paramètres pour l'action SET_COLOR avec couleur nommée (L530 seulement)"""
    action: TapoAction = Field(default=TapoAction.SET_COLOR, description="Changer la couleur")
    color: str = Field(
        description=f"Nom de couleur: {', '.join(TAPO_COLORS.keys())}"
    )

    @model_validator(mode='after')
    def validate_color_and_device(self):
        """Valide la couleur et que l'appareil supporte le changement de couleur"""
        super().validate_device_exists()

        # Valider la couleur
        if self.color not in TAPO_COLORS:
            available = ", ".join(TAPO_COLORS.keys())
            raise ValueError(f"Couleur '{self.color}' non supportée. Disponibles: {available}")

        # Valider que l'appareil supporte les couleurs
        device_type = DEVICE_TYPE_MAPPING.get(self.device_name)
        if device_type and TapoAction.SET_COLOR not in DEVICE_ACTIONS[device_type]:
            supported = [action.value for action in DEVICE_ACTIONS[device_type]]
            raise ValueError(
                f"Action 'set_color' non supportée pour {self.device_name} "
                f"(type {device_type.value}). Actions supportées: {supported}"
            )
        return self


# Union discriminé basé sur le champ 'action' pour validation optimisée
def get_discriminator_value(v: Any) -> str:
    """Fonction discriminatrice pour identifier le bon modèle selon l'action"""
    if isinstance(v, dict):
        action = v.get('action')
        if action == 'on':
            return 'on'
        elif action == 'off':
            return 'off'
        elif action == 'toggle':
            return 'toggle'
        elif action == 'get_info':
            return 'get_info'
        elif action == 'set_brightness':
            return 'set_brightness'
        elif action == 'set_color':
            # Distinguer entre RGB et couleur nommée
            if 'color' in v and v['color'] is not None:
                return 'set_color_named'
            else:
                return 'set_color_rgb'
    return 'on'  # default


TapoUnifiedParameters = Union[
    TapoOnParameters,
    TapoOffParameters,
    TapoToggleParameters,
    TapoGetInfoParameters,
    TapoSetBrightnessParameters,
    TapoSetColorRGBParameters,
    TapoSetColorNamedParameters
]

# Modèle général pour LlamaIndex (tous paramètres optionnels sauf les obligatoires)
class TapoGeneralParameters(BaseModel):
    """Modèle général pour LlamaIndex avec tous les paramètres possibles"""
    device_name: str = Field(description="Nom exact de l'appareil TAPO à contrôler")
    action: TapoAction = Field(description="Action à effectuer sur l'appareil")
    # Paramètres optionnels selon l'action
    value: Optional[int] = Field(default=None, ge=0, le=100, description="Luminosité 0-100 (pour set_brightness)")
    r: Optional[int] = Field(default=None, ge=0, le=255, description="Rouge 0-255 (pour set_color)")
    g: Optional[int] = Field(default=None, ge=0, le=255, description="Vert 0-255 (pour set_color)")
    b: Optional[int] = Field(default=None, ge=0, le=255, description="Bleu 0-255 (pour set_color)")
    color: Optional[str] = Field(default=None, description=f"Couleur par nom: {', '.join(TAPO_COLORS.keys())} (pour set_color)")

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
        self.tool_name = config.get('tool_name', 'control_tapo_device')
        self.tool_description = config.get('tool_description', 'Contrôle des appareils Tapo connectés')
        
        # Client API
        self.client = None
        
        if not self.email or not self.password:
            raise ValueError("Email et mot de passe Tapo requis")

        # Mettre à jour le nom du tool depuis la config
        self.name = self.tool_name

        # Mettre à jour le mappage des types d'appareils selon la configuration
        self._update_device_type_mapping()

        # Construire la description dynamiquement avec la liste des appareils
        self._build_description()

    def _update_device_type_mapping(self) -> None:
        """Met à jour le mappage global des types d'appareils selon la config"""
        global DEVICE_TYPE_MAPPING

        # Réinitialiser le mappage
        DEVICE_TYPE_MAPPING.clear()

        # Construire le mappage depuis la configuration
        for device_id, device_config in self.devices.items():
            device_type_str = device_config.get('type', '').upper()
            try:
                device_type = TapoDeviceType(device_type_str)
                DEVICE_TYPE_MAPPING[device_id] = device_type
                self.logger.debug(f"Mappage ajouté: {device_id} -> {device_type.value}")
            except ValueError:
                self.logger.warning(f"Type d'appareil '{device_type_str}' non supporté pour {device_id}")

        self.logger.info(f"Mappage des appareils TAPO: {dict(DEVICE_TYPE_MAPPING)}")

    def get_pydantic_schema(self):
        """Retourne le schéma Pydantic pour les paramètres de l'outil"""
        # Retourner le modèle général qui peut être utilisé par LlamaIndex
        # La validation stricte se fera dans execute() avec les modèles spécifiques
        return TapoGeneralParameters

    def _build_description(self) -> None:
        """Construit la description avec la liste des appareils disponibles"""
        base_description = self.tool_description

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
            # Validation stricte avec le modèle unifié basé sur l'action
            # Le modèle correct sera automatiquement sélectionné selon l'action
            if 'action' not in kwargs:
                raise ValueError("Paramètre 'action' obligatoire")

            action_value = kwargs['action']
            device_name = kwargs.get('device_name')

            # Créer le bon modèle selon l'action
            if action_value == 'on':
                params = TapoOnParameters(**kwargs)
            elif action_value == 'off':
                params = TapoOffParameters(**kwargs)
            elif action_value == 'toggle':
                params = TapoToggleParameters(**kwargs)
            elif action_value == 'get_info':
                params = TapoGetInfoParameters(**kwargs)
            elif action_value == 'set_brightness':
                params = TapoSetBrightnessParameters(**kwargs)
            elif action_value == 'set_color':
                # Distinguer RGB vs couleur nommée
                if 'color' in kwargs and kwargs['color'] is not None:
                    params = TapoSetColorNamedParameters(**kwargs)
                    # Convertir couleur nommée en RGB pour l'exécution
                    r, g, b = TAPO_COLORS[params.color]
                    # Créer un objet temporaire avec RGB pour l'exécution
                    class TempParams:
                        def __init__(self, base_params, r, g, b):
                            self.device_name = base_params.device_name
                            self.action = base_params.action
                            self.r, self.g, self.b = r, g, b
                    params = TempParams(params, r, g, b)
                else:
                    params = TapoSetColorRGBParameters(**kwargs)
            else:
                raise ValueError(f"Action '{action_value}' non reconnue")

            action = action_value
            
            # Vérification déjà faite par la validation Pydantic, mais double sécurité
            if not device_name or device_name not in self.devices:
                return {
                    "success": False,
                    "error": f"Appareil '{device_name}' introuvable",
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
                # Cette erreur ne devrait jamais arriver grâce à la validation Pydantic
                return {
                    "success": False,
                    "error": f"Action non supportée: {action}",
                    "supported_actions": [action.value for action in TapoAction]
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

    def _rgb_to_hue_sat(self, r: int, g: int, b: int) -> tuple:
        """Convertit RGB (0-255) vers hue/saturation pour l'API Tapo"""
        # Normaliser les valeurs RGB (0-1)
        r_norm = r / 255.0
        g_norm = g / 255.0
        b_norm = b / 255.0

        max_val = max(r_norm, g_norm, b_norm)
        min_val = min(r_norm, g_norm, b_norm)
        diff = max_val - min_val

        # Calcul de la teinte (hue)
        if diff == 0:
            hue = 0
        elif max_val == r_norm:
            hue = (60 * ((g_norm - b_norm) / diff) + 360) % 360
        elif max_val == g_norm:
            hue = (60 * ((b_norm - r_norm) / diff) + 120) % 360
        else:
            hue = (60 * ((r_norm - g_norm) / diff) + 240) % 360

        # Calcul de la saturation
        saturation = 0 if max_val == 0 else (diff / max_val) * 100

        return int(hue), int(saturation)
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Schéma des paramètres pour OpenAI function calling avec paramètres conditionnels"""
        # Construire les enums dynamiquement depuis la configuration
        device_names = list(self.devices.keys()) if self.devices else []
        actions = [action.value for action in TapoAction]

        return {
            "type": "function",
            "function": {
                "name": "control_tapo_device",
                "description": "Contrôle les appareils Tapo avec paramètres conditionnels selon l'action",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_name": {
                            "type": "string",
                            "description": "Nom exact de l'appareil TAPO à contrôler",
                            "enum": device_names
                        },
                        "action": {
                            "type": "string",
                            "description": "Action à effectuer",
                            "enum": actions
                        }
                    },
                    "required": ["device_name", "action"],
                    "allOf": [
                        {
                            "if": {"properties": {"action": {"const": "set_brightness"}}},
                            "then": {
                                "properties": {
                                    "value": {
                                        "type": "integer",
                                        "description": "Luminosité 0-100 (OBLIGATOIRE pour set_brightness)",
                                        "minimum": 0,
                                        "maximum": 100
                                    }
                                },
                                "required": ["device_name", "action", "value"],
                                "additionalProperties": False
                            }
                        },
                        {
                            "if": {"properties": {"action": {"const": "set_color"}}},
                            "then": {
                                "oneOf": [
                                    {
                                        "properties": {
                                            "device_name": {"type": "string"},
                                            "action": {"const": "set_color"},
                                            "r": {"type": "integer", "minimum": 0, "maximum": 255, "description": "Rouge 0-255"},
                                            "g": {"type": "integer", "minimum": 0, "maximum": 255, "description": "Vert 0-255"},
                                            "b": {"type": "integer", "minimum": 0, "maximum": 255, "description": "Bleu 0-255"}
                                        },
                                        "required": ["device_name", "action", "r", "g", "b"],
                                        "additionalProperties": False
                                    },
                                    {
                                        "properties": {
                                            "device_name": {"type": "string"},
                                            "action": {"const": "set_color"},
                                            "color": {
                                                "type": "string",
                                                "description": f"Couleur par nom: {', '.join(TAPO_COLORS.keys())}",
                                                "enum": list(TAPO_COLORS.keys())
                                            }
                                        },
                                        "required": ["device_name", "action", "color"],
                                        "additionalProperties": False
                                    }
                                ]
                            }
                        },
                        {
                            "if": {
                                "properties": {
                                    "action": {
                                        "enum": ["on", "off", "toggle", "get_info"]
                                    }
                                }
                            },
                            "then": {
                                "properties": {
                                    "device_name": {"type": "string"},
                                    "action": {"type": "string"}
                                },
                                "required": ["device_name", "action"],
                                "additionalProperties": False
                            }
                        }
                    ]
                }
            }
        }
    
    async def validate_parameters(self, **kwargs) -> bool:
        """Valide les paramètres avec le modèle Pydantic strict"""
        try:
            # Utiliser la validation Pydantic stricte
            TapoUnifiedParameters(**kwargs)
            return True
        except Exception:
            return False