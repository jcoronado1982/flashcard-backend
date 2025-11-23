# Archivo: app/main.py
import uvicorn
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Importamos la configuración y el router principal
from app.core.config import settings
from app.api.api import api_router
from app.services.gcs_helper import GCSHelper

app = FastAPI(title="Flashcard AI API")

# --- Middlewares (CORS) ---
# Definimos los orígenes permitidos (Local + Producción)
origins = [
    "http://localhost",
    "http://localhost:5173",      # Vite local
    "http://localhost:3000",      # React estándar local
    "http://127.0.0.1:5173",
    "https://flashcard.theruby.lat",      # TU NUEVO DOMINIO (Frontend)
    "https://www.flashcard.theruby.lat",  # Con www por si acaso
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # Usamos la lista específica por seguridad
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Montar Rutas de la API ---
# Todas las rutas de 'api_router' ahora tendrán el prefijo /api
app.include_router(api_router, prefix="/api")

# --- NOTA: Archivos estáticos ahora servidos desde GCS ---
# Los montajes de audio, imágenes y JSON han sido removidos.
# Todos los archivos multimedia ahora se sirven desde Google Cloud Storage.

# --- Ruta Principal (Servir HTML - Opcional si solo es API) ---
@app.get("/")
async def serve_html():
    # Nota: En producción con Frontend separado, esto es menos relevante,
    # pero lo dejamos por si quieres verificar que la API está viva.
    html_path = settings.BASE_DIR / settings.STATIC_DIR / "flashcard_app.html"
    if html_path.exists():
        return FileResponse(html_path, media_type="text/html")
    else:
        return {"message": "Flashcard AI API is running 🚀"}

# --- REDIRECCIONES A GCS (Compatibilidad Frontend) ---

@app.get("/card_images/{file_path:path}")
async def redirect_images(file_path: str):
    """Redirige las peticiones de imágenes locales a GCS."""
    gcs_url = f"https://storage.googleapis.com/{settings.GCS_BUCKET_NAME}/{settings.GCS_IMAGES_PREFIX}/{file_path}"
    return RedirectResponse(url=gcs_url)

@app.get("/card_audio/{file_path:path}")
async def proxy_audio(file_path: str):
    """
    Proxy para archivos de audio desde GCS.
    Descarga el archivo y lo sirve directamente para evitar problemas de CORS/Redirección en el navegador.
    """
    print(f"🔍 Proxy Audio Request: {file_path}")
    blob_path = f"{settings.GCS_AUDIO_PREFIX}/{file_path}"
    try:
        # Descargar contenido (esto es rápido para archivos pequeños de audio)
        audio_content = GCSHelper.download_blob_as_bytes(blob_path)
        # print(f"✅ Proxy Audio Success: {len(audio_content)} bytes") # Comentado para no ensuciar logs en prod
        return Response(content=audio_content, media_type="audio/mpeg")
    except Exception as e:
        print(f"❌ Proxy Audio Error: {e}")
        raise HTTPException(status_code=404, detail=f"Audio no encontrado: {e}")

# --- Ejecución (para desarrollo local) ---
if __name__ == '__main__':
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=8000, 
        timeout_keep_alive=settings.SERVER_TIMEOUT,
        reload=True
    )