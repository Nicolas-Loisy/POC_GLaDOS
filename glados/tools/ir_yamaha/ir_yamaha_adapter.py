"""
Adaptateur pour le contrôle IR des amplificateurs Yamaha
Basé sur le script IR Yamaha de MarkIO - Fonctionnement uniquement sur Raspberry Pi
"""

import asyncio
import os
import platform
import time
from typing import Dict, Any, Union, Optional, Annotated, Literal
import logging
from pydantic import BaseModel, Field, model_validator, Discriminator
from enum import Enum

from ...core.interfaces import ToolAdapter

# Vérification de la plateforme
IS_RASPBERRY_PI = platform.machine().startswith('arm') or platform.machine().startswith('aarch64')

# Import conditionnel du code IR Yamaha
if IS_RASPBERRY_PI:
    try:
        import lgpio
        LGPIO_AVAILABLE = True
    except ImportError:
        LGPIO_AVAILABLE = False
else:
    LGPIO_AVAILABLE = False


class YamahaCommand(str, Enum):
    """Commandes IR Yamaha disponibles"""
    # Contrôles principaux
    POWER = "power"
    VOL_UP = "vol_up"
    VOL_DOWN = "vol_down"

    # Lecture
    PLAY = "play"
    PAUSE = "pause"
    STOP = "stop"
    FF = "ff"
    REW = "rew"

    # Sources d'entrée
    TUNER = "tuner"
    TAPE = "tape"
    AUX = "aux"
    MD = "md"
    DVD = "dvd"
    MODE = "mode"  # CD/DISC

    # Fonctions avancées
    RANDOM = "random"
    REPEAT = "repeat"
    DISPLAY = "display"
    SLEEP = "sleep"

    # Chiffres
    DIGIT_0 = "digit_0"
    DIGIT_1 = "digit_1"
    DIGIT_2 = "digit_2"
    DIGIT_3 = "digit_3"
    DIGIT_4 = "digit_4"
    DIGIT_5 = "digit_5"
    DIGIT_6 = "digit_6"
    DIGIT_7 = "digit_7"
    DIGIT_8 = "digit_8"
    DIGIT_9 = "digit_9"

    # Fonctions spéciales
    MODE_10 = "mode_10"
    START_100 = "start_100"
    PRESET_UP = "preset_up"
    PRESET_DOWN = "preset_down"
    TIME = "time"


class YamahaAction(str, Enum):
    """Types d'actions pour le contrôle Yamaha"""
    POWER = "power"
    VOLUME = "volume"
    PLAYBACK = "playback"
    SOURCE = "source"
    PRESET = "preset"
    DIGIT = "digit"
    FUNCTION = "function"


# Mappage des commandes par catégorie d'action
COMMAND_ACTIONS = {
    YamahaAction.POWER: [YamahaCommand.POWER],
    YamahaAction.VOLUME: [YamahaCommand.VOL_UP, YamahaCommand.VOL_DOWN],
    YamahaAction.PLAYBACK: [
        YamahaCommand.PLAY, YamahaCommand.PAUSE, YamahaCommand.STOP,
        YamahaCommand.FF, YamahaCommand.REW
    ],
    YamahaAction.SOURCE: [
        YamahaCommand.TUNER, YamahaCommand.TAPE, YamahaCommand.AUX,
        YamahaCommand.MD, YamahaCommand.DVD, YamahaCommand.MODE
    ],
    YamahaAction.PRESET: [YamahaCommand.PRESET_UP, YamahaCommand.PRESET_DOWN],
    YamahaAction.DIGIT: [
        YamahaCommand.DIGIT_0, YamahaCommand.DIGIT_1, YamahaCommand.DIGIT_2,
        YamahaCommand.DIGIT_3, YamahaCommand.DIGIT_4, YamahaCommand.DIGIT_5,
        YamahaCommand.DIGIT_6, YamahaCommand.DIGIT_7, YamahaCommand.DIGIT_8,
        YamahaCommand.DIGIT_9
    ],
    YamahaAction.FUNCTION: [
        YamahaCommand.RANDOM, YamahaCommand.REPEAT, YamahaCommand.DISPLAY,
        YamahaCommand.SLEEP, YamahaCommand.MODE_10, YamahaCommand.START_100,
        YamahaCommand.TIME
    ]
}

