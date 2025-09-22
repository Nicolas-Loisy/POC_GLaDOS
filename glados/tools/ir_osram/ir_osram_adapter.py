"""
Adaptateur pour le contrôle IR des ampoules OSRAM RGBW
Basé sur le script IR OSRAM de MarkIO - Fonctionnement uniquement sur Raspberry Pi
"""

import asyncio
import platform
from typing import Dict, Any, List, Optional, Union
import logging
from pydantic import BaseModel, Field, model_validator, Discriminator
from enum import Enum

from ...core.interfaces import ToolAdapter

# Vérification de la plateforme
IS_RASPBERRY_PI = platform.machine().startswith('arm') or platform.machine().startswith('aarch64')

# Import conditionnel du code IR OSRAM
if IS_RASPBERRY_PI:
    try:
        import lgpio
        LGPIO_AVAILABLE = True
    except ImportError:
        LGPIO_AVAILABLE = False
else:
    LGPIO_AVAILABLE = False


class OsramCommand(str, Enum):
    """Commandes IR OSRAM RGBW disponibles"""
    # Contrôles principaux
    ON = "on"
    OFF = "off"
    BRIGHT_UP = "bright_up"
    BRIGHT_DOWN = "bright_down"

    # Couleurs principales
    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    WHITE = "white"

    # Couleurs étendues
    RED1 = "red1"
    GREEN1 = "green1"
    BLUE1 = "blue1"
    RED2 = "red2"
    GREEN2 = "green2"
    BLUE2 = "blue2"
    RED3 = "red3"
    GREEN3 = "green3"
    BLUE3 = "blue3"
    RED4 = "red4"
    GREEN4 = "green4"
    BLUE4 = "blue4"

    # Couleurs nommées (aliases)
    ORANGE = "orange"
    CYAN = "cyan"
    PURPLE = "purple"
    YELLOW = "yellow"
    PINK = "pink"
    LIME = "lime"
    VIOLET = "violet"
    MAGENTA = "magenta"

    # Effets lumineux
    FLASH = "flash"
    STROBE = "strobe"
    SMOOTH = "smooth"
    MODE = "mode"


class OsramAction(str, Enum):
    """Types d'actions pour le contrôle OSRAM"""
    POWER = "power"
    BRIGHTNESS = "brightness"
    COLOR = "color"
    EFFECT = "effect"


# Mappage des commandes par catégorie d'action
COMMAND_ACTIONS = {
    OsramAction.POWER: [OsramCommand.ON, OsramCommand.OFF],
    OsramAction.BRIGHTNESS: [OsramCommand.BRIGHT_UP, OsramCommand.BRIGHT_DOWN],
    OsramAction.COLOR: [
        OsramCommand.RED, OsramCommand.GREEN, OsramCommand.BLUE, OsramCommand.WHITE,
        OsramCommand.RED1, OsramCommand.GREEN1, OsramCommand.BLUE1,
        OsramCommand.RED2, OsramCommand.GREEN2, OsramCommand.BLUE2,
        OsramCommand.RED3, OsramCommand.GREEN3, OsramCommand.BLUE3,
        OsramCommand.RED4, OsramCommand.GREEN4, OsramCommand.BLUE4,
        OsramCommand.ORANGE, OsramCommand.CYAN, OsramCommand.PURPLE,
        OsramCommand.YELLOW, OsramCommand.PINK, OsramCommand.LIME,
        OsramCommand.VIOLET, OsramCommand.MAGENTA
    ],
    OsramAction.EFFECT: [OsramCommand.FLASH, OsramCommand.STROBE, OsramCommand.SMOOTH, OsramCommand.MODE]
}

# Mappage des aliases pour rétrocompatibilité
OSRAM_ALIASES = {
    'power_on': OsramCommand.ON,
    'power_off': OsramCommand.OFF,
    'power': OsramCommand.ON,
    'bright+': OsramCommand.BRIGHT_UP,
    'bright-': OsramCommand.BRIGHT_DOWN,
    'brighter': OsramCommand.BRIGHT_UP,
    'dimmer': OsramCommand.BRIGHT_DOWN,
    'light_up': OsramCommand.BRIGHT_UP,
    'light_down': OsramCommand.BRIGHT_DOWN,
    'r': OsramCommand.RED,
    'g': OsramCommand.GREEN,
    'b': OsramCommand.BLUE,
    'w': OsramCommand.WHITE,
    'blink': OsramCommand.FLASH,
    'stroboscope': OsramCommand.STROBE,
    'gradual': OsramCommand.SMOOTH
}


