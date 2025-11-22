import os
import uvicorn
import logging
import json
import hashlib
import sys
from pathlib import Path
from typing import List, Optional

# Importaciones de Google Cloud
try:
    import vertexai
    from vertexai.preview.vision_models import ImageGenerationModel
    from google.cloud import texttospeech
except ImportError as e:
    print(f"FATAL: Falta una o más librerías. {e}. Instala: pip install google-cloud-aiplatform google-cloud-texttospeech pydantic")
    sys.exit(1)

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from requests.exceptions import Timeout, ConnectionError
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ----------------------------------------------------------------------
# --- CONFIGURACIÓN DE FASTAPI ---
# ----------------------------------------------------------------------
app = FastAPI()

# SOLUCIÓN CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------
# --- CONFIGURACIÓN DE RUTAS DE ARCHIVOS Y VERTEX AI ---
# ----------------------------------------------------------------------
PROJECT_ID = "xrubi-fd22e" # DEBE SER TU PROJECT ID REAL
REGION = "us-central1"
CARD_IMAGES_BASE_DIR = "card_images" # Directorio base fijo
IMAGE_DIR = "" # Directorio de imágenes dinámico (e.g., 'card_images/get')
AUDIO_DIR = "card_audio"
STATIC_DIR = "static"
JSON_SUB_DIR = "json"
SERVER_TIMEOUT = 300

# --- VARIABLES GLOBALES PARA GESTIÓN DE ARCHIVOS ---
FLASHCARDS_FILE_NAME = "get.json" 

BASE_DIR = Path(__file__).resolve().parent
JSON_DIR_PATH = BASE_DIR / STATIC_DIR / JSON_SUB_DIR

def get_current_flashcards_path() -> Path:
    """Retorna la ruta completa al archivo JSON de flashcards actualmente activo."""
    return JSON_DIR_PATH / FLASHCARDS_FILE_NAME

def _set_dynamic_image_dir(deck_name_base: str):
    """Establece IMAGE_DIR y asegura que el subdirectorio exista, basado en el nombre del deck."""
    global IMAGE_DIR
    global CARD_IMAGES_BASE_DIR
    
    # 1. Obtener el nombre de la carpeta (ej. 'get' de 'get.json')
    folder_name = deck_name_base.replace(".json", "")
    
    # 2. Construir la ruta completa del directorio de imágenes (e.g., 'card_images/get')
    new_image_dir = os.path.join(CARD_IMAGES_BASE_DIR, folder_name)
    
    # 3. Crear el directorio si no existe
    os.makedirs(new_image_dir, exist_ok=True)
    
    # 4. Actualizar la variable global
    IMAGE_DIR = new_image_dir
    logging.info(f"📁 Directorio de imágenes activo: {IMAGE_DIR}")

# Crear directorios fijos si no existen
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(JSON_DIR_PATH, exist_ok=True)
os.makedirs(CARD_IMAGES_BASE_DIR, exist_ok=True) # Asegura que el directorio padre exista

# Inicializar el directorio de imágenes dinámico para el archivo por defecto
_set_dynamic_image_dir(FLASHCARDS_FILE_NAME) # Inicializa IMAGE_DIR y crea la carpeta (e.g., card_images/get)

# Inicialización de clientes
ia_model = None
tts_client = None

try:
    vertexai.init(project=PROJECT_ID, location=REGION)
    ia_model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-002")
    logging.info("✅ Vertex AI (Imagen) inicializado.")
    
    tts_client = texttospeech.TextToSpeechClient()
    logging.info("✅ Google Cloud Text-to-Speech inicializado.")

except Exception as e:
    logging.error(f"❌ Error al inicializar Google Cloud Services: {e}")

# ----------------------------------------------------------------------
# --- MODELOS DE DATOS (PYDANTIC) ---
# ----------------------------------------------------------------------
class GenerateRequest(BaseModel):
    index: int = Field(..., description="Índice de la flashcard.")
    def_index: int = Field(0, description="Índice de la definición (0 por defecto).")
    prompt: str = Field(..., description="Prompt de texto para la generación de imagen.")
    force_generation: bool = Field(False, description="Si es 'False', solo se busca la imagen existente, no se genera.") # 👈 CAMBIO A FALSE

class DeleteRequest(BaseModel):
    index: int
    def_index: int = 0

