import json
import logging
from typing import List, Dict, Any

# Importamos la configuración central y el helper de GCS
from app.core.config import settings
from app.services.gcs_helper import GCSHelper

# --- ¡FUNCIÓN REFACTORIZADA PARA GCS! ---
def list_categories() -> List[str]:
    """Lista todas las categorías (carpetas virtuales) desde GCS, priorizando 'phrasal_verbs'."""
    gcs = GCSHelper()
    
    # Obtener los prefijos (directorios virtuales) desde GCS
    prefixes = gcs.list_virtual_directories(f"{settings.GCS_JSON_PREFIX}/")
    
    if not prefixes:
        logging.warning("No se encontraron categorías en GCS")
        return []
    
    # Extraer nombres de categorías de los prefijos
    # Ejemplo: "data/json/phrasal_verbs/" -> "phrasal_verbs"
    categories = [
        prefix.replace(f"{settings.GCS_JSON_PREFIX}/", "").rstrip("/")
        for prefix in prefixes
    ]
    
    # Ordenarlas alfabéticamente para un orden base predecible
    categories.sort()
    
    # Mover 'phrasal_verbs' al inicio de la lista si existe
    preferred_category = "phrasal_verbs"
    if preferred_category in categories:
        categories.remove(preferred_category)
        categories.insert(0, preferred_category)
        
    logging.info(f"Categorías encontradas en GCS: {categories}")
    return categories

# --- ¡REFACTORIZADA PARA GCS! ---
def _get_deck_blob_path(category: str, deck_name: str) -> str:
    """Retorna la ruta del blob en GCS para un deck específico DENTRO de una categoría."""
    filename = deck_name if deck_name.endswith(".json") else f"{deck_name}.json"
    
    # Construye la ruta del blob en GCS
    blob_path = f"{settings.GCS_JSON_PREFIX}/{category}/{filename}"
    
    # Verificar que existe en GCS
    gcs = GCSHelper()
    if not gcs.blob_exists(blob_path):
        logging.warning(f"Blob de deck no encontrado en GCS: {blob_path}")
        raise FileNotFoundError(f"El archivo del deck '{filename}' no existe en la categoría '{category}'.")
    
    return blob_path

# --- ¡REFACTORIZADA PARA GCS! ---
def list_decks(category: str) -> List[str]:
    """Lista todos los archivos JSON de decks disponibles DENTRO de una categoría desde GCS."""
    gcs = GCSHelper()
    prefix = f"{settings.GCS_JSON_PREFIX}/{category}/"
    
    # Listar todos los blobs con ese prefijo y extensión .json
    blob_names = gcs.list_blobs_with_prefix(prefix, extension=".json")
    
    if not blob_names:
        logging.warning(f"Categoría no encontrada o vacía en GCS: {category}")
        raise FileNotFoundError(f"La categoría '{category}' no existe o está vacía.")
    
    # Extraer solo el nombre del archivo (sin la ruta completa)
    decks = [blob.split("/")[-1] for blob in blob_names]
    
    logging.info(f"Decks encontrados en GCS para '{category}': {len(decks)}")
    return decks

# --- ¡REFACTORIZADA PARA GCS! ---
def get_deck_data(category: str, deck_name: str) -> List[Dict[str, Any]]:
    """Lee y retorna todos los datos de un deck específico desde GCS."""
    blob_path = _get_deck_blob_path(category, deck_name)
    gcs = GCSHelper()
    
    try:
        json_content = gcs.download_blob_as_string(blob_path)
        return json.loads(json_content)
    except json.JSONDecodeError:
        logging.error(f"Error al decodificar JSON desde GCS: {blob_path}")
        raise ValueError(f"No se pudo leer el archivo '{deck_name}.json'.")
    except Exception as e:
        logging.error(f"Error al cargar deck desde GCS: {e}")
        raise

# --- ¡REFACTORIZADA PARA GCS! ---
def update_card_status(category: str, deck_name: str, index: int, learned: bool):
    """Actualiza el estado 'learned' de una tarjeta por índice en un deck en GCS."""
    blob_path = _get_deck_blob_path(category, deck_name)
    
    try:
        data = get_deck_data(category, deck_name)
    except (FileNotFoundError, ValueError) as e:
        logging.error(f"No se pudo cargar {category}/{deck_name} para actualizar: {e}")
        raise
        
    if 0 <= index < len(data):
        data[index]['learned'] = learned
    else:
        raise IndexError("Índice fuera de rango.")
    
    # Subir datos actualizados a GCS
    gcs = GCSHelper()
    json_content = json.dumps(data, indent=4, ensure_ascii=False)
    success = gcs.upload_blob_from_string(blob_path, json_content, content_type="application/json")
    
    if not success:
        raise Exception(f"Error al actualizar el deck en GCS: {blob_path}")

