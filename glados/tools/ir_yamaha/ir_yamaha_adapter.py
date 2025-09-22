"""
Adaptateur pour le contrôle IR des amplificateurs Yamaha
Basé sur le script IR Yamaha de MarkIO - Fonctionnement uniquement sur Raspberry Pi
"""

import asyncio
import os
import platform
import time
from typing import Dict, Any, Union
import logging
from pydantic import BaseModel, Field, model_validator
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


# Modèles Pydantic stricts pour chaque type d'action
class YamahaBaseParameters(BaseModel):
    """Paramètres de base pour toutes les actions Yamaha IR"""

    @model_validator(mode='after')
    def validate_raspberry_pi(self):
        """Valide que le système est un Raspberry Pi avec lgpio disponible"""
        if not IS_RASPBERRY_PI:
            raise ValueError(
                "Contrôle IR Yamaha disponible uniquement sur Raspberry Pi. "
                f"Plateforme détectée: {platform.machine()}"
            )

        if not LGPIO_AVAILABLE:
            raise ValueError(
                "Module lgpio requis non disponible. Installez avec: sudo apt install python3-lgpio"
            )

        return self


class YamahaPowerParameters(YamahaBaseParameters):
    """Paramètres pour le contrôle d'alimentation Yamaha"""
    action: YamahaAction = Field(default=YamahaAction.POWER, description="Contrôle de l'alimentation")
    command: YamahaCommand = Field(description="Commande d'alimentation: power")
    double_send: bool = Field(
        default=True,
        description="Envoi double du signal pour fiabilité (recommandé pour POWER)"
    )

    @model_validator(mode='after')
    def validate_power_command(self):
        """Valide que la commande est bien une commande d'alimentation"""
        super().validate_raspberry_pi()

        if self.command not in COMMAND_ACTIONS[YamahaAction.POWER]:
            valid_commands = [cmd.value for cmd in COMMAND_ACTIONS[YamahaAction.POWER]]
            raise ValueError(
                f"Commande '{self.command}' invalide pour l'action 'power'. "
                f"Commandes valides: {valid_commands}"
            )
        return self


class YamahaVolumeParameters(YamahaBaseParameters):
    """Paramètres pour le contrôle de volume Yamaha"""
    action: YamahaAction = Field(default=YamahaAction.VOLUME, description="Contrôle du volume")
    command: YamahaCommand = Field(description="Commande de volume: vol_up ou vol_down")
    repeat_count: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Nombre de répétitions pour ajuster le volume (1-10)"
    )

    @model_validator(mode='after')
    def validate_volume_command(self):
        """Valide que la commande est bien une commande de volume"""
        super().validate_raspberry_pi()

        if self.command not in COMMAND_ACTIONS[YamahaAction.VOLUME]:
            valid_commands = [cmd.value for cmd in COMMAND_ACTIONS[YamahaAction.VOLUME]]
            raise ValueError(
                f"Commande '{self.command}' invalide pour l'action 'volume'. "
                f"Commandes valides: {valid_commands}"
            )
        return self


class YamahaPlaybackParameters(YamahaBaseParameters):
    """Paramètres pour le contrôle de lecture Yamaha"""
    action: YamahaAction = Field(default=YamahaAction.PLAYBACK, description="Contrôle de la lecture")
    command: YamahaCommand = Field(description="Commande de lecture: play, pause, stop, ff, rew")

    @model_validator(mode='after')
    def validate_playback_command(self):
        """Valide que la commande est bien une commande de lecture"""
        super().validate_raspberry_pi()

        if self.command not in COMMAND_ACTIONS[YamahaAction.PLAYBACK]:
            valid_commands = [cmd.value for cmd in COMMAND_ACTIONS[YamahaAction.PLAYBACK]]
            raise ValueError(
                f"Commande '{self.command}' invalide pour l'action 'playback'. "
                f"Commandes valides: {valid_commands}"
            )
        return self


