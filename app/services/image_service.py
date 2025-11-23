import os
import logging
from typing import Optional
from requests.exceptions import Timeout, ConnectionError
from app.core.config import settings, ia_model
from app.services.gcs_helper import GCSHelper
# --- ¡IMPORTACIÓN AÑADIDA! ---
from app.services import deck_service 


# --- ¡REFACTORIZADA PARA GCS! ---
def _get_image_blob_prefix(category: str, deck_name: str) -> str:
    """Retorna el prefijo del blob en GCS para las imágenes de un deck."""
    folder_name = deck_name.replace(".json", "")
    return f"{settings.GCS_IMAGES_PREFIX}/{category}/{folder_name}"

def _get_deck_prefix(deck_name: str) -> str:
    """Extrae el nombre base del deck/verbo."""
    return deck_name.replace(".json", "")

def get_image_blob_path(category: str, deck_name: str, card_index: int, def_index: int) -> str:
    """Construye la ruta completa del blob en GCS donde debería estar una imagen."""
    prefix = _get_image_blob_prefix(category, deck_name)
    deck_prefix = _get_deck_prefix(deck_name)
    # Importante: siempre usa .jpg como extensión final para estandarizar
    filename = f"{deck_prefix}_card_{card_index}_def{def_index}.jpg"
    return f"{prefix}/{filename}"

def find_existing_image_path(category: str, deck_name: str, card_index: int, def_index: int) -> Optional[str]:
    """Busca una imagen existente en GCS (jpg o jpeg)."""
    gcs = GCSHelper()
    prefix = _get_image_blob_prefix(category, deck_name)
    deck_prefix = _get_deck_prefix(deck_name)
    base_filename = f"{deck_prefix}_card_{card_index}_def{def_index}"
    
    # Verificar .jpg
    jpg_path = f"{prefix}/{base_filename}.jpg"
    if gcs.blob_exists(jpg_path):
        return jpg_path
    
    # Verificar .jpeg
    jpeg_path = f"{prefix}/{base_filename}.jpeg"
    if gcs.blob_exists(jpeg_path):
        return jpeg_path
    
    return None

def generate_image(prompt: str, category: str, deck_name: str, card_index: int, def_index: int, force_generation: bool) -> tuple[bool, str, str]:
    """
    Genera una imagen si es necesario y la sube a GCS.
    Retorna (success, error_message, blob_path_or_url)
    """
    gcs = GCSHelper()
    blob_path = get_image_blob_path(category, deck_name, card_index, def_index)
    existing_path = find_existing_image_path(category, deck_name, card_index, def_index)

    if existing_path:
        logging.info(f"✅ Imagen ya existe en GCS: {existing_path}")
        return True, "", gcs.get_public_url(existing_path)
    
    if not force_generation:
        return False, "Imagen no existe y la generación fue omitida (force_generation=False).", blob_path
        
    if not ia_model:
        return False, "Modelo de IA no disponible.", blob_path
        
    logging.info(f"🖼️ Generando imagen para GCS: '{prompt[:80]}...'")
    try:
        response = ia_model.generate_images(prompt=prompt, number_of_images=1, aspect_ratio="1:1")
        if not response.images:
            return False, "La API no devolvió ninguna imagen.", blob_path
        
        # Guardar la imagen en GCS directamente desde el buffer de memoria
        image_obj = response.images[0]
        # Convertir la imagen a bytes
        import io
        image_bytes = io.BytesIO()
        image_obj._pil_image.save(image_bytes, format='JPEG')
        image_bytes = image_bytes.getvalue()
        
        # Subir a GCS
        success = gcs.upload_blob_from_bytes(blob_path, image_bytes, content_type="image/jpeg")
        
        if success:
            logging.info(f"✅ Imagen generada y subida a GCS: {blob_path}")
            return True, "", gcs.get_public_url(blob_path)
        else:
            return False, "Error al subir imagen a GCS.", blob_path
            
    except (Timeout, ConnectionError):
        return False, "Tiempo de espera (Timeout) o error de conexión.", blob_path
    except Exception as e:
        return False, f"Error interno de la API de IA: {e}", blob_path

def delete_image(category: str, deck_name: str, card_index: int, def_index: int) -> tuple[bool, str]:
    """Elimina una imagen de GCS si existe."""
    gcs = GCSHelper()
    blob_path = find_existing_image_path(category, deck_name, card_index, def_index)
    
    if not blob_path:
        return True, "Imagen no encontrada en GCS."
    
    success = gcs.delete_blob(blob_path)
    if success:
        return True, "Imagen eliminada de GCS."
    else:
        return False, "Error al eliminar imagen de GCS."

# --- ¡REFACTORIZADA PARA GCS! ---
def upload_image(
    category: str, 
    deck_name: str, 
    card_index: int, 
    def_index: int, 
    file_content: bytes, 
    file_extension: str = '.jpg'
) -> tuple[bool, str, str]:
    """
    Guarda el contenido binario de una imagen subida en GCS.
    Retorna (success, error_message, blob_path_or_url)
    """
    gcs = GCSHelper()
    blob_path = get_image_blob_path(category, deck_name, card_index, def_index)
    
    # Si existe un archivo con otra extensión (como .jpeg), lo borramos primero.
    existing_path = find_existing_image_path(category, deck_name, card_index, def_index)
    if existing_path and existing_path != blob_path:
        gcs.delete_blob(existing_path)
        logging.info(f"Antigua imagen eliminada de GCS: {existing_path}")

    try:
        # Subir el archivo binario a GCS
        success = gcs.upload_blob_from_bytes(blob_path, file_content, content_type="image/jpeg")
        
        if not success:
            return False, "Error al subir imagen a GCS", blob_path
        
        logging.info(f"✅ Imagen subida a GCS: {blob_path}")
        
        # Actualizar el JSON con la URL pública de GCS
        public_url = gcs.get_public_url(blob_path)
        
        # Llama al servicio de deck para actualizar la tarjeta
        deck_service.update_image_path_in_card(category, deck_name, card_index, def_index, public_url)

        return True, "", public_url
        
    except Exception as e:
        error_msg = f"Error al guardar o actualizar JSON: {e}"
        logging.error(error_msg)
        return False, error_msg, blob_path