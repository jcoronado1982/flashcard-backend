import os
import hashlib
import logging
import re
from typing import Optional, Tuple
from pathlib import Path
from starlette.concurrency import run_in_threadpool
from google.cloud import texttospeech
from google.api_core.exceptions import InvalidArgument

# Importaciones reales
from app.core.config import settings, tts_client


# ============================================================
# --- FUNCIONES AUXILIARES ---
# ============================================================

# --- ¡MODIFICADA! ---
def _get_audio_dir_for_deck(category: str, deck_name: str) -> Path:
    """Retorna la ruta al directorio de audio para un deck y asegura que exista."""
    folder_name = deck_name.replace(".json", "")
    
    # Crea la ruta incluyendo la categoría
    deck_audio_dir = settings.BASE_DIR / settings.AUDIO_DIR / category / folder_name
    
    os.makedirs(deck_audio_dir, exist_ok=True)
    return deck_audio_dir


def _to_safe_filename(text: str) -> str:
    """Limpia una cadena para que sea segura en un nombre de archivo."""
    safe_text = text.lower()
    safe_text = re.sub(r"[^a-z0-9\s-]", "", safe_text)
    safe_text = re.sub(r"[\s-]+", "_", safe_text)
    return safe_text[:50].strip('_')


# --- ¡MODIFICADA! ---
def get_audio_filepath(category: str, deck_name: str, filename: str) -> Path:
    """Construye la ruta completa para un archivo de audio usando el nombre de archivo final."""
    # Pasa la categoría a la función helper
    audio_dir = _get_audio_dir_for_deck(category, deck_name)
    return audio_dir / filename


# ============================================================
# --- FUNCIÓN PRINCIPAL ---
# ============================================================

# --- ¡MODIFICADA! ---
async def synthesize_speech_file(
    category: str,  # <-- ¡AÑADIDO!
    deck_name: str,
    text: str,
    voice_name: str,
    model_name: Optional[str],
    tone: str,
    verb_name: str,
) -> Tuple[bool, Path | None, str]:
    """
    Genera (o reutiliza) un archivo de audio para la frase indicada.
    """
    original_text = text.strip()

    # 1️⃣ Preparar texto para el modelo TTS
    tone_instruction = tone.strip()
    if tone_instruction and tone_instruction.lower() != "default":
        text_to_synthesize = f"{tone_instruction}: {original_text}"
    else:
        text_to_synthesize = original_text
        tone_instruction = "default"

    # 2️⃣ Crear identificadores y hash
    deck_prefix = deck_name.replace(".json", "")
    tone_prefix = _to_safe_filename(tone_instruction)
    safe_verb_name = _to_safe_filename(verb_name)
    safe_text = _to_safe_filename(original_text)

    # 🔑 Hash único por texto + voz + modelo
    hash_base_string = f"{original_text}|{voice_name}|{model_name or 'default_model'}"
    unique_key_cache = hash_base_string.strip().lower()
    current_hash = hashlib.sha256(unique_key_cache.encode("utf-8")).hexdigest()[:10]

    # Nombre del archivo final
    new_filename = f"{deck_prefix}_{safe_verb_name}_{safe_text}_{tone_prefix}_{current_hash}.mp3"
    
    # --- ¡MODIFICADO! ---
    # Pasa la categoría a las funciones helper
    filepath_current = get_audio_filepath(category, deck_name, new_filename)
    deck_dir = _get_audio_dir_for_deck(category, deck_name)
    # --- FIN MODIFICACIÓN ---


    # ============================================================
    # --- VALIDACIÓN: EXISTE AUDIO DE LA MISMA FRASE ---
    # ============================================================
    pattern = f"{deck_prefix}_{safe_verb_name}_{safe_text}_*.mp3"
    existing_files = list(deck_dir.glob(pattern))

    if existing_files:
        # Tomamos el archivo más reciente (último generado)
        latest_file = max(existing_files, key=lambda f: f.stat().st_mtime)
        filename = latest_file.name

        # Extraer el tono actual del archivo existente
        match = re.search(rf"{deck_prefix}_{safe_verb_name}_{safe_text}_(.+?)_[0-9a-f]+\.mp3$", filename)
        tone_from_filename = match.group(1).replace("_", " ") if match else "default"

        logging.info(f"🎧 Audio existente encontrado: {filename} (tono: {tone_from_filename})")

        # Comparar tono actual con el nuevo
        if tone_from_filename.lower() == tone_prefix.replace("_", " ").lower():
            logging.info(f"🔁 Misma frase y mismo tono — reutilizando audio existente.")
            return True, latest_file, ""
        else:
            logging.info(f"⚠️ Misma frase pero tono distinto ('{tone_from_filename}' → '{tone_prefix}') — regenerando.")
            try:
                os.remove(latest_file)
                logging.info(f"🗑️ Eliminado audio anterior: {latest_file.name}")
            except OSError as e:
                logging.warning(f"No se pudo eliminar el archivo anterior: {e}")

    # ============================================================
    # --- GENERACIÓN NUEVA ---
    # ============================================================

    if not tts_client:
        logging.error("❌ Cliente Text-to-Speech no inicializado.")
        return False, None, "Cliente TTS no disponible."

    logging.info(f"🎤 Generando nuevo audio: {new_filename}")

    try:
        synthesis_input = texttospeech.SynthesisInput(text=text_to_synthesize)
        voice_params = {"language_code": "en-US", "name": voice_name}
        if model_name:
            voice_params["model_name"] = model_name

        voice = texttospeech.VoiceSelectionParams(**voice_params)
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=0.9
        )

        response = await run_in_threadpool(
            tts_client.synthesize_speech,
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        with open(filepath_current, "wb") as out:
            out.write(response.audio_content)

        logging.info(f"✅ Audio creado: {filepath_current.name}")
        return True, filepath_current, ""

    except InvalidArgument as e:
        logging.error(f"❌ Error 400 en TTS: {e}")
        if filepath_current.exists():
            os.remove(filepath_current)
        return False, None, f"Error 400: Parámetros de voz/modelo inválidos. Detalle: {e}"

    except Exception as e:
        logging.error(f"❌ Error general al generar audio: {e}")
        if filepath_current.exists():
            os.remove(filepath_current)
        return False, None, f"Error de síntesis de voz: {e}"