class YamahaSourceParameters(YamahaBaseParameters):
    """Paramètres pour la sélection de source Yamaha"""
    action: YamahaAction = Field(default=YamahaAction.SOURCE, description="Sélection de source audio")
    command: YamahaCommand = Field(description="Source: tuner, tape, aux, md, dvd, mode (CD)")

    @model_validator(mode='after')
    def validate_source_command(self):
        """Valide que la commande est bien une commande de source"""
        super().validate_raspberry_pi()

        if self.command not in COMMAND_ACTIONS[YamahaAction.SOURCE]:
            valid_commands = [cmd.value for cmd in COMMAND_ACTIONS[YamahaAction.SOURCE]]
            raise ValueError(
                f"Commande '{self.command}' invalide pour l'action 'source'. "
                f"Commandes valides: {valid_commands}"
            )
        return self


class YamahaDigitParameters(YamahaBaseParameters):
    """Paramètres pour la saisie de chiffres Yamaha"""
    action: YamahaAction = Field(default=YamahaAction.DIGIT, description="Saisie de chiffres")
    command: YamahaCommand = Field(description="Chiffre: digit_0 à digit_9")

    @model_validator(mode='after')
    def validate_digit_command(self):
        """Valide que la commande est bien une commande de chiffre"""
        super().validate_raspberry_pi()

        if self.command not in COMMAND_ACTIONS[YamahaAction.DIGIT]:
            valid_commands = [cmd.value for cmd in COMMAND_ACTIONS[YamahaAction.DIGIT]]
            raise ValueError(
                f"Commande '{self.command}' invalide pour l'action 'digit'. "
                f"Commandes valides: {valid_commands}"
            )
        return self


class YamahaFunctionParameters(YamahaBaseParameters):
    """Paramètres pour les fonctions Yamaha"""
    action: YamahaAction = Field(default=YamahaAction.FUNCTION, description="Fonctions diverses")
    command: YamahaCommand = Field(description="Fonction: random, repeat, display, sleep, etc.")

    @model_validator(mode='after')
    def validate_function_command(self):
        """Valide que la commande est bien une commande de fonction"""
        super().validate_raspberry_pi()

        if self.command not in COMMAND_ACTIONS[YamahaAction.FUNCTION]:
            valid_commands = [cmd.value for cmd in COMMAND_ACTIONS[YamahaAction.FUNCTION]]
            raise ValueError(
                f"Commande '{self.command}' invalide pour l'action 'function'. "
                f"Commandes valides: {valid_commands}"
            )
        return self


# Union des paramètres Yamaha pour la validation
YamahaParameters = Union[
    YamahaPowerParameters,
    YamahaVolumeParameters,
    YamahaPlaybackParameters,
    YamahaSourceParameters,
    YamahaDigitParameters,
    YamahaFunctionParameters
]