class SynthesizeRequest(BaseModel):
    text: str = Field(..., description="Texto a sintetizar.")
    voice_name: str = Field("Aoede", description="Nombre de la voz TTS.")
    model_name: Optional[str] = Field("gemini-2.5-pro-tts", description="Nombre del modelo TTS.")
    deck: Optional[str] = Field(None, description="Nombre del deck actual, enviado por el frontend.")

class UpdateStatusRequest(BaseModel):
    index: int = Field(..., description="Índice de la tarjeta a actualizar.")
    learned: bool = Field(..., description="Nuevo estado de aprendizaje.")
    deck: Optional[str] = None # No se usa pero se mantiene por consistencia con el frontend

class ResetRequest(BaseModel):
    deck: str = Field(..., description="Nombre del deck a resetear.") # Modelo añadido para reset

# ----------------------------------------------------------------------
# --- LÓGICA DE GENERACIÓN DE IMAGENES Y SÍNTESIS DE VOZ ---
# ----------------------------------------------------------------------

def _get_deck_prefix() -> str:
    """Extrae el nombre base del deck/verbo del IMAGE_DIR actual."""
    return os.path.basename(IMAGE_DIR)

def find_existing_image_path(card_index: int, def_index: int) -> Optional[str]:
    # Construye el nombre del archivo con el prefijo del deck (ej. 'go_card_0_def0.jpg')
    prefix = _get_deck_prefix()
    base_filename = f"{prefix}_card_{card_index}_def{def_index}"
    
    jpg_path = os.path.join(IMAGE_DIR, f"{base_filename}.jpg")
    if os.path.exists(jpg_path):
        return jpg_path
    jpeg_path = os.path.join(IMAGE_DIR, f"{base_filename}.jpeg")
    if os.path.exists(jpeg_path):
        return jpeg_path
    return None

def get_image_filepath(card_index: int, def_index: int) -> str:
    # Construye el nombre del archivo con el prefijo del deck (ej. 'go_card_0_def0.jpg')
    prefix = _get_deck_prefix()
    filename = f"{prefix}_card_{card_index}_def{def_index}.jpg"
    
    return os.path.join(IMAGE_DIR, filename)

def generate_image_file(prompt: str, card_index: int, def_index: int, force_generation: bool) -> tuple[bool, str]:
    existing_path = find_existing_image_path(card_index, def_index)
    
    if existing_path:
        logging.info(f"✅ Imagen ya existe: {os.path.basename(existing_path)}")
        return True, "" 
    
    # LÓGICA DE CONTROL: Si la imagen NO existe y force_generation es False, salimos.
    if not force_generation:
        return False, "Imagen no existe y la generación fue omitida (force_generation=False)."
        
    filepath = get_image_filepath(card_index, def_index)
    if not ia_model:
        return False, "Modelo de IA no disponible."
        
    logging.info(f"🖼️ Generando imagen en '{IMAGE_DIR}' para: '{prompt[:80]}...'")
    try:
        response = ia_model.generate_images(prompt=prompt, number_of_images=1, aspect_ratio="1:1")
        if not response.images:
            return False, "La API no devolvió ninguna imagen."
        response.images[0].save(filepath)
        logging.info(f"✅ Generación completada: {os.path.basename(filepath)}")
        return True, ""
    except (Timeout, ConnectionError) as e:
        return False, "Tiempo de espera (Timeout) o error de conexión."
    except Exception as e:
        return False, f"Error interno de la API de IA: {e}"

def get_audio_filepath(text_hash: str) -> str:
    filename = f"{text_hash}.mp3"
    return os.path.join(AUDIO_DIR, filename)

async def synthesize_speech_file(text: str, voice_name: str, model_name: Optional[str]) -> tuple[bool, str, str]:
    original_text = text.strip()
    # Añadir un prefijo para mejor pronunciación si es una frase corta
    text_to_synthesize = f"The word is: {original_text}" if len(original_text.split()) <= 2 and len(original_text) <= 10 else original_text
    
    unique_key = f"{text_to_synthesize}|{voice_name}|{model_name or ''}"
    text_hash = hashlib.sha256(unique_key.encode("utf-8")).hexdigest()
    filepath = get_audio_filepath(text_hash)
    
    if os.path.exists(filepath):
        return True, filepath, ""
        
    if not tts_client:
        return False, "", "Cliente TTS no disponible."
        
    try:
        synthesis_input = texttospeech.SynthesisInput(text=text_to_synthesize)
        voice_params = {"language_code": "en-US", "name": voice_name}
        if model_name:
            voice_params["model_name"] = model_name
            
        voice = texttospeech.VoiceSelectionParams(**voice_params)
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3, speaking_rate=0.9)
        
        # Uso de run_in_threadpool para la llamada de Vertex AI TTS (operación de red bloqueante)
        response = await run_in_threadpool(tts_client.synthesize_speech, input=synthesis_input, voice=voice, audio_config=audio_config)
        
        with open(filepath, "wb") as out:
            out.write(response.audio_content)
            
        return True, filepath, ""
        
    except Exception as e:
        return False, "", f"Error de síntesis de voz: {e}."