# Mappage des aliases pour rétrocompatibilité
YAMAHA_ALIASES = {
    'pwr': YamahaCommand.POWER,
    'vol+': YamahaCommand.VOL_UP,
    'volup': YamahaCommand.VOL_UP,
    'vol-': YamahaCommand.VOL_DOWN,
    'voldown': YamahaCommand.VOL_DOWN,
    'forward': YamahaCommand.FF,
    'rewind': YamahaCommand.REW,
    'radio': YamahaCommand.TUNER,
    'cd': YamahaCommand.MODE,
    'disc': YamahaCommand.MODE,
    '0': YamahaCommand.DIGIT_0,
    '1': YamahaCommand.DIGIT_1,
    '2': YamahaCommand.DIGIT_2,
    '3': YamahaCommand.DIGIT_3,
    '4': YamahaCommand.DIGIT_4,
    '5': YamahaCommand.DIGIT_5,
    '6': YamahaCommand.DIGIT_6,
    '7': YamahaCommand.DIGIT_7,
    '8': YamahaCommand.DIGIT_8,
    '9': YamahaCommand.DIGIT_9
}


# Modèles Pydantic stricts par action avec validation
class YamahaBaseParameters(BaseModel):
    """Paramètres de base pour toutes les actions Yamaha IR"""
    pass

class YamahaPowerParameters(YamahaBaseParameters):
    """Paramètres pour le contrôle d'alimentation Yamaha"""
    action: YamahaAction = Field(default=YamahaAction.POWER, description="Action d'alimentation")
    command: YamahaCommand = Field(description="Commande: power")
    double_send: bool = Field(default=True, description="Envoi double pour fiabilité")

    @model_validator(mode='after')
    def validate_power_command(self):
        """Valide que la commande correspond à l'action power"""
        if self.command not in COMMAND_ACTIONS[YamahaAction.POWER]:
            valid_commands = [cmd.value for cmd in COMMAND_ACTIONS[YamahaAction.POWER]]
            raise ValueError(f"Commande '{self.command}' invalide pour action 'power'. Commandes valides: {valid_commands}")
        return self

class YamahaVolumeParameters(YamahaBaseParameters):
    """Paramètres pour le contrôle de volume Yamaha"""
    action: YamahaAction = Field(default=YamahaAction.VOLUME, description="Action de volume")
    command: YamahaCommand = Field(description="Commande: vol_up ou vol_down")
    repeat_count: int = Field(default=1, ge=1, le=10, description="Répétitions (1-10)")

    @model_validator(mode='after')
    def validate_volume_command(self):
        """Valide que la commande correspond à l'action volume"""
        if self.command not in COMMAND_ACTIONS[YamahaAction.VOLUME]:
            valid_commands = [cmd.value for cmd in COMMAND_ACTIONS[YamahaAction.VOLUME]]
            raise ValueError(f"Commande '{self.command}' invalide pour action 'volume'. Commandes valides: {valid_commands}")
        return self

class YamahaPlaybackParameters(YamahaBaseParameters):
    """Paramètres pour le contrôle de lecture Yamaha"""
    action: YamahaAction = Field(default=YamahaAction.PLAYBACK, description="Action de lecture")
    command: YamahaCommand = Field(description="Commande: play, pause, stop, ff, rew")

    @model_validator(mode='after')
    def validate_playback_command(self):
        """Valide que la commande correspond à l'action playback"""
        if self.command not in COMMAND_ACTIONS[YamahaAction.PLAYBACK]:
            valid_commands = [cmd.value for cmd in COMMAND_ACTIONS[YamahaAction.PLAYBACK]]
            raise ValueError(f"Commande '{self.command}' invalide pour action 'playback'. Commandes valides: {valid_commands}")
        return self

