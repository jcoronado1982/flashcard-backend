import logging
from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from typing import Optional, List

# Importamos los modelos y servicios
from app.models.flashcard import UpdateStatusRequest, ResetRequest
from app.services import deck_service

router = APIRouter()

# --- ¡NUEVO ENDPOINT! ---
@router.get("/categories")
async def get_categories():
    """Retorna la lista de todas las categorías (carpetas) disponibles."""
    try:
        categories = await run_in_threadpool(deck_service.list_categories)
        return JSONResponse({"success": True, "categories": categories})
    except Exception as e:
        logging.error(f"No se pudieron listar las categorías: {e}")
        raise HTTPException(status_code=500, detail=f"No se pudieron listar las categorías: {e}")

# --- ¡MODIFICADO! ---
@router.get("/available-flashcards-files")
async def get_available_flashcards_files(category: str = Query(...)):
    """Retorna la lista de todos los archivos JSON de decks disponibles PARA UNA CATEGORÍA."""
    try:
        # Llama al servicio modificado con la categoría
        file_list = await run_in_threadpool(deck_service.list_decks, category)
        
        default_deck = file_list[0] if file_list else ""
        
        return JSONResponse({"success": True, "files": file_list, "active_file": default_deck})
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Categoría no encontrada: {category}")
    except Exception as e:
        logging.error(f"No se pudieron listar los archivos para {category}: {e}")
        raise HTTPException(status_code=500, detail=f"No se pudieron listar los archivos: {e}")

# --- ¡MODIFICADO! ---
@router.get("/flashcards-data")
async def get_flashcards_data(category: str = Query(...), deck: str = Query(...)):
    """Retorna los datos del deck especificado DENTRO de una categoría."""
    try:
        # Llama al servicio modificado con ambos parámetros
        data = await run_in_threadpool(deck_service.get_deck_data, category, deck)
        return JSONResponse(data)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Archivo de deck no encontrado: {category}/{deck}")
    except Exception as e:
        logging.error(f"No se pudieron cargar los datos: {e}")
        raise HTTPException(status_code=500, detail=f"No se pudieron cargar los datos: {e}")

# --- ¡MODIFICADO! ---
@router.post('/update-status')
async def update_card_status(request_data: UpdateStatusRequest):
    """Actualiza el estado de la tarjeta para el deck especificado."""
    # (El modelo 'UpdateStatusRequest' AHORA ESTÁ INCORRECTO, lo arreglamos en el sig. paso)
    try:
        await run_in_threadpool(
            deck_service.update_card_status,
            request_data.category, # <-- ¡NUEVO!
            request_data.deck, 
            request_data.index, 
            request_data.learned
        )
        return JSONResponse({"success": True, "message": f"Tarjeta {request_data.index} actualizada."})
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Deck no encontrado: {request_data.category}/{request_data.deck}")
    except IndexError:
        raise HTTPException(status_code=404, detail="Índice fuera de rango.")
    except Exception as e:
        logging.error(f"Error al actualizar estado para {request_data.deck}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar el estado: {e}")

# --- ¡MODIFICADO! ---
@router.post("/reset-all")
async def reset_all_statuses(request_data: ResetRequest):
    """Resetea el estado de todas las tarjetas para el deck especificado."""
    # (El modelo 'ResetRequest' AHORA ESTÁ INCORRECTO, lo arreglamos en el sig. paso)
    try:
        await run_in_threadpool(
            deck_service.reset_deck_status, 
            request_data.category, # <-- ¡NUEVO!
            request_data.deck
        )
        return JSONResponse({"success": True, "message": f"Todas las tarjetas en '{request_data.deck}' reseteadas."})
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Deck no encontrado para reset: {request_data.category}/{request_data.deck}")
    except Exception as e:
        logging.error(f"Error al resetear deck {request_data.deck}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al resetear: {e}")

# --- (SIN CAMBIOS) ---
@router.get("/phonics-data")
async def get_phonics_data():
    """
    Retorna los datos de fonética desde static/json/phonics.json.
    """
    try:
        data = await run_in_threadpool(deck_service.get_phonics_data)
        return JSONResponse(content=data)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logging.error(f"Error interno al leer archivo de fonética: {e}")
        raise HTTPException(status_code=500, detail="Error interno al leer archivo de fonética.")
