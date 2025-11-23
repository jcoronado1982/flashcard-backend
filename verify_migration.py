#!/usr/bin/env python3
"""
Script de Verificación de Migración a GCS
Verifica la conexión al bucket y la estructura de datos.
"""

import os
import sys
from pathlib import Path

# Añadir el directorio raíz al path para importar módulos
sys.path.insert(0, str(Path(__file__).parent))

from google.cloud import storage
from app.core.config import settings

def main():
    print("=" * 60)
    print("🔍 VERIFICACIÓN DE MIGRACIÓN A GCS")
    print("=" * 60)
    print()
    
    # 1. Verificar configuración
    print(f"📋 Configuración:")
    print(f"   Bucket: {settings.GCS_BUCKET_NAME}")
    print(f"   JSON Prefix: {settings.GCS_JSON_PREFIX}")
    print(f"   Images Prefix: {settings.GCS_IMAGES_PREFIX}")
    print(f"   Audio Prefix: {settings.GCS_AUDIO_PREFIX}")
    print()
    
    try:
        # 2. Conectar al bucket
        print("🔌 Conectando a Google Cloud Storage...")
        client = storage.Client(project=settings.PROJECT_ID)
        bucket = client.bucket(settings.GCS_BUCKET_NAME)
        print(f"✅ Conexión exitosa al bucket '{settings.GCS_BUCKET_NAME}'")
        print()
        
        # 3. Listar categorías (simulando deck_service.list_categories)
        print(f"📁 Listando categorías desde '{settings.GCS_JSON_PREFIX}/'...")
        blobs = bucket.list_blobs(prefix=f"{settings.GCS_JSON_PREFIX}/", delimiter="/")
        
        # Consumir el iterador para poblar prefixes
        list(blobs)
        
        if blobs.prefixes:
            categories = [
                prefix.replace(f"{settings.GCS_JSON_PREFIX}/", "").rstrip("/")
                for prefix in blobs.prefixes
            ]
            categories.sort()
            
            print(f"✅ Categorías encontradas ({len(categories)}):")
            for cat in categories:
                print(f"   - {cat}")
            print()
        else:
            print("❌ No se encontraron categorías en el bucket")
            print(f"   Verifica que existan carpetas en '{settings.GCS_JSON_PREFIX}/'")
            return False
        
        # 4. Verificar JSONs en la primera categoría
        if categories:
            first_category = categories[0]
            print(f"📄 Verificando JSONs en categoría '{first_category}'...")
            json_prefix = f"{settings.GCS_JSON_PREFIX}/{first_category}/"
            json_blobs = list(bucket.list_blobs(prefix=json_prefix))
            json_files = [blob.name for blob in json_blobs if blob.name.endswith('.json')]
            
            if json_files:
                print(f"✅ Encontrados {len(json_files)} archivos JSON:")
                for json_file in json_files[:5]:  # Mostrar solo los primeros 5
                    print(f"   - {json_file}")
                if len(json_files) > 5:
                    print(f"   ... y {len(json_files) - 5} más")
                print()
            else:
                print(f"⚠️  No se encontraron archivos JSON en '{json_prefix}'")
                print()
        
        # 5. Verificar imágenes
        print(f"🖼️  Verificando imágenes en '{settings.GCS_IMAGES_PREFIX}/'...")
        image_blobs = list(bucket.list_blobs(prefix=f"{settings.GCS_IMAGES_PREFIX}/", max_results=10))
        image_files = [blob.name for blob in image_blobs if blob.name.endswith(('.jpg', '.jpeg', '.png'))]
        
        if image_files:
            print(f"✅ Encontradas imágenes (mostrando primeras {len(image_files)}):")
            for img in image_files[:5]:
                print(f"   - {img}")
            print()
        else:
            print(f"⚠️  No se encontraron imágenes en '{settings.GCS_IMAGES_PREFIX}/'")
            print()
        
        # 6. Verificar audio
        print(f"🔊 Verificando audio en '{settings.GCS_AUDIO_PREFIX}/'...")
        audio_blobs = list(bucket.list_blobs(prefix=f"{settings.GCS_AUDIO_PREFIX}/", max_results=10))
        audio_files = [blob.name for blob in audio_blobs if blob.name.endswith('.mp3')]
        
        if audio_files:
            print(f"✅ Encontrados archivos de audio (mostrando primeros {len(audio_files)}):")
            for audio in audio_files[:5]:
                print(f"   - {audio}")
            print()
        else:
            print(f"⚠️  No se encontraron archivos de audio en '{settings.GCS_AUDIO_PREFIX}/'")
            print()
        
        # 7. Resumen final
        print("=" * 60)
        if categories and (json_files or image_files or audio_files):
            print("✅ CONEXIÓN Y ESTRUCTURA VERIFICADAS CORRECTAMENTE")
            print("=" * 60)
            print()
            print("📊 Resumen:")
            print(f"   ✓ Categorías: {len(categories)}")
            print(f"   ✓ JSONs verificados: {len(json_files) if json_files else 0}")
            print(f"   ✓ Imágenes verificadas: {len(image_files) if image_files else 0}")
            print(f"   ✓ Audio verificado: {len(audio_files) if audio_files else 0}")
            print()
            print("🚀 El backend está listo para usar GCS")
            return True
        else:
            print("⚠️  VERIFICACIÓN INCOMPLETA")
            print("=" * 60)
            print()
            print("Algunos recursos no se encontraron en el bucket.")
            print("Verifica que los archivos estén subidos correctamente.")
            return False
            
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ ERROR EN LA VERIFICACIÓN")
        print("=" * 60)
        print(f"Error: {e}")
        print()
        print("Posibles causas:")
        print("  1. Credenciales de GCP no configuradas")
        print("  2. Bucket no existe o no tienes permisos")
        print("  3. Variable PROJECT_ID no está en .env")
        print()
        print("Solución:")
        print("  Ejecuta: gcloud auth application-default login")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
