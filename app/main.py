# Archivo: app/main.py
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Importamos la configuración y el router principal
from app.core.config import settings
from app.api.api import api_router

app = FastAPI(title="Flashcard AI API")

# --- Middlewares (CORS) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Montar Rutas de la API ---
# Todas las rutas de 'api_router' ahora tendrán el prefijo /api
app.include_router(api_router, prefix="/api")


# --- Montar Directorios Estáticos ---
# Sirve los archivos de audio (ej. /card_audio/hash.mp3)
app.mount(
    f"/{settings.AUDIO_DIR}", 
    StaticFiles(directory=settings.BASE_DIR / settings.AUDIO_DIR), 
    name="audio"
)
# Sirve las imágenes (ej. /card_images/get/get_card_0.jpg)
app.mount(
    f"/{settings.CARD_IMAGES_BASE_DIR}", 
    StaticFiles(directory=settings.BASE_DIR / settings.CARD_IMAGES_BASE_DIR), 
    name="images"
)
# Sirve el frontend (ej. /static/json/get.json)
app.mount(
    f"/{settings.STATIC_DIR}", 
    StaticFiles(directory=settings.BASE_DIR / settings.STATIC_DIR), 
    name="static"
)

# --- Ruta Principal (Servir HTML) ---
@app.get("/")
async def serve_html():
    html_path = settings.BASE_DIR / settings.STATIC_DIR / "flashcard_app.html"
    if html_path.exists():
        return FileResponse(html_path, media_type="text/html")
    else:
        raise HTTPException(status_code=404, detail="No se encuentra el archivo HTML principal.")

# --- Ejecución (para desarrollo) ---
if __name__ == '__main__':
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=8000, 
        timeout_keep_alive=settings.SERVER_TIMEOUT,
        reload=True  # 'reload=True' es genial para desarrollo
    )