# ----------------------------------------------------------------------
# --- FUNCIONES SINCRONAS DE GESTIÓN DE ARCHIVOS JSON ---
# ----------------------------------------------------------------------

def _list_available_json_files_sync() -> List[str]:
    """Lista todos los archivos JSON en el directorio de datos."""
    if not JSON_DIR_PATH.exists():
        return []
    # Retorna solo los nombres de los archivos .json
    return [p.name for p in JSON_DIR_PATH.glob("*.json")]

def _set_active_json_file_sync(filename: str):
    """Establece el nombre del archivo JSON activo y el directorio de imágenes correspondiente."""
    global FLASHCARDS_FILE_NAME
    # Permite pasar el nombre sin extensión, ya que se asume que proviene del deck parameter
    file_with_ext = filename if filename.endswith(".json") else f"{filename}.json" 
    full_path = JSON_DIR_PATH / file_with_ext
    
    if not full_path.exists():
        raise FileNotFoundError(f"El archivo '{file_with_ext}' no existe.")
        
    FLASHCARDS_FILE_NAME = file_with_ext
    _set_dynamic_image_dir(file_with_ext) # LLAMADA PARA CREAR Y ESTABLECER EL NUEVO DIRECTORIO
    logging.info(f"✅ Archivo JSON activo cambiado a: {FLASHCARDS_FILE_NAME}")

def _get_flashcards_data_sync():
    """Lee y retorna todos los datos del archivo JSON actualmente activo."""
    current_path = get_current_flashcards_path()
    
    if not current_path.exists():
        available_files = _list_available_json_files_sync()
        if not available_files:
            raise FileNotFoundError("Archivo de datos no encontrado y no hay JSONs disponibles.")
        
        global FLASHCARDS_FILE_NAME
        FLASHCARDS_FILE_NAME = available_files[0]
        current_path = get_current_flashcards_path()
        logging.warning(f"⚠️ Archivo principal '{current_path.name}' no encontrado. Usando: {FLASHCARDS_FILE_NAME}")
    
    with open(current_path, "r", encoding="utf-8") as f:
        return json.load(f)

