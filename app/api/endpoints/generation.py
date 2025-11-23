from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
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
    
    success, error_message, url_or_path = await run_in_threadpool(
        image_service.generate_image,
        request_data.prompt,
        request_data.category,  # <-- ¡AÑADIDO!
        request_data.deck,
        request_data.index,
        request_data.def_index,
        request_data.force_generation
    )
    
    if success:
        # Extraer el nombre del archivo y construir la ruta relativa
        # URL GCS: https://storage.googleapis.com/bucket/card_images/category/deck/file.jpg
        # Ruta relativa esperada: /card_images/category/deck/file.jpg
        
        filename = url_or_path.split("/")[-1]
        
        # Encontrar la parte de la ruta que empieza con card_images
        # Esto asume que la URL de GCS contiene el prefijo configurado
        try:
            relative_path = url_or_path.split(f"/{settings.GCS_IMAGES_PREFIX}/")[1]
            web_path = f"/{settings.GCS_IMAGES_PREFIX}/{relative_path}"
        except IndexError:
            # Fallback si la estructura de URL no es la esperada
            web_path = url_or_path

        return JSONResponse({
            "success": True, 
            "filename": filename,
            "path": web_path # Retornamos ruta relativa para que el frontend use el redirect
        })
    else:
        if "omitida" in error_message:
            # Intentamos reconstruir el nombre esperado para el error 404
            expected_filename = f"{request_data.deck.replace('.json', '')}_card_{request_data.index}_def{request_data.def_index}.jpg"
            
            return JSONResponse(
                content={
                    "success": False,
                    "message": error_message,
                    "filename_expected": expected_filename
                },
                status_code=404
            )
        raise HTTPException(status_code=500, detail=error_message)

# --------------------------------------------------------------------
# 🗑️ ELIMINACIÓN DE IMÁGENES
# --------------------------------------------------------------------
@router.delete('/delete-image')
async def delete_image_api(request_data: ImageDeleteRequest):
    """Elimina la imagen asociada a una tarjeta."""
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
async def synthesize_speech_api(request: Request, request_data: SynthesizeRequest):
    """
    Genera (o reutiliza) un archivo de voz TTS desde el texto enviado.
    Ahora retorna la URL pública de GCS en lugar de servir el archivo directamente.
    """
    success, url_or_path, error_message = await audio_service.synthesize_speech_file(
        category=request_data.category,
        deck_name=request_data.deck, 
        text=request_data.text,
        voice_name=request_data.voice_name,
        model_name=request_data.model_name,
        tone=request_data.tone,
        verb_name=request_data.verb_name
    )

    if success and url_or_path:
        # Retornar la URL del proxy local en lugar de la URL directa de GCS
        # URL GCS: https://storage.googleapis.com/bucket/card_audio/category/deck/file.mp3
        # Proxy URL: http://localhost:8000/card_audio/category/deck/file.mp3
        
        try:
            # Intentar extraer la parte relativa después de 'card_audio'
            if f"/{settings.GCS_AUDIO_PREFIX}/" in url_or_path:
                relative_path = url_or_path.split(f"/{settings.GCS_AUDIO_PREFIX}/")[1]
                # Construir URL absoluta usando la request actual
                # request.base_url devuelve ej: http://localhost:8000/
                proxy_url = f"{request.base_url}{settings.GCS_AUDIO_PREFIX}/{relative_path}"
            else:
                # Si no coincide el formato esperado, devolver tal cual (fallback)
                proxy_url = url_or_path
        except Exception:
            proxy_url = url_or_path

        return JSONResponse({
            "success": True,
            "audio_url": proxy_url
        })
    
    print(f"❌ Synthesize Speech Error: {error_message}")
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
    """Sube y guarda una imagen en GCS para una tarjeta específica."""
    
    # 1. Leer el contenido del archivo subido
    try:
        file_content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo leer el archivo: {e}")

    # 2. Llamar al servicio de subida (que también actualiza el JSON)
    success, error_message, url_or_path = await run_in_threadpool(
        image_service.upload_image,
        category,
        deck,
        card_index,
        def_index,
        file_content,
        Path(file.filename).suffix.lower()
    )
    
    if success:
        # Construir ruta relativa
        filename = url_or_path.split("/")[-1]
        
        try:
            relative_path = url_or_path.split(f"/{settings.GCS_IMAGES_PREFIX}/")[1]
            web_path = f"/{settings.GCS_IMAGES_PREFIX}/{relative_path}"
        except IndexError:
            web_path = url_or_path
        
        return JSONResponse({
            "success": True, 
            "filename": filename,
            "path": web_path
        })
    else:
        # Si falla la subida, se devuelve 500
        raise HTTPException(status_code=500, detail=error_message)
