from fastapi import APIRouter, HTTPException, UploadFile, File, Form
import logging
from fastapi.responses import JSONResponse, FileResponse
from starlette.concurrency import run_in_threadpool
from pathlib import Path

# Importamos modelos y servicios
from app.models.flashcard import ImageGenerateRequest, ImageDeleteRequest, SynthesizeRequest
from app.services import image_service, audio_service
from app.core.config import settings

router = APIRouter()

# --------------------------------------------------------------------
# 📸 GENERACIÓN DE IMÁGENES
# --------------------------------------------------------------------
@router.post('/generate-image')
async def generate_image_api(request_data: ImageGenerateRequest):
    """Genera una imagen (o recupera una existente) para una tarjeta."""
    
    success, error_message, filepath = await run_in_threadpool(
        image_service.generate_image,
        request_data.prompt,
        request_data.category,  # <-- ¡AÑADIDO!
        request_data.deck,
        request_data.index,
        request_data.def_index,
        request_data.force_generation
    )
    
    try:
        # Intentamos calcular la ruta relativa para la web
        relative_path = filepath.relative_to(settings.BASE_DIR)
        web_path = f"/{relative_path.as_posix()}"
    except ValueError:
        # Si falla (ej. ruta inesperada), devolvemos un error claro
        logging.error(f"Error al calcular la ruta relativa para {filepath} desde {settings.BASE_DIR}")
        raise HTTPException(status_code=500, detail="Error al calcular la ruta del archivo.")

    
    if success:
        return JSONResponse({
            "success": True, 
            "filename": filepath.name,
            "path": web_path
        })
    else:
        if "omitida" in error_message:
            return JSONResponse(
                content={
                    "success": False,
                    "message": error_message,
                    "filename_expected": filepath.name,
                    "path_expected": web_path
                },
                status_code=404
            )
        raise HTTPException(status_code=500, detail=error_message)

# --------------------------------------------------------------------
# 🗑️ ELIMINACIÓN DE IMÁGENES
# --------------------------------------------------------------------
@router.delete('/delete-image')
async def delete_image_api(request_data: ImageDeleteRequest):
    """Elimina una imagen de una tarjeta si existe."""
    success, message = await run_in_threadpool(
        image_service.delete_image,
        request_data.category,  # <-- ¡AÑADIDO!
        request_data.deck,
        request_data.index,
        request_data.def_index
    )
    if success:
        return JSONResponse({"success": True, "message": message})
    else:
        raise HTTPException(status_code=500, detail=message)

# --------------------------------------------------------------------
# 🔊 SÍNTESIS DE VOZ (TTS)
# --------------------------------------------------------------------
@router.post("/synthesize-speech")
async def synthesize_speech_api(request_data: SynthesizeRequest):
    """
    Genera (o reutiliza) un archivo de voz TTS desde el texto enviado.
    """
    success, filepath, error_message = await audio_service.synthesize_speech_file(
        category=request_data.category,  # <-- ¡AÑADIDO!
        deck_name=request_data.deck, 
        text=request_data.text,
        voice_name=request_data.voice_name,
        model_name=request_data.model_name,
        tone=request_data.tone,
        verb_name=request_data.verb_name
    )

    if success and filepath and filepath.exists():
        return FileResponse(filepath, media_type="audio/mpeg", filename=filepath.name)
    
    status_code = 400 if "400" in error_message else 500
    raise HTTPException(status_code=status_code, detail=error_message)

@router.post('/upload-image')
async def upload_image_api(
    category: str = Form(...), 
    deck: str = Form(...), 
    card_index: int = Form(...),
    def_index: int = Form(...),
    file: UploadFile = File(...) # Archivo subido
):
    """Sube y guarda una imagen localmente para una tarjeta específica."""
    
    # 1. Leer el contenido del archivo subido
    try:
        file_content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo leer el archivo: {e}")

    # 2. Llamar al servicio de subida (que también actualiza el JSON)
    success, error_message, filepath = await run_in_threadpool(
        image_service.upload_image,
        category,
        deck,
        card_index,
        def_index,
        file_content,
        Path(file.filename).suffix.lower()
    )
    
    # 3. Calcular la ruta web relativa para el frontend
    try:
        relative_path = filepath.relative_to(settings.BASE_DIR)
        web_path = f"/{relative_path.as_posix()}"
    except ValueError:
        raise HTTPException(status_code=500, detail="Error al calcular la ruta del archivo.")

    
    if success:
        return JSONResponse({
            "success": True, 
            "filename": filepath.name,
            "path": web_path
        })
    else:
        # Si falla la subida, se devuelve 500
        raise HTTPException(status_code=500, detail=error_message)