def _update_card_status_sync(index: int, learned: bool):
    """Actualiza el estado 'learned' de una tarjeta por índice."""
    data = _get_flashcards_data_sync()
    if 0 <= index < len(data):
        data[index]['learned'] = learned
    else:
        raise IndexError("Índice fuera de rango.")
    
    with open(get_current_flashcards_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def _reset_all_statuses_sync():
    """Marca todas las tarjetas como 'not learned' para el archivo activo."""
    data = _get_flashcards_data_sync()
    for card in data:
        card['learned'] = False
        if 'imagePath' in card:
             card['imagePath'] = None 
             
    with open(get_current_flashcards_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# ----------------------------------------------------------------------
# --- ENDPOINTS ---
# ----------------------------------------------------------------------

# --- GESTIÓN DE ARCHIVOS JSON ---
@app.get("/api/available-flashcards-files")
async def get_available_flashcards_files():
    """
    Retorna la lista de todos los archivos JSON disponibles y el activo.
    """
    try:
        file_list = await run_in_threadpool(_list_available_json_files_sync)
        return JSONResponse({"success": True, "files": file_list, "active_file": FLASHCARDS_FILE_NAME})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudieron listar los archivos: {e}")


@app.get("/api/flashcards-data")
async def get_flashcards_data(deck: Optional[str] = Query(None)):
    """
    Retorna los datos de las tarjetas. Si se proporciona 'deck', cambia el archivo activo.
    """
    try:
        # 1. Cambiar el archivo activo si se proporciona el parámetro 'deck'
        if deck:
            await run_in_threadpool(_set_active_json_file_sync, deck)
            
        # 2. Cargar los datos del archivo ACTIVO
        data = await run_in_threadpool(_get_flashcards_data_sync)
        return JSONResponse(data)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Archivo de deck no encontrado: {deck}.json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudieron cargar los datos: {e}")

@app.post('/api/update-status')
async def update_card_status(request_data: UpdateStatusRequest):
    """
    Actualiza el estado de la tarjeta para el archivo activo.
    """
    try:
        await run_in_threadpool(_update_card_status_sync, request_data.index, request_data.learned)
        return JSONResponse({"success": True, "message": f"Tarjeta {request_data.index} actualizada."})
    except IndexError:
        raise HTTPException(status_code=404, detail="Índice fuera de rango.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar el estado: {e}")

@app.post("/api/reset-all")
async def reset_all_statuses(request_data: ResetRequest):
    """
    Resetea el estado de todas las tarjetas para el deck especificado.
    """
    try:
        # 1. Asegura que el archivo correcto esté activo y actualiza la carpeta de imágenes
        await run_in_threadpool(_set_active_json_file_sync, request_data.deck)
        
        # 2. Resetea el progreso
        await run_in_threadpool(_reset_all_statuses_sync)
        
        return JSONResponse({"success": True, "message": f"Todas las tarjetas en '{request_data.deck}' reseteadas."})
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Deck no encontrado para reset: {request_data.deck}.json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al resetear: {e}")

# --- GENERACIÓN DE CONTENIDO ---
@app.post('/api/generate-image')
async def generate_image_api(request_data: GenerateRequest):
    
    # 1. Calcular el nombre de archivo y subdirectorio ESPERADOS
    subdir = os.path.basename(IMAGE_DIR)
    expected_filepath = get_image_filepath(request_data.index, request_data.def_index)
    expected_filename = os.path.basename(expected_filepath)
    expected_path = f"/card_images/{subdir}/{expected_filename}"

    # 2. Llamar a la lógica de generación/búsqueda
    success, error_message = await run_in_threadpool(
        generate_image_file, 
        request_data.prompt, 
        request_data.index, 
        request_data.def_index, 
        request_data.force_generation
    )
    
    if success:
        # CASO A: Imagen encontrada o generada con éxito (200 OK)
        return JSONResponse({
            "success": True, 
            "filename": expected_filename, 
            "path": expected_path
        }) 
    else:
        # CASO B: Fallo o Imagen omitida (404/500)
        
        # Devuelve 404 si la imagen no existe y la generación fue omitida
        if "omitida" in error_message:
            # Retorna 404 pero incluye el nombre del archivo esperado en el cuerpo (para copia manual)
            return JSONResponse(
                content={
                    "success": False,
                    "message": error_message,
                    "filename_expected": expected_filename,
                    "path_expected": expected_path
                },
                status_code=404 # Código 404 indica que el recurso no fue encontrado
            )
        
        # Devuelve 500 para errores de generación o indisponibilidad del modelo
        raise HTTPException(status_code=500, detail=error_message)

@app.delete('/api/delete-image')
async def delete_image_api(request_data: DeleteRequest):
    path_to_delete = find_existing_image_path(request_data.index, request_data.def_index)
    if not path_to_delete:
        return JSONResponse({"success": True, "message": "Archivo no encontrado."})
    try:
        os.remove(path_to_delete)
        return JSONResponse({"success": True, "message": "Imagen eliminada."})
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar: {e}")

@app.post("/api/synthesize-speech")
async def synthesize_speech_api(request_data: SynthesizeRequest):
    success, filepath, error_message = await synthesize_speech_file(request_data.text, request_data.voice_name, request_data.model_name)
    if success:
        return FileResponse(filepath, media_type="audio/mpeg", filename=os.path.basename(filepath))
    else:
        raise HTTPException(status_code=500, detail=error_message)

# Montar directorios estáticos y servir HTML
app.mount(f"/{AUDIO_DIR}", StaticFiles(directory=AUDIO_DIR), name="audio")
# Monta la URL /card_images para servir el contenido del directorio base card_images
app.mount("/card_images", StaticFiles(directory=CARD_IMAGES_BASE_DIR), name="images") 
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def serve_html():
    html_path = BASE_DIR / STATIC_DIR / "flashcard_app.html"
    if html_path.exists():
        return FileResponse(html_path, media_type="text/html")
    else:
        raise HTTPException(status_code=404, detail="No se encuentra el archivo HTML principal.")

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000, timeout_keep_alive=SERVER_TIMEOUT)