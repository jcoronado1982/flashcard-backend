import os
import hashlib
import logging
import re
from typing import Optional, Tuple
from starlette.concurrency import run_in_threadpool
from google.cloud import texttospeech
from google.api_core.exceptions import InvalidArgument

# Importaciones reales
from app.core.config import settings, tts_client
from app.services.gcs_helper import GCSHelper


# ============================================================
# --- FUNCIONES AUXILIARES ---
# ============================================================

# --- ¡REFACTORIZADA PARA GCS! ---
def _get_audio_blob_prefix(category: str, deck_name: str) -> str:
    """Retorna el prefijo del blob en GCS para los archivos de audio de un deck."""
    folder_name = deck_name.replace(".json", "")
    return f"{settings.GCS_AUDIO_PREFIX}/{category}/{folder_name}"


def _to_safe_filename(text: str) -> str:
    """Limpia una cadena para que sea segura en un nombre de archivo."""
    safe_text = text.lower()
    safe_text = re.sub(r"[^a-z0-9\s-]", "", safe_text)
    safe_text = re.sub(r"[\s-]+", "_", safe_text)
    return safe_text[:50].strip('_')


# --- ¡REFACTORIZADA PARA GCS! ---
def get_audio_blob_path(category: str, deck_name: str, filename: str) -> str:
    """Construye la ruta completa del blob en GCS para un archivo de audio."""
    prefix = _get_audio_blob_prefix(category, deck_name)
    return f"{prefix}/{filename}"


# ============================================================
# --- FUNCIÓN PRINCIPAL ---
# ============================================================

# --- ¡REFACTORIZADA PARA GCS! ---
async def synthesize_speech_file(
    category: str,
    deck_name: str,
    text: str,
    voice_name: str,
    model_name: Optional[str],
    tone: str,
    verb_name: str,
) -> Tuple[bool, str | None, str]:
    """
    Genera (o reutiliza) un archivo de audio para la frase indicada y lo sube a GCS.
    Retorna (success, blob_path_or_url, error_message)
    """
    gcs = GCSHelper()
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
    
    # Ruta del blob en GCS
    blob_path_current = get_audio_blob_path(category, deck_name, new_filename)
    blob_prefix = _get_audio_blob_prefix(category, deck_name)

    # ============================================================
    # --- VALIDACIÓN: EXISTE AUDIO DE LA MISMA FRASE EN GCS ---
    # ============================================================
    pattern = f"{deck_prefix}_{safe_verb_name}_{safe_text}_"
    
    # Listar blobs con el prefijo del deck
    existing_blobs = gcs.list_blobs_with_prefix(blob_prefix, extension=".mp3")
    
    # Filtrar por el patrón de la frase específica
    matching_blobs = [blob for blob in existing_blobs if pattern in blob]

    if matching_blobs:
        # Tomamos el primer archivo encontrado (en GCS no tenemos timestamps fáciles)
        latest_blob = matching_blobs[0]
        filename = latest_blob.split("/")[-1]

        # Extraer el tono actual del archivo existente
        match = re.search(rf"{deck_prefix}_{safe_verb_name}_{safe_text}_(.+?)_[0-9a-f]+\.mp3$", filename)
        tone_from_filename = match.group(1).replace("_", " ") if match else "default"

        logging.info(f"🎧 Audio existente encontrado en GCS: {filename} (tono: {tone_from_filename})")

        # Comparar tono actual con el nuevo
        if tone_from_filename.lower() == tone_prefix.replace("_", " ").lower():
            logging.info(f"🔁 Misma frase y mismo tono — reutilizando audio existente.")
            return True, gcs.get_public_url(latest_blob), ""
        else:
            logging.info(f"⚠️ Misma frase pero tono distinto ('{tone_from_filename}' → '{tone_prefix}') — regenerando.")
            gcs.delete_blob(latest_blob)
            logging.info(f"🗑️ Eliminado audio anterior de GCS: {filename}")

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

        # Subir audio directamente a GCS
        success = gcs.upload_blob_from_bytes(
            blob_path_current, 
            response.audio_content, 
            content_type="audio/mpeg"
        )
        
        if success:
            logging.info(f"✅ Audio creado y subido a GCS: {new_filename}")
            return True, gcs.get_public_url(blob_path_current), ""
        else:
            return False, None, "Error al subir audio a GCS."

    except InvalidArgument as e:
        logging.error(f"❌ Error 400 en TTS: {e}")
        return False, None, f"Error 400: Parámetros de voz/modelo inválidos. Detalle: {e}"

    except Exception as e:
        logging.error(f"❌ Error general al generar audio: {e}")
        return False, None, f"Error de síntesis de voz: {e}"