class YamahaSourceParameters(YamahaBaseParameters):
    """Paramètres pour la sélection de source Yamaha"""
    action: YamahaAction = Field(default=YamahaAction.SOURCE, description="Action de source")
    command: YamahaCommand = Field(description="Commande: tuner, tape, aux, md, dvd, mode")

    @model_validator(mode='after')
    def validate_source_command(self):
        """Valide que la commande correspond à l'action source"""
        if self.command not in COMMAND_ACTIONS[YamahaAction.SOURCE]:
            valid_commands = [cmd.value for cmd in COMMAND_ACTIONS[YamahaAction.SOURCE]]
            raise ValueError(f"Commande '{self.command}' invalide pour action 'source'. Commandes valides: {valid_commands}")
        return self

class YamahaDigitParameters(YamahaBaseParameters):
    """Paramètres pour la saisie de chiffres Yamaha"""
    action: YamahaAction = Field(default=YamahaAction.DIGIT, description="Action de chiffre")
    command: YamahaCommand = Field(description="Commande: digit_0 à digit_9")

    @model_validator(mode='after')
    def validate_digit_command(self):
        """Valide que la commande correspond à l'action digit"""
        if self.command not in COMMAND_ACTIONS[YamahaAction.DIGIT]:
            valid_commands = [cmd.value for cmd in COMMAND_ACTIONS[YamahaAction.DIGIT]]
            raise ValueError(f"Commande '{self.command}' invalide pour action 'digit'. Commandes valides: {valid_commands}")
        return self

class YamahaFunctionParameters(YamahaBaseParameters):
    """Paramètres pour les fonctions Yamaha"""
    action: YamahaAction = Field(default=YamahaAction.FUNCTION, description="Action de fonction")
    command: YamahaCommand = Field(description="Commande: random, repeat, display, sleep, etc.")

    @model_validator(mode='after')
    def validate_function_command(self):
        """Valide que la commande correspond à l'action function"""
        if self.command not in COMMAND_ACTIONS[YamahaAction.FUNCTION]:
            valid_commands = [cmd.value for cmd in COMMAND_ACTIONS[YamahaAction.FUNCTION]]
            raise ValueError(f"Commande '{self.command}' invalide pour action 'function'. Commandes valides: {valid_commands}")
        return self

# Union des paramètres Yamaha (sans discriminator pour simplifier)
YamahaParameters = Union[
    YamahaPowerParameters,
    YamahaVolumeParameters,
    YamahaPlaybackParameters,
    YamahaSourceParameters,
    YamahaDigitParameters,
    YamahaFunctionParameters
]


# Modèle général pour LlamaIndex avec littéraux stricts
class YamahaGeneralParameters(BaseModel):
    """Modèle général pour le contrôle Yamaha IR"""
    action: Literal["power", "volume", "playback", "source", "digit", "function"] = Field(description="Type d'action à effectuer")
    command: Literal[
        # Power
        "power",
        # Volume
        "vol_up", "vol_down",
        # Playback
        "play", "pause", "stop", "ff", "rew",
        # Source
        "tuner", "tape", "aux", "md", "dvd", "mode",
        # Digits
        "digit_0", "digit_1", "digit_2", "digit_3", "digit_4",
        "digit_5", "digit_6", "digit_7", "digit_8", "digit_9",
        # Functions
        "random", "repeat", "display", "sleep", "mode_10", "start_100", "preset_up", "preset_down", "time"
    ] = Field(description="Commande spécifique selon l'action")

    # Paramètres optionnels
    double_send: bool = Field(default=True, description="Envoi double du signal (pour power)")
    repeat_count: int = Field(default=1, ge=1, le=10, description="Répétitions (pour volume)")

    @model_validator(mode='after')
    def validate_action_command_compatibility(self):
        """Valide que la commande est compatible avec l'action"""
        # Mapping action -> commandes valides
        valid_combinations = {
            "power": ["power"],
            "volume": ["vol_up", "vol_down"],
            "playback": ["play", "pause", "stop", "ff", "rew"],
            "source": ["tuner", "tape", "aux", "md", "dvd", "mode"],
            "digit": ["digit_0", "digit_1", "digit_2", "digit_3", "digit_4",
                     "digit_5", "digit_6", "digit_7", "digit_8", "digit_9"],
            "function": ["random", "repeat", "display", "sleep", "mode_10",
                        "start_100", "preset_up", "preset_down", "time"]
        }

        if self.command not in valid_combinations[self.action]:
            valid_commands = valid_combinations[self.action]
            raise ValueError(f"Commande '{self.command}' invalide pour action '{self.action}'. Commandes valides: {valid_commands}")

        return self


