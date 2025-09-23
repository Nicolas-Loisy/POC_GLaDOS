"""
Adaptateur pour les informations météorologiques via OpenWeatherMap API
"""

import aiohttp
from typing import Dict, Any
import logging
import re
from pydantic import BaseModel, Field, model_validator

from ...core.interfaces import ToolAdapter
from ...config.config_manager import ConfigManager


class WeatherParameters(BaseModel):
    """Paramètres pour les requêtes météorologiques"""
    city: str = Field(
        min_length=2,
        max_length=100,
        description="Nom de la ville (ex: Paris, Lyon, Marseille)"
    )

    @model_validator(mode='after')
    def validate_city_name(self):
        """Valide le nom de la ville"""
        # Nettoyer le nom de la ville
        self.city = self.city.strip()

        if not self.city:
            raise ValueError("Le nom de la ville ne peut pas être vide")

        # Vérifier les caractères autorisés (lettres, espaces, tirets, apostrophes, virgules)
        if not re.match(r"^[a-zA-ZÀ-ÿ\s\-'\.,-]+$", self.city):
            raise ValueError(
                "Nom de ville invalide. Utilisez uniquement des lettres, espaces, tirets, apostrophes et virgules"
            )

        return self


class WeatherAdapter(ToolAdapter):
    """Adaptateur pour les informations météorologiques"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.logger = logging.getLogger(__name__)

        # Configuration
        self.api_key = config.get('api_key') or ConfigManager().get_env_var('OPENWEATHERMAP_API_KEY')
        self.default_city = config.get('default_city', 'Paris')
        self.default_units = config.get('default_units', 'metric')
        self.default_language = config.get('default_language', 'fr')
        self.tool_name = config.get('tool_name', 'get_weather')
        self.tool_description = config.get('tool_description', 'Obtenir les informations météorologiques')

        # Mettre à jour le nom et la description depuis la config
        self.name = self.tool_name
        self.description = self.tool_description

        # URLs API OpenWeatherMap
        self.base_url = "https://api.openweathermap.org/data/2.5"
        self.geo_url = "https://api.openweathermap.org/geo/1.0"

        # Validation de la configuration
        if not self.api_key:
            self.logger.error("Clé API OpenWeatherMap manquante")

    async def initialize(self) -> bool:
        """Initialise l'adaptateur météo"""
        if not self.api_key:
            self.logger.error("Clé API OpenWeatherMap requise")
            return False


        try:
            # Test simple de la clé API avec une requête géocodage
            geo_url = f"{self.geo_url}/direct"
            geo_params = {
                'q': self.default_city,
                'limit': 1,
                'appid': self.api_key
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(geo_url, params=geo_params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        self.logger.info("Adaptateur météo initialisé avec succès")
                        return True
                    elif response.status == 401:
                        self.logger.error("Clé API OpenWeatherMap invalide")
                        return False
                    else:
                        self.logger.warning(f"Test API météo: statut {response.status}")
                        return True  # On continue même si le test échoue

        except Exception as e:
            self.logger.error(f"Erreur test API météo: {e}")
            return False

    def get_parameters_schema(self) -> Dict[str, Any]:
        """Retourne le schéma des paramètres pour la météo"""
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Nom de la ville"
                }
            },
            "required": ["city"]
        }

    def get_pydantic_schema(self):
        """Retourne le schéma Pydantic pour les paramètres de l'outil"""
        return WeatherParameters

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Exécute une requête météorologique"""
        if not self.api_key:
            return {
                "success": False,
                "error": "Clé API OpenWeatherMap non configurée"
            }
        self.logger.info(f"Exécution de l'adaptateur météo avec paramètres: {kwargs}")
        try:
            # Validation avec Pydantic
            params = WeatherParameters(**kwargs)

            self.logger.info(f"Requête météo pour la ville: {params.city}")
            return await self._get_weather_info(params.city)

        except Exception as e:
            self.logger.error(f"Erreur requête météo: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _get_weather_info(self, city: str) -> Dict[str, Any]:
        """Récupère les informations météorologiques"""
        try:
            # Étape 1: Géocodage pour obtenir les coordonnées
            geo_coords = await self._get_city_coordinates(city)
            if not geo_coords:
                return {"success": False, "error": f"Ville '{city}' non trouvée"}
            self.logger.info(f"Coordonnées trouvées pour {city}: {geo_coords}")

            # Étape 2: Récupération des données météo avec les coordonnées
            lat, lon = geo_coords
            weather_url = f"{self.base_url}/weather"
            weather_params = {
                'lat': lat,
                'lon': lon,
                'appid': self.api_key,
                'units': self.default_units,
                'lang': self.default_language
            }

            self.logger.info(f"Requête météo pour {city} (lat={lat}, lon={lon})")

            # Requête API asynchrone
            async with aiohttp.ClientSession() as session:
                async with session.get(weather_url, params=weather_params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return await self._format_weather_response(data, city)
                    elif response.status == 401:
                        return {"success": False, "error": "Clé API OpenWeatherMap invalide"}
                    else:
                        error_text = await response.text()
                        return {"success": False, "error": f"Erreur API météo (statut {response.status}): {error_text}"}

        except Exception as e:
            self.logger.error(f"Erreur récupération météo: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _get_city_coordinates(self, city: str) -> tuple[float, float] | None:
        """Récupère les coordonnées d'une ville via l'API Geocoding"""
        try:
            self.logger.info(f"Géocodage pour la ville: {city}")
            geo_url = f"{self.geo_url}/direct"
            geo_params = {
                'q': city,
                'limit': 1,
                'appid': self.api_key
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(geo_url, params=geo_params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and len(data) > 0:
                            location = data[0]
                            return (location['lat'], location['lon'])
                        else:
                            return None
                    else:
                        self.logger.error(f"Erreur géocodage: statut {response.status}")
                        return None

        except Exception as e:
            self.logger.error(f"Erreur géocodage pour {city}: {e}")
            return None

    async def _format_weather_response(self, data: Dict[str, Any], city: str) -> Dict[str, Any]:
        """Formate la réponse météorologique"""
        try:
            city = data['name']
            country = data['sys']['country']
            temperature = round(data['main']['temp'])
            feels_like = round(data['main']['feels_like'])
            humidity = data['main']['humidity']
            pressure = data['main']['pressure']
            description = data['weather'][0]['description'].capitalize()
            wind_speed = data.get('wind', {}).get('speed', 0)

            # Détection de l'ensoleillement
            icon = data['weather'][0]['icon']
            is_sunny = 'd' in icon and ('01' in icon or '02' in icon)  # Clear sky ou few clouds pendant la journée
            sunshine = "Oui" if is_sunny else "Non"

            # Format simple selon la configuration par défaut (metric)
            temp_unit = "°C"
            wind_unit = "m/s"

            # Format simple
            message = f"Météo à {city}\nTempérature : {temperature}{temp_unit}\nHumidité : {humidity}%\nEnsoleillement : {sunshine}"

            return {
                "success": True,
                "message": message,
                "data": {
                    "city": city,
                    "country": country,
                    "temperature": temperature,
                    "feels_like": feels_like,
                    "humidity": humidity,
                    "pressure": pressure,
                    "description": description,
                    "wind_speed": wind_speed,
                    "sunshine": sunshine,
                    "units": temp_unit,
                    "icon": icon
                }
            }

        except KeyError as e:
            return {
                "success": False,
                "error": f"Données météo incomplètes: {e}"
            }

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        self.logger.info("Adaptateur météo nettoyé")