# --- ¡REFACTORIZADA PARA GCS! ---
def reset_deck_status(category: str, deck_name: str):
    """Marca todas las tarjetas como 'not learned' para un deck en GCS."""
    blob_path = _get_deck_blob_path(category, deck_name)
    
    try:
        data = get_deck_data(category, deck_name)
    except (FileNotFoundError, ValueError) as e:
        logging.error(f"No se pudo cargar {category}/{deck_name} para resetear: {e}")
        raise

    for card in data:
        card['learned'] = False
        # Resetea también el imagePath en *todas las definiciones*
        if 'definitions' in card and isinstance(card['definitions'], list):
            for i in range(len(card['definitions'])):
                if card['definitions'][i].get('imagePath') is not None:
                        card['definitions'][i]['imagePath'] = None 
            
    # Subir datos reseteados a GCS
    gcs = GCSHelper()
    json_content = json.dumps(data, indent=4, ensure_ascii=False)
    success = gcs.upload_blob_from_string(blob_path, json_content, content_type="application/json")
    
    if not success:
        raise Exception(f"Error al resetear el deck en GCS: {blob_path}")

# --- ¡REFACTORIZADA PARA GCS! ---
def update_image_path_in_card(category: str, deck_name: str, index: int, def_index: int, image_path: str | None):
    """
    Actualiza el 'imagePath' de una definición específica dentro de una tarjeta en el deck en GCS.
    Si image_path es None, borra la ruta.
    """
    blob_path = _get_deck_blob_path(category, deck_name)
    
    try:
        data = get_deck_data(category, deck_name)
    except (FileNotFoundError, ValueError) as e:
        logging.error(f"No se pudo cargar {category}/{deck_name} para actualizar imagen: {e}")
        raise
        
    # Verificar que el índice de la tarjeta esté dentro de los límites
    if 0 <= index < len(data):
        card = data[index]
        if 'definitions' in card and isinstance(card['definitions'], list):
            defs = card['definitions']
            # Verificar que el índice de la definición esté dentro de los límites
            if 0 <= def_index < len(defs):
                defs[def_index]['imagePath'] = image_path
            else:
                raise IndexError(f"Índice de definición ({def_index}) fuera de rango.")
        else:
            raise ValueError(f"La tarjeta en el índice {index} no tiene una lista de 'definitions'.")
    else:
        raise IndexError(f"Índice de tarjeta ({index}) fuera de rango.")
    
    # Subir datos actualizados a GCS
    gcs = GCSHelper()
    json_content = json.dumps(data, indent=4, ensure_ascii=False)
    success = gcs.upload_blob_from_string(blob_path, json_content, content_type="application/json")
    
    if not success:
        raise Exception(f"Error al actualizar imagen en deck en GCS: {blob_path}")


# --- (SIN CAMBIOS) ---
# Esta función es independiente y se queda como está.
def get_phonics_data() -> List[Dict[str, Any]]:
    """
    Carga y retorna el archivo JSON de fonética (phonics.json)
    desde su carpeta personalizada (static/phonics_audio/).
    """
    
    # 1. Construimos la ruta personalizada
    # (settings.BASE_DIR / 'static' / 'phonics_audio' / 'phonics.json')
    phonics_path = settings.BASE_DIR / settings.STATIC_DIR / "phonics_audio" / "phonics.json"
    
    # 2. Verificamos que exista en esa ruta
    if not phonics_path.exists():
        logging.error(f"¡Archivo de fonética no encontrado en la ruta personalizada: {phonics_path}!")
        raise FileNotFoundError(f"El archivo phonics.json no fue encontrado en {phonics_path}")
    
    # 3. Lo leemos y devolvemos
    try:
        with open(phonics_path, "r", encoding="utf-8") as f:
            logging.info(f"Cargando {phonics_path} ...")
            return json.load(f)
    except json.JSONDecodeError as e:
        logging.error(f"Error al leer o parsear phonics.json: {e}")
        raise ValueError("Error al procesar el archivo de fonética.")