class YamahaRemote:
    """
    Classe pour contrôler les amplificateurs Yamaha par IR
    Adaptée du script original pour intégration dans GLaDOS
    """

    def __init__(self, ir_pin: int = 18):
        self.ir_pin = ir_pin
        self.h = None
        self.YAMAHA_ADDRESS = 0x78

        # Codes de commandes Yamaha (du script original)
        self.commands = {
            'POWER': 0x0F,
            'DIGIT_0': 0x10,
            'DIGIT_1': 0x11,
            'DIGIT_2': 0x12,
            'DIGIT_3': 0x13,
            'DIGIT_4': 0x14,
            'DIGIT_5': 0x15,
            'DIGIT_6': 0x16,
            'DIGIT_7': 0x17,
            'DIGIT_8': 0x18,
            'DIGIT_9': 0x19,
            'MODE_10': 0x1A,
            'START_100': 0x1D,
            'REP_A': 0x0C,
            'RANDOM_B': 0x07,
            'PROG_C': 0x0B,
            'D_KEY': 0x09,
            'PAUSE': 0x0A,
            'TIME': 0x08,
            'PLAY': 0x02,
            'REW': 0x04,
            'STOP': 0x01,
            'FF': 0x03,
            'TAPE_DIR': 0x43,
            'PRESET_DN': 0x1C,
            'TUNER': 0x4B,
            'PRESET_UP': 0x1B,
            'MD': 0x57,
            'DVD': 0x4A,
            'TAPE': 0x41,
            'AUX': 0x49,
            'MD_REC': 0x58,
            'TAPE_REC': 0x46,
            'MODE': 0x05,
            'START': 0x06,
            'SLEEP': 0x4F,
            'VOL_UP': 0x1E,
            'DISPLAY': 0x4E,
            'VOL_DOWN': 0x1F
        }

        # Optimisations timing
        self.carrier_freq = 38000
        self.duty_cycle = 0.33

        self.init_gpio()

    def init_gpio(self):
        """Initialise la connexion GPIO avec lgpio"""
        if not LGPIO_AVAILABLE:
            raise RuntimeError("lgpio non disponible")

        try:
            self.h = lgpio.gpiochip_open(0)
            lgpio.gpio_claim_output(self.h, self.ir_pin, 0)
        except Exception as e:
            raise RuntimeError(f"Erreur d'initialisation GPIO: {e}")

    def nec_encode(self, address: int, command: int) -> list:
        """Encode une commande au format NEC"""
        data = []

        # AGC burst: 9ms ON, 4.5ms OFF
        data.extend([9000, 4500])

        # Address (8 bits, LSB first)
        for i in range(8):
            if (address >> i) & 1:
                data.extend([560, 1690])  # Bit 1
            else:
                data.extend([560, 560])   # Bit 0

        # ~Address (8 bits, LSB first)
        address_inv = (~address) & 0xFF
        for i in range(8):
            if (address_inv >> i) & 1:
                data.extend([560, 1690])  # Bit 1
            else:
                data.extend([560, 560])   # Bit 0

        # Command (8 bits, LSB first)
        for i in range(8):
            if (command >> i) & 1:
                data.extend([560, 1690])  # Bit 1
            else:
                data.extend([560, 560])   # Bit 0

        # ~Command (8 bits, LSB first)
        command_inv = (~command) & 0xFF
        for i in range(8):
            if (command_inv >> i) & 1:
                data.extend([560, 1690])  # Bit 1
            else:
                data.extend([560, 560])   # Bit 0

        # Stop bit
        data.append(560)

        return data

    def send_ir_burst(self, duration_us: int):
        """Génère une rafale IR modulée à 38kHz"""
        if duration_us <= 0:
            return

        period_us = 26.3  # 1000000 / 38000
        on_time_us = period_us * self.duty_cycle
        off_time_us = period_us - on_time_us

        cycles = int(duration_us / period_us)

        on_time_ns = int(on_time_us * 1000)
        off_time_ns = int(off_time_us * 1000)

        start_time = time.time_ns()

        for cycle in range(cycles):
            lgpio.gpio_write(self.h, self.ir_pin, 1)
            target_time = start_time + (cycle * period_us * 1000) + on_time_ns
            while time.time_ns() < target_time:
                pass

            lgpio.gpio_write(self.h, self.ir_pin, 0)
            target_time = start_time + ((cycle + 1) * period_us * 1000)
            while time.time_ns() < target_time:
                pass

        lgpio.gpio_write(self.h, self.ir_pin, 0)

    def send_ir_signal(self, pulses: list):
        """Envoie le signal IR avec timing précis"""
        try:
            try:
                os.nice(-10)  # Priorité plus haute
            except:
                pass

            start_time = time.time_ns()

            for i, duration in enumerate(pulses):
                if i % 2 == 0:  # Impulsion ON
                    self.send_ir_burst(duration)
                else:  # Pause OFF
                    lgpio.gpio_write(self.h, self.ir_pin, 0)
                    target_time = start_time + sum(pulses[:i+1]) * 1000
                    while time.time_ns() < target_time:
                        pass

            lgpio.gpio_write(self.h, self.ir_pin, 0)

        except Exception as e:
            raise RuntimeError(f"Erreur lors de l'envoi IR: {e}")

    def send_command(self, command_name: str, double_send: bool = False) -> bool:
        """Envoie une commande IR Yamaha"""
        # Conversion en majuscules
        command_upper = command_name.upper()

        if command_upper not in self.commands:
            return False

        command_code = self.commands[command_upper]

        # Encode et envoie
        pulses = self.nec_encode(self.YAMAHA_ADDRESS, command_code)
        self.send_ir_signal(pulses)

        # Double envoi si demandé
        if double_send:
            time.sleep(0.108)  # Gap standard NEC
            self.send_ir_signal(pulses)

        return True

    def cleanup(self):
        """Nettoie les ressources"""
        if self.h is not None:
            lgpio.gpio_write(self.h, self.ir_pin, 0)
            lgpio.gpiochip_close(self.h)


