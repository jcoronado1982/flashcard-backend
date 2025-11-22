import json
import logging
from typing import List, Dict, Any
from pathlib import Path

# Importamos la configuración central
from app.core.config import settings

# --- ¡FUNCIÓN MODIFICADA! ---
def list_categories() -> List[str]:
    """Lista todas las subcarpetas (categorías) en el directorio JSON, priorizando 'phrasal_verbs'."""
    if not settings.JSON_DIR_PATH.exists():
        return []
    
    # 1. Obtener todas las categorías (carpetas)
    categories = [p.name for p in settings.JSON_DIR_PATH.iterdir() if p.is_dir()]
    
    # 2. Ordenarlas alfabéticamente para un orden base predecible
    categories.sort()
    
    # 3. Mover 'phrasal_verbs' al inicio de la lista si existe
    preferred_category = "phrasal_verbs"
    if preferred_category in categories:
        categories.remove(preferred_category)
        categories.insert(0, preferred_category)
        
    logging.info(f"Categorías ordenadas: {categories}")
    return categories

# --- ¡MODIFICADA! ---
def _get_deck_path(category: str, deck_name: str) -> Path:
    """Retorna la ruta completa al archivo JSON de un deck específico DENTRO de una categoría."""
    filename = deck_name if deck_name.endswith(".json") else f"{deck_name}.json"
    
    # Construye la ruta usando la categoría
    path = settings.JSON_DIR_PATH / category / filename
    
    if not path.exists():
        logging.warning(f"Archivo de deck no encontrado en: {path}")
        raise FileNotFoundError(f"El archivo del deck '{filename}' no existe en la categoría '{category}'.")
    return path

# --- ¡MODIFICADA! ---
def list_decks(category: str) -> List[str]:
    """Lista todos los archivos JSON de decks disponibles DENTRO de una categoría."""
    category_path = settings.JSON_DIR_PATH / category
    
    if not category_path.exists() or not category_path.is_dir():
        logging.warning(f"Categoría no encontrada o no es un directorio: {category_path}")
        raise FileNotFoundError(f"La categoría '{category}' no existe.")
        
    # Lista los JSON dentro de la carpeta de la categoría
    decks = [p.name for p in category_path.glob("*.json")]
    logging.info(f"Decks encontrados en '{category}': {len(decks)}")
    return decks

# --- ¡MODIFICADA! ---
def get_deck_data(category: str, deck_name: str) -> List[Dict[str, Any]]:
    """Lee y retorna todos los datos de un deck específico."""
    # Pasa ambos parámetros al helper
    current_path = _get_deck_path(category, deck_name)
    try:
        with open(current_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        logging.error(f"Error al decodificar JSON en: {current_path}")
        raise ValueError(f"No se pudo leer el archivo '{deck_name}.json'.")

# --- ¡MODIFICADA! ---
def update_card_status(category: str, deck_name: str, index: int, learned: bool):
    """Actualiza el estado 'learned' de una tarjeta por índice en un deck."""
    # Pasa ambos parámetros
    current_path = _get_deck_path(category, deck_name)
    
    try:
        # Pasa ambos parámetros
        data = get_deck_data(category, deck_name)
    except (FileNotFoundError, ValueError) as e:
        logging.error(f"No se pudo cargar {category}/{deck_name} para actualizar: {e}")
        raise
        
    if 0 <= index < len(data):
        data[index]['learned'] = learned
    else:
        raise IndexError("Índice fuera de rango.")
    
    # Escribir datos
    with open(current_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- ¡MODIFICADA! ---
def reset_deck_status(category: str, deck_name: str):
    """Marca todas las tarjetas como 'not learned' para un deck."""
    # Pasa ambos parámetros
    current_path = _get_deck_path(category, deck_name)
    
    try:
        # Pasa ambos parámetros
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
            
    # Escribir datos
    with open(current_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- ¡FUNCIÓN NUEVA AÑADIDA! ---
def update_image_path_in_card(category: str, deck_name: str, index: int, def_index: int, image_path: str | None):
    """
    Actualiza el 'imagePath' de una definición específica dentro de una tarjeta en el deck.
    Si image_path es None, borra la ruta.
    """
    current_path = _get_deck_path(category, deck_name)
    
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
    
    # Escribir datos
    with open(current_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


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
