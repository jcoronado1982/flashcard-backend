# Archivo: app/core/config.py
import os
import sys
import logging
from pathlib import Path
from typing import Optional 
from pydantic_settings import BaseSettings

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# --- Carga de Configuración ---
class Settings(BaseSettings):
    # ID real del proyecto y Región correcta
    PROJECT_ID: str = "xrubi-fd22e" 
    REGION: str = "us-east1"  # <--- CORREGIDO AQUÍ
    
    # Credencial opcional para evitar errores en Cloud Run
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # GCS Configuration
    GCS_BUCKET_NAME: str = "theruby-assets"
    GCS_JSON_PREFIX: str = "json"
    GCS_IMAGES_PREFIX: str = "card_images"
    GCS_AUDIO_PREFIX: str = "card_audio"
    
    # Legacy local paths (kept for phonics data only)
    CARD_IMAGES_BASE_DIR: str = "card_images"
    AUDIO_DIR: str = "card_audio"
    STATIC_DIR: str = "static"
    JSON_SUB_DIR: str = "json"
    SERVER_TIMEOUT: int = 300
    
    # BASE_DIR es el directorio raíz
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    
    # --- Propiedades de Ruta Calculadas ---
    @property
    def JSON_DIR_PATH(self) -> Path:
        return self.BASE_DIR / self.STATIC_DIR / self.JSON_SUB_DIR

    @property
    def AUDIO_DIR_PATH(self) -> Path:
        return self.BASE_DIR / self.AUDIO_DIR

    @property
    def IMAGES_BASE_PATH(self) -> Path:
        return self.BASE_DIR / self.CARD_IMAGES_BASE_DIR

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        extra = "ignore" 

settings = Settings()

# --- Crear Directorios Locales (Solo para Phonics) ---
phonics_dir = settings.BASE_DIR / settings.STATIC_DIR / "phonics_audio"
os.makedirs(phonics_dir, exist_ok=True)
logging.info(f"Directorio de phonics asegurado en: {phonics_dir}")


# --- Inicialización de Clientes de Google ---
try:
    import vertexai
    from vertexai.preview.vision_models import ImageGenerationModel
    from google.cloud import texttospeech

    # Inicializamos con los valores seguros de settings
    vertexai.init(project=settings.PROJECT_ID, location=settings.REGION)
    ia_model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-002")
    tts_client = texttospeech.TextToSpeechClient()
    
    logging.info(f"✅ Vertex AI inicializado en proyecto: {settings.PROJECT_ID} ({settings.REGION})")
    logging.info("✅ Google Cloud Text-to-Speech inicializado.")

except ImportError as e:
    logging.critical(f"FATAL: Falta una o más librerías. {e}. Instala desde requirements.txt")
    sys.exit(1)
except Exception as e:
    logging.error(f"❌ Error al inicializar Google Cloud Services: {e}")
    ia_model = None
    tts_client = None