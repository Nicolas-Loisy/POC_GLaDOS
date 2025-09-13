"""
Moteur ReAct pour GLaDOS basé sur LlamaIndex
Orchestrateur principal qui gère les interactions entre inputs, outputs et tools
"""

import asyncio
from typing import Dict, List, Any, Optional
import logging
from llama_index.core.agent import ReActAgent
from llama_index.llms.openai import OpenAI
from llama_index.core.tools import BaseTool, FunctionTool
from llama_index.core.memory import ChatMemoryBuffer

from .interfaces import (
    InputModule, OutputModule, ToolAdapter, 
    GLaDOSMessage, GLaDOSEvent, MessageType,
    InputModuleFactory, OutputModuleFactory, ToolAdapterFactory
)
from ..config.config_manager import ConfigManager, GLaDOSConfig


class GLaDOSReActEngine:
    """
    Moteur principal de GLaDOS utilisant ReAct de LlamaIndex
    Pattern: Orchestrator + Observer
    """
    
    def __init__(self, config: GLaDOSConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Composants ReAct
        self.llm = None
        self.agent = None
        self.tools: List[BaseTool] = []
        self.memory = ChatMemoryBuffer.from_defaults(token_limit=4000)
        
        # Modules GLaDOS
        self.input_modules: Dict[str, InputModule] = {}
        self.output_modules: Dict[str, OutputModule] = {}
        self.tool_adapters: Dict[str, ToolAdapter] = {}
        
        # État du moteur
        self.is_running = False
        self.conversation_context = {}
    
    async def initialize(self) -> bool:
        """
        Initialise le moteur ReAct et tous les modules
        """
        try:
            self.logger.info("Initialisation du moteur GLaDOS ReAct...")
            
            # 1. Initialiser le LLM
            await self._initialize_llm()
            
            # 2. Charger et initialiser les tools
            await self._initialize_tools()
            
            # 3. Créer l'agent ReAct
            await self._initialize_agent()
            
            # 4. Initialiser les modules d'entrée et de sortie
            await self._initialize_modules()
            
            self.logger.info("Moteur GLaDOS initialisé avec succès")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'initialisation: {e}")
            return False
    
    async def _initialize_llm(self) -> None:
        """Initialise le modèle de langage"""
        self.llm = OpenAI(
            model=self.config.core.model_name,
            temperature=self.config.core.temperature,
            api_key=ConfigManager().get_env_var('OPENAI_API_KEY')
        )
        self.logger.info(f"LLM initialisé: {self.config.core.model_name}")
    
    async def _initialize_tools(self) -> None:
        """Charge et initialise tous les outils/tools"""
        self.logger.info("Chargement des outils...")
        
        for tool_name, tool_config in self.config.tools.items():
            if not tool_config.get('enabled', False):
                continue
                
            try:
                # Créer l'adaptateur d'outil
                adapter = ToolAdapterFactory.create(tool_name, tool_name, tool_config)
                self.tool_adapters[tool_name] = adapter
                
                # Créer l'outil LlamaIndex
                llama_tool = self._create_llama_tool(adapter)
                self.tools.append(llama_tool)
                
                self.logger.info(f"Outil chargé: {tool_name}")
                
            except Exception as e:
                self.logger.error(f"Erreur lors du chargement de l'outil {tool_name}: {e}")
    
    def _create_llama_tool(self, adapter: ToolAdapter) -> FunctionTool:
        """
        Crée un outil LlamaIndex à partir d'un adaptateur
        """
        async def tool_function(**kwargs):
            try:
                result = await adapter.execute(**kwargs)
                return result
            except Exception as e:
                return {"error": str(e), "success": False}
        
        return FunctionTool.from_defaults(
            fn=tool_function,
            name=adapter.name,
            description=adapter.description,
            fn_schema=adapter.get_parameters_schema()
        )
    
    async def _initialize_agent(self) -> None:
        """Initialise l'agent ReAct"""
        system_prompt = self._build_system_prompt()
        
        self.agent = ReActAgent.from_tools(
            tools=self.tools,
            llm=self.llm,
            memory=self.memory,
            system_prompt=system_prompt,
            max_iterations=self.config.core.max_iterations,
            verbose=self.config.core.verbose
        )
        
        self.logger.info("Agent ReAct initialisé")
    
    def _build_system_prompt(self) -> str:
        """Construit le prompt système pour GLaDOS"""
        prompt = """
Vous êtes GLaDOS, un assistant vocal intelligent et configurable.

Votre personnalité :
- Intelligent et efficace
- Légèrement sarcastique mais utile
- Orienté solutions
- Capable de contrôler divers appareils intelligents

Vos capacités :
- Contrôler les appareils connectés (lumières, prises, etc.)
- Répondre aux questions
- Exécuter des commandes système
- Interagir via voix, texte ou Discord

Instructions importantes :
- Soyez concis mais informatif
- Confirmez les actions avant de les exécuter
- Gérez les erreurs avec élégance
- Adaptez votre réponse au contexte de la conversation

Outils disponibles :
"""
        
        # Ajouter la description des outils
        for tool in self.tools:
            prompt += f"- {tool.metadata.name}: {tool.metadata.description}\n"
        
        return prompt
    
    async def _initialize_modules(self) -> None:
        """Initialise les modules d'entrée et de sortie"""
        # Initialiser les modules d'entrée
        if self.config.inputs.enabled:
            await self._initialize_input_modules()
        
        # Initialiser les modules de sortie
        if self.config.outputs.enabled:
            await self._initialize_output_modules()
    
    async def _initialize_input_modules(self) -> None:
        """Initialise les modules d'entrée"""
        inputs_config = self.config.inputs
        
        # Wake word + STT
        if inputs_config.wake_word and inputs_config.wake_word.get('enabled', False):
            try:
                module = InputModuleFactory.create('wake_word', 'wake_word', inputs_config.wake_word)
                await module.initialize()
                module.subscribe_to_messages(self._handle_input_message)
                self.input_modules['wake_word'] = module
                self.logger.info("Module Wake Word initialisé")
            except Exception as e:
                self.logger.error(f"Erreur initialisation Wake Word: {e}")
        
        # Discord
        if inputs_config.discord and inputs_config.discord.get('enabled', False):
            try:
                module = InputModuleFactory.create('discord', 'discord', inputs_config.discord)
                await module.initialize()
                module.subscribe_to_messages(self._handle_input_message)
                self.input_modules['discord'] = module
                self.logger.info("Module Discord initialisé")
            except Exception as e:
                self.logger.error(f"Erreur initialisation Discord: {e}")
        
        # Terminal
        if inputs_config.terminal and inputs_config.terminal.get('enabled', True):
            try:
                module = InputModuleFactory.create('terminal', 'terminal', inputs_config.terminal)
                await module.initialize()
                module.subscribe_to_messages(self._handle_input_message)
                self.input_modules['terminal'] = module
                self.logger.info("Module Terminal initialisé")
            except Exception as e:
                self.logger.error(f"Erreur initialisation Terminal: {e}")
        
        # Web Interface
        if hasattr(inputs_config, 'web') and inputs_config.web and inputs_config.web.get('enabled', False):
            try:
                module = InputModuleFactory.create('web', 'web', inputs_config.web)
                await module.initialize()
                module.subscribe_to_messages(self._handle_input_message)
                self.input_modules['web'] = module
                self.logger.info("Module Web Interface initialisé")
            except Exception as e:
                self.logger.error(f"Erreur initialisation Web Interface: {e}")
    
    async def _initialize_output_modules(self) -> None:
        """Initialise les modules de sortie"""
        outputs_config = self.config.outputs
        
        # TTS GLaDOS
        if outputs_config.tts_glados and outputs_config.tts_glados.get('enabled', False):
            try:
                module = OutputModuleFactory.create('tts_glados', 'tts_glados', outputs_config.tts_glados)
                await module.initialize()
                self.output_modules['tts_glados'] = module
                self.logger.info("Module TTS GLaDOS initialisé")
            except Exception as e:
                self.logger.error(f"Erreur initialisation TTS GLaDOS: {e}")
        
        # Terminal output
        if outputs_config.terminal and outputs_config.terminal.get('enabled', True):
            try:
                module = OutputModuleFactory.create('terminal_output', 'terminal_output', outputs_config.terminal)
                await module.initialize()
                self.output_modules['terminal_output'] = module
                self.logger.info("Module Terminal Output initialisé")
            except Exception as e:
                self.logger.error(f"Erreur initialisation Terminal Output: {e}")
    
    async def _handle_input_message(self, message: GLaDOSMessage) -> None:
        """
        Traite un message d'entrée et génère une réponse
        """
        try:
            self.logger.info(f"Message reçu de {message.source}: {message.content}")
            
            # Traiter le message avec l'agent ReAct
            response = await self._process_with_agent(message.content)
            
            # Créer le message de réponse
            response_message = GLaDOSMessage(
                content=response,
                message_type=MessageType.TEXT,
                source="glados_engine",
                metadata={
                    "original_source": message.source,
                    "original_type": message.message_type.value
                }
            )
            
            # Envoyer la réponse via les modules de sortie appropriés
            await self._send_response(response_message, message.source)
            
        except Exception as e:
            self.logger.error(f"Erreur lors du traitement du message: {e}")
            
            # Envoyer un message d'erreur
            error_message = GLaDOSMessage(
                content=f"Désolé, j'ai rencontré une erreur: {str(e)}",
                message_type=MessageType.ERROR,
                source="glados_engine"
            )
            await self._send_response(error_message, message.source)
    
    async def _process_with_agent(self, query: str) -> str:
        """
        Traite une requête avec l'agent ReAct
        """
        try:
            # Utiliser l'agent pour traiter la requête
            response = await self.agent.achat(query)
            return str(response)
        
        except Exception as e:
            self.logger.error(f"Erreur lors du traitement par l'agent: {e}")
            return f"Je n'ai pas pu traiter votre demande: {str(e)}"
    
    async def _send_response(self, message: GLaDOSMessage, original_source: str) -> None:
        """
        Envoie une réponse via les modules de sortie appropriés
        """
        # Déterminer quels modules de sortie utiliser selon la source
        output_modules_to_use = []
        
        if original_source == "wake_word":
            # Pour les commandes vocales, privilégier TTS + terminal
            if "tts_glados" in self.output_modules:
                output_modules_to_use.append(self.output_modules["tts_glados"])
            if "terminal_output" in self.output_modules:
                output_modules_to_use.append(self.output_modules["terminal_output"])
        
        elif original_source == "terminal":
            # Pour le terminal, utiliser la sortie terminal
            if "terminal_output" in self.output_modules:
                output_modules_to_use.append(self.output_modules["terminal_output"])
        
        elif original_source == "web":
            # Pour l'interface web, envoyer vers web et terminal
            if "web" in self.input_modules:
                # Envoyer la réponse vers l'interface web
                try:
                    await self.input_modules["web"].send_response_to_web(message.content)
                except Exception as e:
                    self.logger.error(f"Erreur envoi réponse web: {e}")
            
            if "terminal_output" in self.output_modules:
                output_modules_to_use.append(self.output_modules["terminal_output"])
        
        elif original_source == "discord":
            # Pour Discord, renvoyer sur Discord (à implémenter)
            pass
        
        # Si aucun module spécifique, utiliser tous les modules actifs
        if not output_modules_to_use:
            output_modules_to_use = list(self.output_modules.values())
        
        # Envoyer le message
        for module in output_modules_to_use:
            try:
                await module.send_message(message)
            except Exception as e:
                self.logger.error(f"Erreur envoi via {module.name}: {e}")
    
    async def start(self) -> None:
        """Démarre le moteur GLaDOS"""
        if self.is_running:
            self.logger.warning("Le moteur GLaDOS est déjà en cours d'exécution")
            return
        
        self.logger.info("Démarrage du moteur GLaDOS...")
        self.is_running = True
        
        # Démarrer tous les modules d'entrée
        start_tasks = []
        for module in self.input_modules.values():
            start_tasks.append(module.start_listening())
        
        if start_tasks:
            await asyncio.gather(*start_tasks, return_exceptions=True)
        
        self.logger.info("Moteur GLaDOS démarré")
    
    async def stop(self) -> None:
        """Arrête le moteur GLaDOS"""
        if not self.is_running:
            return
        
        self.logger.info("Arrêt du moteur GLaDOS...")
        self.is_running = False
        
        # Arrêter tous les modules
        cleanup_tasks = []
        
        for module in self.input_modules.values():
            cleanup_tasks.append(module.cleanup())
        
        for module in self.output_modules.values():
            cleanup_tasks.append(module.cleanup())
        
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        self.logger.info("Moteur GLaDOS arrêté")
    
    def is_active(self) -> bool:
        """Retourne l'état du moteur"""
        return self.is_running