def validate_yamaha_parameters(params_dict: Dict[str, Any]) -> Union[YamahaPowerParameters, YamahaVolumeParameters, YamahaPlaybackParameters, YamahaSourceParameters, YamahaDigitParameters, YamahaFunctionParameters]:
    """Valide et retourne les paramètres selon l'action"""
    action = params_dict.get('action')

    if action == 'power':
        return YamahaPowerParameters(**params_dict)
    elif action == 'volume':
        return YamahaVolumeParameters(**params_dict)
    elif action == 'playback':
        return YamahaPlaybackParameters(**params_dict)
    elif action == 'source':
        return YamahaSourceParameters(**params_dict)
    elif action == 'digit':
        return YamahaDigitParameters(**params_dict)
    elif action == 'function':
        return YamahaFunctionParameters(**params_dict)
    else:
        raise ValueError(f"Action '{action}' non supportée. Actions valides: power, volume, playback, source, digit, function")


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

        # Validation de la plateforme
        if not IS_RASPBERRY_PI:
            self.logger.error(f"Contrôle IR Yamaha non disponible sur {platform.machine()}")
        elif not LGPIO_AVAILABLE:
            self.logger.error("Module lgpio requis non disponible")

    async def initialize(self) -> bool:
        """Initialise l'adaptateur IR Yamaha"""
        if not IS_RASPBERRY_PI or not LGPIO_AVAILABLE:
            self.logger.warning("IR Yamaha désactivé (non Raspberry Pi ou lgpio manquant)")
            return False

        try:
            self.remote = YamahaRemote(self.ir_pin)
            self.logger.info(f"Adaptateur IR Yamaha initialisé (pin {self.ir_pin})")
            return True
        except Exception as e:
            self.logger.error(f"Erreur initialisation IR Yamaha: {e}")
            return False

    def get_parameters_schema(self) -> Dict[str, Any]:
        """Retourne le schéma des paramètres pour l'IR Yamaha"""
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
                    "default": False,
                    "description": "Envoi double du signal (recommandé pour POWER)"
                },
                "repeat_count": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 1,
                    "description": "Nombre de répétitions (pour volume uniquement)"
                }
            },
            "required": ["action", "command"]
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Exécute une commande IR Yamaha avec validation stricte"""
        if not self.remote:
            return {
                "success": False,
                "error": "Contrôle IR Yamaha non disponible (non Raspberry Pi ou lgpio manquant)"
            }

        try:
            # Récupérer les paramètres
            action = kwargs.get('action')
            command = kwargs.get('command')
            double_send = kwargs.get('double_send', False)
            repeat_count = kwargs.get('repeat_count', 1)

            return await self._control_yamaha_ir(action, command, double_send, repeat_count)

        except Exception as e:
            self.logger.error(f"Erreur contrôle IR Yamaha: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _control_yamaha_ir(self, action: str, command: str, double_send: bool = False, repeat_count: int = 1) -> Dict[str, Any]:
        """Exécute une commande IR Yamaha avec validation stricte"""
        try:
            # Validation stricte avec Pydantic
            params_dict = {
                'action': action,
                'command': command
            }

            # Ajouter les paramètres optionnels selon l'action
            if action == 'power':
                params_dict['double_send'] = double_send
            elif action == 'volume':
                params_dict['repeat_count'] = repeat_count

            # Validation avec la fonction helper
            validated_params = validate_yamaha_parameters(params_dict)

            # Conversion de la commande en format attendu
            command_upper = validated_params.command.value.upper()

            # Gestion des aliases et mapping
            command_mapping = {
                'VOL_UP': 'VOL_UP',
                'VOL_DOWN': 'VOL_DOWN',
                'FF': 'FF',
                'REW': 'REW',
                'MODE': 'MODE',
                'DIGIT_0': 'DIGIT_0',
                'DIGIT_1': 'DIGIT_1',
                'DIGIT_2': 'DIGIT_2',
                'DIGIT_3': 'DIGIT_3',
                'DIGIT_4': 'DIGIT_4',
                'DIGIT_5': 'DIGIT_5',
                'DIGIT_6': 'DIGIT_6',
                'DIGIT_7': 'DIGIT_7',
                'DIGIT_8': 'DIGIT_8',
                'DIGIT_9': 'DIGIT_9',
                'PRESET_UP': 'PRESET_UP',
                'PRESET_DOWN': 'PRESET_DN',
                'RANDOM': 'RANDOM_B',
                'REPEAT': 'REP_A'
            }

            final_command = command_mapping.get(command_upper, command_upper)

            # Gestion spéciale pour POWER
            use_double_send = getattr(validated_params, 'double_send', False) if action == 'power' else False
            use_repeat_count = getattr(validated_params, 'repeat_count', 1) if action == 'volume' else 1

            self.logger.info(f"Envoi commande IR Yamaha: {final_command} (double_send: {use_double_send}, repeat: {use_repeat_count})")

            # Envoi de la commande
            for i in range(use_repeat_count):
                success = self.remote.send_command(final_command, use_double_send)
                if not success:
                    return {
                        "success": False,
                        "error": f"Échec envoi commande IR Yamaha '{validated_params.command.value}'"
                    }

                # Délai entre répétitions
                if i < use_repeat_count - 1:
                    time.sleep(0.5)

            message = f"Commande IR Yamaha '{validated_params.command.value}' envoyée"
            if use_double_send:
                message += " (double envoi)"
            if use_repeat_count > 1:
                message += f" ({use_repeat_count} répétitions)"

            return {
                "success": True,
                "message": message,
                "action": validated_params.command.value,
                "double_send": use_double_send,
                "repeat_count": use_repeat_count
            }

        except Exception as e:
            self.logger.error(f"Erreur contrôle IR Yamaha: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        if self.remote:
            self.remote.cleanup()
        self.logger.info("Adaptateur IR Yamaha nettoyé")