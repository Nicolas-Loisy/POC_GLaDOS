"""
Module de sortie Terminal pour GLaDOS
Affiche les réponses formatées dans le terminal
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

from ...core.interfaces import OutputModule, GLaDOSMessage, MessageType


class TerminalOutput(OutputModule):
    """
    Module de sortie pour affichage terminal
    Formate et affiche les messages GLaDOS dans la console
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.logger = logging.getLogger(__name__)
        
        # Configuration terminal
        self.color_scheme = config.get('color_scheme', 'green')
        self.prefix = config.get('prefix', '[GLaDOS] ')
        self.show_timestamp = config.get('show_timestamp', False)
        self.show_source = config.get('show_source', False)
        
        # Couleurs ANSI
        self.colors = {
            'green': '\033[92m',
            'blue': '\033[94m',
            'red': '\033[91m',
            'yellow': '\033[93m',
            'magenta': '\033[95m',
            'cyan': '\033[96m',
            'white': '\033[97m',
            'reset': '\033[0m',
            'bold': '\033[1m',
            'dim': '\033[2m'
        }
        
        # Couleurs selon le type de message
        self.message_type_colors = {
            MessageType.TEXT: self.color_scheme,
            MessageType.VOICE: 'cyan',
            MessageType.COMMAND: 'yellow',
            MessageType.ERROR: 'red',
            MessageType.STATUS: 'blue'
        }
    
    async def initialize(self) -> bool:
        """Initialise le module de sortie terminal"""
        try:
            self.logger.info("Initialisation du module Terminal Output...")
            self.is_active = True
            self.logger.info("Module Terminal Output initialisé avec succès")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur initialisation Terminal Output: {e}")
            return False
    
    async def send_message(self, message: GLaDOSMessage) -> bool:
        """
        Affiche un message dans le terminal avec formatage
        """
        if not self.is_active:
            return False
        
        try:
            # Construire le message formaté
            formatted_message = self._format_message(message)
            
            # Afficher le message
            print(formatted_message)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur affichage terminal: {e}")
            return False
    
    def _format_message(self, message: GLaDOSMessage) -> str:
        """
        Formate un message pour l'affichage terminal
        """
        # Déterminer la couleur selon le type de message
        color = self.message_type_colors.get(message.message_type, 'white')
        color_code = self.colors.get(color, '')
        reset_code = self.colors['reset']
        bold_code = self.colors['bold']
        
        # Construire le préfixe
        parts = []
        
        # Timestamp (optionnel)
        if self.show_timestamp:
            timestamp = datetime.now().strftime('%H:%M:%S')
            parts.append(f"[{timestamp}]")
        
        # Préfixe GLaDOS
        parts.append(f"{color_code}{bold_code}{self.prefix}{reset_code}")
        
        # Source (optionnel)
        if self.show_source and message.source:
            parts.append(f"{self.colors['dim']}({message.source}){reset_code}")
        
        # Indicateur de type de message
        type_indicator = self._get_type_indicator(message.message_type)
        if type_indicator:
            parts.append(f"{color_code}{type_indicator}{reset_code}")
        
        # Contenu du message
        content = self._format_content(message.content, message.message_type)
        parts.append(f"{color_code}{content}{reset_code}")
        
        return ' '.join(parts)
    
    def _get_type_indicator(self, message_type: MessageType) -> str:
        """Retourne un indicateur visuel pour le type de message"""
        indicators = {
            MessageType.TEXT: '',
            MessageType.VOICE: '🎤',
            MessageType.COMMAND: '⚡',
            MessageType.ERROR: '❌',
            MessageType.STATUS: 'ℹ️'
        }
        return indicators.get(message_type, '')
    
    def _format_content(self, content: str, message_type: MessageType) -> str:
        """
        Formate le contenu du message selon son type
        """
        if message_type == MessageType.ERROR:
            return f"Erreur: {content}"
        elif message_type == MessageType.STATUS:
            return f"Statut: {content}"
        elif message_type == MessageType.COMMAND:
            return f"Commande: {content}"
        else:
            return content
    
    def can_handle_message_type(self, message_type: MessageType) -> bool:
        """Vérifie si ce module peut traiter ce type de message"""
        # Le terminal peut afficher tous les types de messages
        return True
    
    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        self.is_active = False
        self.logger.info("Module Terminal Output nettoyé")
    
    def set_color_scheme(self, color_scheme: str) -> None:
        """Change le schéma de couleurs"""
        if color_scheme in self.colors:
            self.color_scheme = color_scheme
            self.message_type_colors[MessageType.TEXT] = color_scheme
            self.logger.info(f"Schéma de couleurs changé: {color_scheme}")
    
    def toggle_timestamp(self) -> None:
        """Active/désactive l'affichage du timestamp"""
        self.show_timestamp = not self.show_timestamp
        status = "activé" if self.show_timestamp else "désactivé"
        self.logger.info(f"Timestamp {status}")
    
    def toggle_source(self) -> None:
        """Active/désactive l'affichage de la source"""
        self.show_source = not self.show_source
        status = "activé" if self.show_source else "désactivé"
        self.logger.info(f"Affichage source {status}")