"""
Module d'entrée Discord pour GLaDOS
Interface Discord Bot avec commandes personnalisées
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ...core.interfaces import InputModule, GLaDOSMessage, MessageType

# Vérification des dépendances Discord
try:
    import discord
    from discord.ext import commands
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    DEPENDENCIES_AVAILABLE = False
    MISSING_DEPENDENCY = str(e)


class DiscordInput(InputModule):
    """Module d'entrée Discord Bot pour GLaDOS"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.logger = logging.getLogger(__name__)

        # Configuration Discord
        self.bot_token = config.get('bot_token')
        self.command_prefix = config.get('command_prefix', '!')
        self.allowed_channels = config.get('allowed_channels', [])
        self.allowed_users = config.get('allowed_users', [])

        # État
        self.bot = None
        self.is_running = False

        if not DEPENDENCIES_AVAILABLE:
            self.logger.error(f"Dépendances Discord manquantes: {MISSING_DEPENDENCY}")
        elif not self.bot_token:
            self.logger.error("Token Discord manquant dans la configuration")

    async def initialize(self) -> bool:
        """Initialise le bot Discord"""
        if not DEPENDENCIES_AVAILABLE:
            self.logger.error("discord.py non disponible")
            return False

        if not self.bot_token:
            self.logger.error("Token Discord requis")
            return False

        try:
            # Configuration des intents Discord
            intents = discord.Intents.default()
            intents.message_content = True  # Nécessaire pour lire les messages

            # Créer le bot Discord
            self.bot = commands.Bot(
                command_prefix=self.command_prefix,
                intents=intents,
                help_command=None  # Désactiver l'aide par défaut
            )

            # Enregistrer les événements
            self._setup_events()
            self._setup_commands()

            self.logger.info("Module Discord initialisé")
            return True

        except Exception as e:
            self.logger.error(f"Erreur initialisation Discord: {e}")
            return False

    def _setup_events(self):
        """Configure les événements Discord"""

        @self.bot.event
        async def on_ready():
            self.logger.info(f"Bot Discord connecté: {self.bot.user}")
            self.is_running = True

        @self.bot.event
        async def on_disconnect():
            self.logger.warning("Bot Discord déconnecté")
            self.is_running = False

        @self.bot.event
        async def on_resumed():
            self.logger.info("Bot Discord reconnecté")
            self.is_running = True

        @self.bot.event
        async def on_message(message):
            # Ignorer les messages du bot lui-même
            if message.author == self.bot.user:
                return

            # Vérifier les canaux autorisés
            if self.allowed_channels and str(message.channel.id) not in self.allowed_channels:
                return

            # Vérifier les utilisateurs autorisés
            if self.allowed_users and str(message.author.id) not in self.allowed_users:
                return

            # Traiter les commandes avec préfixe
            if message.content.startswith(self.command_prefix):
                await self.bot.process_commands(message)
                return

            # Traiter les messages mentionnant le bot
            if self.bot.user.mentioned_in(message):
                content = message.content.replace(f'<@{self.bot.user.id}>', '').strip()
                if content:
                    await self._process_message(message, content)

    def _setup_commands(self):
        """Configure les commandes Discord"""

        @self.bot.command(name='glados', aliases=['g', 'ask'])
        async def glados_command(ctx, *, question: str = None):
            """Poser une question à GLaDOS"""
            if not question:
                await ctx.send("Vous devez poser une question, sujet de test.")
                return

            await self._process_message(ctx.message, question)

        @self.bot.command(name='status')
        async def status_command(ctx):
            """Vérifier le statut de GLaDOS"""
            status_msg = f"GLaDOS est {'en ligne' if self.is_active else 'hors ligne'}"
            await ctx.send(status_msg)

        @self.bot.command(name='help')
        async def help_command(ctx):
            """Afficher l'aide"""
            help_text = f"""
**Commandes GLaDOS:**
- `{self.command_prefix}glados <question>` - Poser une question à GLaDOS
- `{self.command_prefix}status` - Vérifier le statut
- `{self.command_prefix}help` - Afficher cette aide

Vous pouvez aussi mentionner le bot (@{self.bot.user.name}) suivi de votre message.
            """
            await ctx.send(help_text)

    async def _process_message(self, discord_message, content: str):
        """Traite un message Discord et l'envoie à GLaDOS"""
        try:
            # Créer le message GLaDOS
            glados_message = GLaDOSMessage(
                content=content,
                message_type=MessageType.TEXT,
                source=self.name,
                metadata={
                    "discord_user": str(discord_message.author),
                    "discord_user_id": str(discord_message.author.id),
                    "discord_channel": str(discord_message.channel),
                    "discord_channel_id": str(discord_message.channel.id),
                    "discord_guild": str(discord_message.guild) if discord_message.guild else "DM",
                    "timestamp": datetime.now().isoformat(),
                    "original_message": discord_message
                }
            )

            self.logger.info(f"Message Discord reçu de {discord_message.author}: {content}")

            # Envoyer le message à GLaDOS
            await self.emit_message(glados_message)

        except Exception as e:
            self.logger.error(f"Erreur traitement message Discord: {e}")
            await discord_message.channel.send("Une erreur est survenue lors du traitement de votre message.")

    async def start_listening(self) -> None:
        """Démarre le bot Discord"""
        if not self.bot or not self.bot_token:
            self.logger.error("Bot Discord non configuré")
            return

        try:
            self.logger.info("Démarrage du bot Discord...")
            # Lancer le bot en arrière-plan
            asyncio.create_task(self.bot.start(self.bot_token))
            await asyncio.sleep(2)  # Attendre la connexion
            self.logger.info("Bot Discord démarré")

        except Exception as e:
            self.logger.error(f"Erreur démarrage bot Discord: {e}")

    async def stop_listening(self) -> None:
        """Arrête le bot Discord"""
        if self.bot and not self.bot.is_closed():
            await self.bot.close()
            self.is_running = False
            self.logger.info("Bot Discord arrêté")

    async def cleanup(self) -> None:
        """Nettoie les ressources Discord"""
        await self.stop_listening()

    async def send_response(self, response: str, metadata: Dict[str, Any] = None) -> None:
        """Envoie une réponse GLaDOS vers Discord"""
        await self.send_response_to_discord(response, metadata)

    async def send_response_to_discord(self, response: str, original_message_metadata: dict = None):
        """Envoie une réponse GLaDOS vers Discord"""
        if not self.bot or not self.is_running:
            self.logger.warning("Bot Discord non actif")
            return

        try:
            self.logger.debug(f"Métadonnées reçues: {original_message_metadata}")

            # Récupérer les informations du message original depuis les métadonnées
            if original_message_metadata and 'original_message' in original_message_metadata:
                original_message = original_message_metadata['original_message']
                channel = original_message.channel
                self.logger.debug(f"Canal trouvé via original_message: {channel}")
            elif original_message_metadata and 'discord_channel_id' in original_message_metadata:
                # Fallback: utiliser l'ID du canal
                channel_id = int(original_message_metadata['discord_channel_id'])
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    self.logger.error(f"Canal Discord introuvable: {channel_id}")
                    return
                self.logger.debug(f"Canal trouvé via discord_channel_id: {channel}")
            else:
                self.logger.error(f"Métadonnées du message original manquantes ou incomplètes")
                self.logger.error(f"Métadonnées disponibles: {list(original_message_metadata.keys()) if original_message_metadata else 'None'}")
                return

            # Limiter la taille du message Discord (2000 caractères max)
            if len(response) > 2000:
                response = response[:1997] + "..."

            await channel.send(response)
            self.logger.info(f"Réponse envoyée sur Discord: {response[:50]}...")

        except Exception as e:
            self.logger.error(f"Erreur envoi réponse Discord: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")