# Modèles Pydantic stricts pour chaque type d'action
class OsramBaseParameters(BaseModel):
    """Paramètres de base pour toutes les actions OSRAM IR"""

    @model_validator(mode='after')
    def validate_raspberry_pi(self):
        """Valide que le système est un Raspberry Pi avec lgpio disponible"""
        if not IS_RASPBERRY_PI:
            raise ValueError(
                "Contrôle IR OSRAM disponible uniquement sur Raspberry Pi. "
                f"Plateforme détectée: {platform.machine()}"
            )

        if not LGPIO_AVAILABLE:
            raise ValueError(
                "Module lgpio requis non disponible. Installez avec: sudo apt install python3-lgpio"
            )

        return self


class OsramPowerParameters(OsramBaseParameters):
    """Paramètres pour le contrôle d'alimentation OSRAM"""
    action: OsramAction = Field(default=OsramAction.POWER, description="Contrôle de l'alimentation")
    command: OsramCommand = Field(description="Commande d'alimentation: on ou off")
    repeat_count: int = Field(
        default=0,
        ge=0,
        le=5,
        description="Nombre de répétitions du signal (0-5)"
    )

    @model_validator(mode='after')
    def validate_power_command(self):
        """Valide que la commande est bien une commande d'alimentation"""
        super().validate_raspberry_pi()

        if self.command not in COMMAND_ACTIONS[OsramAction.POWER]:
            valid_commands = [cmd.value for cmd in COMMAND_ACTIONS[OsramAction.POWER]]
            raise ValueError(
                f"Commande '{self.command}' invalide pour l'action 'power'. "
                f"Commandes valides: {valid_commands}"
            )
        return self


class OsramBrightnessParameters(OsramBaseParameters):
    """Paramètres pour le contrôle de luminosité OSRAM"""
    action: OsramAction = Field(default=OsramAction.BRIGHTNESS, description="Contrôle de la luminosité")
    command: OsramCommand = Field(description="Commande de luminosité: bright_up ou bright_down")
    repeat_count: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Nombre de répétitions pour ajuster l'intensité (1-10)"
    )

    @model_validator(mode='after')
    def validate_brightness_command(self):
        """Valide que la commande est bien une commande de luminosité"""
        super().validate_raspberry_pi()

        if self.command not in COMMAND_ACTIONS[OsramAction.BRIGHTNESS]:
            valid_commands = [cmd.value for cmd in COMMAND_ACTIONS[OsramAction.BRIGHTNESS]]
            raise ValueError(
                f"Commande '{self.command}' invalide pour l'action 'brightness'. "
                f"Commandes valides: {valid_commands}"
            )
        return self


class OsramColorParameters(OsramBaseParameters):
    """Paramètres pour le contrôle de couleur OSRAM"""
    action: OsramAction = Field(default=OsramAction.COLOR, description="Contrôle de la couleur")
    command: OsramCommand = Field(description="Commande de couleur (red, green, blue, white, etc.)")
    repeat_count: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Nombre de répétitions pour maintenir la couleur (0-3)"
    )

    @model_validator(mode='after')
    def validate_color_command(self):
        """Valide que la commande est bien une commande de couleur"""
        super().validate_raspberry_pi()

        if self.command not in COMMAND_ACTIONS[OsramAction.COLOR]:
            valid_commands = [cmd.value for cmd in COMMAND_ACTIONS[OsramAction.COLOR]]
            raise ValueError(
                f"Commande '{self.command}' invalide pour l'action 'color'. "
                f"Commandes valides: {valid_commands}"
            )
        return self


