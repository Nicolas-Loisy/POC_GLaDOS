"""
Moteur ReAct pour GLaDOS basé sur LlamaIndex
Orchestrateur principal qui gère les interactions entre inputs, outputs et tools
"""

import asyncio
from typing import Dict, List, Any, Optional
import logging
from llama_index.core.agent.workflow import ReActAgent
from llama_index.core.tools import BaseTool, FunctionTool
from llama_index.core.memory import ChatMemoryBuffer

from .interfaces import (
    InputModule, OutputModule, ToolAdapter,
    GLaDOSMessage, GLaDOSEvent, MessageType
)
from .factories import InputModuleFactory, OutputModuleFactory, ToolAdapterFactory, LLMFactory
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
        """Initialise le modèle de langage via la factory"""
        try:
            llm_config = self.config.core.llm
            if not llm_config:
                raise ValueError("Configuration LLM manquante")

            self.llm = LLMFactory.create(llm_config)

            llm_type = llm_config.get('type', 'unknown')
            llm_model = llm_config.get('params', {}).get('model', 'unknown')
            self.logger.info(f"LLM initialisé: {llm_type}/{llm_model}")

        except Exception as e:
            self.logger.error(f"Erreur lors de l'initialisation du LLM: {e}")
            raise
    
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
                # Log des paramètres bruts reçus
                self.logger.info(f"🔧 Appel de l'outil '{adapter.name}' avec les paramètres bruts: {kwargs}")

                # Passer directement les kwargs à l'adaptateur
                # Le schéma Pydantic s'occupera de la validation et extraction
                result = await adapter.execute(**kwargs)
                self.logger.info(f"✅ Résultat de l'outil '{adapter.name}': {result}")
                return result
            except Exception as e:
                self.logger.error(f"❌ Erreur dans l'outil '{adapter.name}': {str(e)}")
                return {"error": str(e), "success": False}

        # Récupérer le schéma Pydantic si disponible
        fn_schema = None
        if hasattr(adapter, 'get_pydantic_schema'):
            fn_schema = adapter.get_pydantic_schema()

        return FunctionTool.from_defaults(
            fn=tool_function,
            name=adapter.name,
            description=adapter.description,
            fn_schema=fn_schema
        )

    async def _initialize_agent(self) -> None:
        """Initialise l'agent ReAct"""
        system_prompt = self._build_system_prompt()

        self.agent = ReActAgent(
            tools=self.tools,
            llm=self.llm,
            timeout=120,
            verbose=self.config.core.verbose
        )

        # Récupérer le react_header actuel
        react_header = self.agent.get_prompts()["react_header"]
        # Ajouter le system_prompt avant le template existant
        react_header.template = system_prompt + react_header.template
        # Mettre à jour l'agent
        self.agent.update_prompts({"react_header": react_header})

        self.logger.info("Agent ReAct initialisé")
    
    def _build_system_prompt(self) -> str:
        """Construit le prompt système pour GLaDOS depuis la configuration"""
        # Récupérer le prompt depuis la config
        base_prompt = getattr(self.config.core, 'system_prompt', '')

        # Fallback si pas de prompt dans la config
        if not base_prompt:
            base_prompt = """Tu es GLaDOS, l'intelligence artificielle sarcastique d'Aperture Science. Réponds avec sarcasme et humour noir. Réponds UNIQUEMENT en français."""

        prompt = base_prompt

        # Ajouter la description des outils
        if self.tools:
            prompt += "\n\nOUTILS DISPONIBLES :\n"
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
        """Initialise automatiquement tous les modules d'entrée configurés"""
        self.input_modules = await InputModuleFactory.create_modules_from_config(
            self.config.inputs,
            self._handle_input_message,
            self.logger
        )
    
    async def _initialize_output_modules(self) -> None:
        """Initialise automatiquement tous les modules de sortie configurés"""
        self.output_modules = await OutputModuleFactory.create_modules_from_config(
            self.config.outputs,
            self.logger
        )
    
    async def _handle_input_message(self, message: GLaDOSMessage) -> None:
        """
        Traite un message d'entrée et génère une réponse
        """
        try:
            self.logger.info(f"Message reçu de {message.source}: {message.content}")
            
            # Traiter le message avec l'agent ReAct
            response = await self._process_with_agent(message.content)
            self.logger.info(f"Réponse générée: '{response}'")

            # Créer le message de réponse en préservant les métadonnées originales
            response_metadata = {
                "original_source": message.source,
                "original_type": message.message_type.value
            }

            # Préserver les métadonnées du message original pour les modules qui en ont besoin
            if message.metadata:
                response_metadata.update(message.metadata)

            response_message = GLaDOSMessage(
                content=response,
                message_type=MessageType.TEXT,
                source="glados_engine",
                metadata=response_metadata
            )

            self.logger.info(f"Envoi de la réponse vers {message.source}")
            # Envoyer la réponse via les modules de sortie appropriés
            await self._send_response(response_message, message.source)
            
        except Exception as e:
            self.logger.error(f"Erreur lors du traitement du message: {e}")
            
            # Envoyer un message d'erreur en préservant les métadonnées
            error_metadata = {
                "original_source": message.source,
                "original_type": message.message_type.value
            }
            if message.metadata:
                error_metadata.update(message.metadata)

            error_message = GLaDOSMessage(
                content=f"Désolé, j'ai rencontré une erreur: {str(e)}",
                message_type=MessageType.ERROR,
                source="glados_engine",
                metadata=error_metadata
            )
            await self._send_response(error_message, message.source)
    
    async def _process_with_agent(self, query: str) -> str:
        """
        Traite une requête avec l'agent ReAct
        """
        try:
            # Utiliser l'agent ReAct pour tout - il décidera automatiquement s'il faut des outils
            from llama_index.core.workflow import Context

            ctx = Context(self.agent)
            result = await self.agent.run(ctx=ctx, user_msg=query, max_iterations=10)
            self.logger.info(f"Réponse de l'agent: {result}")
            return str(result)

        except Exception as e:
            self.logger.error(f"Erreur lors du traitement par l'agent: {e}")
            return f"Je n'ai pas pu traiter votre demande: {str(e)}"
    
    async def _send_response(self, message: GLaDOSMessage, original_source: str) -> None:
        """
        Envoie une réponse via les modules de sortie configurés pour chaque source d'entrée
        """
        output_modules_to_use = []

        # Récupérer la liste des outputs configurée pour cette source d'entrée
        configured_outputs = self._get_configured_outputs_for_source(original_source)

        if configured_outputs:
            # Utiliser les outputs configurés pour cette source
            for output_name in configured_outputs:
                if output_name in self.output_modules:
                    output_modules_to_use.append(self.output_modules[output_name])
                else:
                    self.logger.warning(f"Module de sortie '{output_name}' configuré mais non disponible pour source '{original_source}'")
        else:
            # Fallback : utiliser tous les modules actifs si aucune configuration spécifique
            self.logger.debug(f"Aucune configuration d'outputs trouvée pour '{original_source}', utilisation de tous les modules actifs")
            output_modules_to_use = list(self.output_modules.values())

        # Gestion des réponses personnalisées pour les modules d'entrée
        if original_source in self.input_modules:
            try:
                await self.input_modules[original_source].send_response(message.content, message.metadata)
            except Exception as e:
                self.logger.error(f"Erreur envoi réponse {original_source}: {e}")

        # Envoyer le message via les modules de sortie sélectionnés
        for module in output_modules_to_use:
            try:
                await module.send_message(message)
            except Exception as e:
                self.logger.error(f"Erreur envoi via {module.name}: {e}")

    def _get_configured_outputs_for_source(self, source: str) -> list:
        """
        Récupère la liste des outputs configurés pour une source d'entrée donnée

        Args:
            source: Nom de la source d'entrée

        Returns:
            Liste des noms des modules de sortie à utiliser
        """
        # Parcourir la configuration des inputs pour trouver les outputs configurés
        for attr_name in dir(self.config.inputs):
            if attr_name.startswith('_') or attr_name == 'enabled':
                continue

            if attr_name == source:
                input_config = getattr(self.config.inputs, attr_name, None)
                if isinstance(input_config, dict):
                    return input_config.get('outputs', [])

        return []
    
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