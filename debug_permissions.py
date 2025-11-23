import sys
import os
from app.services.gcs_helper import GCSHelper
from app.core.config import settings

def check_permissions():
    print("🔍 Checking GCS Permissions...")
    
    try:
        gcs = GCSHelper()
        bucket_name = settings.GCS_BUCKET_NAME
        print(f"📦 Bucket: {bucket_name}")
        
        # 1. Check List Permissions
        print("\n1️⃣ Testing List Permissions...")
        blobs = gcs.list_blobs_with_prefix(settings.GCS_AUDIO_PREFIX, extension=".mp3")
        print(f"✅ List successful. Found {len(blobs)} audio files.")
        if len(blobs) > 0:
            print(f"   Example: {blobs[0]}")
            
            # 2. Check Read Permissions
            print("\n2️⃣ Testing Read Permissions...")
            blob_path = blobs[0]
            print(f"   Attempting to download: {blob_path}")
            
            try:
                content = gcs.download_blob_as_bytes(blob_path)
                print(f"✅ Download successful. Size: {len(content)} bytes")
            except Exception as e:
                print(f"❌ Download FAILED: {e}")
        else:
            print("⚠️ No blobs found to test download.")
            
    except Exception as e:
        print(f"❌ GCS Initialization or List FAILED: {e}")

if __name__ == "__main__":
    # Ensure we can import app modules
    sys.path.append(os.getcwd())
    check_permissions()