class OsramEffectParameters(OsramBaseParameters):
    """Paramètres pour les effets lumineux OSRAM"""
    action: OsramAction = Field(default=OsramAction.EFFECT, description="Effets lumineux")
    command: OsramCommand = Field(description="Commande d'effet: flash, strobe, smooth, mode")
    repeat_count: int = Field(
        default=0,
        ge=0,
        le=2,
        description="Nombre de répétitions pour activer l'effet (0-2)"
    )

    @model_validator(mode='after')
    def validate_effect_command(self):
        """Valide que la commande est bien une commande d'effet"""
        super().validate_raspberry_pi()

        if self.command not in COMMAND_ACTIONS[OsramAction.EFFECT]:
            valid_commands = [cmd.value for cmd in COMMAND_ACTIONS[OsramAction.EFFECT]]
            raise ValueError(
                f"Commande '{self.command}' invalide pour l'action 'effect'. "
                f"Commandes valides: {valid_commands}"
            )
        return self


# Union discriminé pour la validation automatique des paramètres
def get_discriminator_value(v: Any) -> str:
    """Fonction discriminatrice pour identifier le bon modèle selon l'action"""
    if isinstance(v, dict):
        action = v.get('action')
        if action == 'power':
            return 'power'
        elif action == 'brightness':
            return 'brightness'
        elif action == 'color':
            return 'color'
        elif action == 'effect':
            return 'effect'
    return 'power'  # default


OsramParameters = Discriminator(
    discriminator=get_discriminator_value,
    custom_serializer=lambda x: x.model_dump(),
    choices={
        'power': OsramPowerParameters,
        'brightness': OsramBrightnessParameters,
        'color': OsramColorParameters,
        'effect': OsramEffectParameters,
    }
)


