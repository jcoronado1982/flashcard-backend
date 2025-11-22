# Archivo: app/api/api.py
from fastapi import APIRouter

from app.api.endpoints import decks, generation

api_router = APIRouter()

# Incluimos las rutas de los endpoints
api_router.include_router(decks.router, tags=["Decks"])
api_router.include_router(generation.router, tags=["Generation"])