class IRYamahaAdapter(ToolAdapter):
    """Adaptateur pour le contrôle IR des amplificateurs Yamaha"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.logger = logging.getLogger(__name__)

        # Configuration
        self.ir_pin = config.get('ir_pin', 18)
        self.tool_name = config.get('tool_name', 'control_yamaha_ir')
        self.tool_description = config.get('tool_description', 'Contrôle Yamaha par infrarouge')
        self.remote = None

        # Mettre à jour le nom et la description depuis la config
        self.name = self.tool_name
        self.description = self.tool_description

        if IS_RASPBERRY_PI and LGPIO_AVAILABLE:
            try:
                self.remote = YamahaRemote(self.ir_pin)
                self.logger.info(f"Adaptateur IR Yamaha initialisé (pin {self.ir_pin})")
            except Exception as e:
                self.logger.error(f"Erreur initialisation IR Yamaha: {e}")
                self.remote = None
        else:
            self.logger.warning(f"IR Yamaha désactivé (plateforme: {platform.machine()}, lgpio: {LGPIO_AVAILABLE})")
            self.remote = None

    def get_parameters_schema(self) -> Dict[str, Any]:
        """Retourne le schéma des paramètres pour l'IR Yamaha (format OpenAI)"""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["power", "volume", "playback", "source", "digit", "function"],
                    "description": "Type d'action à effectuer"
                },
                "command": {
                    "type": "string",
                    "description": "Commande spécifique selon l'action"
                },
                "double_send": {
                    "type": "boolean",
                    "default": True,
                    "description": "Envoi double du signal (pour power)"
                },
                "repeat_count": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 1,
                    "description": "Répétitions (pour volume)"
                }
            },
            "required": ["action", "command"]
        }

    def get_pydantic_schema(self):
        """Retourne le modèle Pydantic pour LlamaIndex"""
        return YamahaGeneralParameters

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Exécute une commande IR Yamaha avec validation stricte"""
        if not self.remote:
            return {
                "success": False,
                "error": "Contrôle IR Yamaha non disponible (non Raspberry Pi ou lgpio manquant)"
            }

        try:
            # Validation stricte avec Pydantic
            params = YamahaGeneralParameters(**kwargs)

            # Exécuter selon l'action validée
            return await self._execute_validated_command(params)

        except Exception as e:
            self.logger.error(f"Erreur contrôle IR Yamaha: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _execute_validated_command(self, params: YamahaGeneralParameters) -> Dict[str, Any]:
        """Exécute une commande Yamaha après validation"""
        # Mapping des commandes vers format attendu par le remote
        command_mapping = {
            'power': 'POWER',
            'vol_up': 'VOL_UP',
            'vol_down': 'VOL_DOWN',
            'play': 'PLAY',
            'pause': 'PAUSE',
            'stop': 'STOP',
            'ff': 'FF',
            'rew': 'REW',
            'tuner': 'TUNER',
            'tape': 'TAPE',
            'aux': 'AUX',
            'md': 'MD',
            'dvd': 'DVD',
            'mode': 'MODE',
            'digit_0': 'DIGIT_0',
            'digit_1': 'DIGIT_1',
            'digit_2': 'DIGIT_2',
            'digit_3': 'DIGIT_3',
            'digit_4': 'DIGIT_4',
            'digit_5': 'DIGIT_5',
            'digit_6': 'DIGIT_6',
            'digit_7': 'DIGIT_7',
            'digit_8': 'DIGIT_8',
            'digit_9': 'DIGIT_9',
            'random': 'RANDOM_B',
            'repeat': 'REP_A',
            'display': 'DISPLAY',
            'sleep': 'SLEEP',
            'preset_up': 'PRESET_UP',
            'preset_down': 'PRESET_DN'
        }

        remote_command = command_mapping.get(params.command)
        if not remote_command:
            return {"success": False, "error": f"Commande '{params.command}' non mappée"}

        # Paramètres d'envoi selon l'action
        use_double_send = params.double_send if params.action == "power" else False
        use_repeat_count = params.repeat_count if params.action == "volume" else 1

        self.logger.info(f"Envoi commande IR Yamaha: {params.action}/{params.command} -> {remote_command}")

        # Envoi avec répétitions si nécessaire
        for i in range(use_repeat_count):
            success = self.remote.send_command(remote_command, use_double_send)
            if not success:
                return {"success": False, "error": f"Échec envoi commande '{params.command}'"}

            if i < use_repeat_count - 1:
                time.sleep(0.5)

        # Construire le message de résultat
        message = f"Commande {params.action}/{params.command} envoyée"
        if use_double_send:
            message += " (double envoi)"
        if use_repeat_count > 1:
            message += f" (x{use_repeat_count})"

        return {
            "success": True,
            "message": message,
            "action": params.action,
            "command": params.command,
            "double_send": use_double_send,
            "repeat_count": use_repeat_count
        }


    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        if self.remote:
            self.remote.cleanup()
        self.logger.info("Adaptateur IR Yamaha nettoyé")