class OsramRGBWRemote:
    """
    Classe pour contrôler les ampoules OSRAM RGBW par IR
    Adaptée du script original pour intégration dans GLaDOS
    """

    def __init__(self, ir_pin: int = 18):
        self.ir_pin = ir_pin
        self.h = None
        self.OSRAM_ADDRESS = 0x00

        # Codes de commandes OSRAM (du script original)
        self.commands = {
            'ON': 0x07,
            'OFF': 0x06,
            'BRIGHT_UP': 0x00,
            'BRIGHT_DOWN': 0x02,
            'RED': 0x08,
            'GREEN': 0x09,
            'BLUE': 0x0A,
            'WHITE': 0x03,
            'RED1': 0x0C,
            'GREEN1': 0x0D,
            'BLUE1': 0x0E,
            'FLASH': 0x0F,
            'RED2': 0x10,
            'GREEN2': 0x11,
            'BLUE2': 0x12,
            'STROBE': 0x13,
            'RED3': 0x14,
            'GREEN3': 0x15,
            'BLUE3': 0x16,
            'SMOOTH': 0x17,
            'RED4': 0x18,
            'GREEN4': 0x19,
            'BLUE4': 0x1A,
            'MODE': 0x1B
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

        # Compléter à 71 impulsions
        while len(data) < 71:
            data.append(560)

        return data

    def send_ir_burst(self, duration_us: int):
        """Génère une rafale IR modulée à 38kHz"""
        if duration_us <= 0:
            return

        import time

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
        import time
        import os

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

    def send_command(self, command_name: str, repeat_count: int = 0) -> bool:
        """Envoie une commande IR OSRAM"""
        # Conversion en majuscules et gestion des aliases
        command_upper = command_name.upper()

        if command_upper not in self.commands:
            return False

        command_code = self.commands[command_upper]

        # Encode et envoie
        pulses = self.nec_encode(self.OSRAM_ADDRESS, command_code)
        self.send_ir_signal(pulses)

        # Répétitions si demandées
        import time
        for _ in range(repeat_count):
            time.sleep(0.108)  # Gap standard NEC
            self.send_ir_signal(pulses)

        return True

    def cleanup(self):
        """Nettoie les ressources"""
        if self.h is not None:
            lgpio.gpio_write(self.h, self.ir_pin, 0)
            lgpio.gpiochip_close(self.h)


class IROsramAdapter(ToolAdapter):
    """Adaptateur pour le contrôle IR des ampoules OSRAM RGBW"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.logger = logging.getLogger(__name__)

        # Configuration
        self.ir_pin = config.get('ir_pin', 18)
        self.remote = None

        # Validation de la plateforme
        if not IS_RASPBERRY_PI:
            self.logger.error(f"Contrôle IR OSRAM non disponible sur {platform.machine()}")
        elif not LGPIO_AVAILABLE:
            self.logger.error("Module lgpio requis non disponible")

    async def initialize(self) -> bool:
        """Initialise l'adaptateur IR OSRAM"""
        if not IS_RASPBERRY_PI or not LGPIO_AVAILABLE:
            self.logger.warning("IR OSRAM désactivé (non Raspberry Pi ou lgpio manquant)")
            return False

        try:
            self.remote = OsramRGBWRemote(self.ir_pin)
            self.logger.info(f"Adaptateur IR OSRAM initialisé (pin {self.ir_pin})")
            return True
        except Exception as e:
            self.logger.error(f"Erreur initialisation IR OSRAM: {e}")
            return False

    def create_tools(self) -> List:
        """Crée les outils LlamaIndex pour le contrôle IR OSRAM"""
        if not self.remote:
            return []

        from llama_index.core.tools import FunctionTool

        def control_osram_ir(
            action: str,
            command: str,
            repeat_count: int = 0
        ) -> str:
            """
            Contrôle une ampoule OSRAM RGBW par infrarouge.

            Args:
                action: Type d'action ('power', 'brightness', 'color', 'effect')
                command: Commande spécifique (ex: 'on', 'red', 'bright_up', 'flash')
                repeat_count: Nombre de répétitions du signal (optionnel, 0-10)

            Returns:
                Résultat de l'opération
            """
            return asyncio.run(self._control_osram_ir(action, command, repeat_count))

        return [
            FunctionTool.from_defaults(
                fn=control_osram_ir,
                name="control_osram_ir",
                description="Contrôle d'une ampoule OSRAM RGBW par infrarouge (Ampoule de la chambre)."
            )
        ]

    async def _control_osram_ir(self, action: str, command: str, repeat_count: int = 0) -> str:
        """Exécute une commande IR OSRAM avec validation stricte"""
        if not self.remote:
            return "Contrôle IR OSRAM non disponible (non Raspberry Pi ou lgpio manquant)"

        try:
            # Validation stricte avec Pydantic
            params_dict = {
                'action': action,
                'command': command,
                'repeat_count': repeat_count
            }

            # Le discriminator choisit automatiquement le bon modèle
            validated_params = OsramParameters.validate_python(params_dict)

            # Conversion de la commande en format attendu
            command_upper = validated_params.command.value.upper()

            # Gestion des aliases
            if command_upper == 'ORANGE':
                command_upper = 'RED1'
            elif command_upper == 'CYAN':
                command_upper = 'BLUE1'
            elif command_upper == 'PURPLE':
                command_upper = 'RED2'
            elif command_upper == 'YELLOW':
                command_upper = 'GREEN2'
            elif command_upper == 'PINK':
                command_upper = 'RED3'
            elif command_upper == 'LIME':
                command_upper = 'GREEN3'
            elif command_upper == 'VIOLET':
                command_upper = 'BLUE3'
            elif command_upper == 'MAGENTA':
                command_upper = 'RED4'

            self.logger.info(f"Envoi commande IR OSRAM: {command_upper} (répétitions: {validated_params.repeat_count})")

            # Envoi de la commande
            success = self.remote.send_command(command_upper, validated_params.repeat_count)

            if success:
                result = f"Commande IR OSRAM '{validated_params.command.value}' envoyée"
                if validated_params.repeat_count > 0:
                    result += f" ({validated_params.repeat_count} répétitions)"
                return result
            else:
                return f"Échec envoi commande IR OSRAM '{validated_params.command.value}'"

        except Exception as e:
            self.logger.error(f"Erreur contrôle IR OSRAM: {e}")
            return f"Erreur: {str(e)}"

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        if self.remote:
            self.remote.cleanup()
        self.logger.info("Adaptateur IR OSRAM nettoyé")