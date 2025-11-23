import sys
import requests
from google.cloud import storage
from app.core.config import settings

def debug_advanced():
    client = storage.Client(project=settings.PROJECT_ID)
    bucket = client.bucket(settings.GCS_BUCKET_NAME)
    
    target_path = "card_images/phrasal_verbs/break/break_card_0_def0.jpg"
    
    print(f"🔍 Advanced Debugging for: {target_path}")
    
    # 1. List files with repr() to see hidden chars
    prefix = "card_images/phrasal_verbs/break/"
    print(f"\n📂 Listing blobs in '{prefix}':")
    blobs = list(bucket.list_blobs(prefix=prefix))
    found_exact_match = False
    for b in blobs:
        print(f"   - Name: {repr(b.name)}")
        print(f"     Size: {b.size}")
        print(f"     Type: {b.content_type}")
        if b.name == target_path:
            found_exact_match = True
            
    if found_exact_match:
        print("\n✅ Exact match found in listing.")
    else:
        print("\n❌ NO exact match found in listing!")
        
    # 2. Try authenticated download
    print("\n🔑 Testing Authenticated Download...")
    blob = bucket.blob(target_path)
    try:
        content = blob.download_as_bytes()
        print(f"   ✅ Downloaded {len(content)} bytes successfully.")
    except Exception as e:
        print(f"   ❌ Authenticated download failed: {e}")

    # 3. Try Unauthenticated Public Access
    public_url = f"https://storage.googleapis.com/{settings.GCS_BUCKET_NAME}/{target_path}"
    print(f"\n🌐 Testing Public URL: {public_url}")
    try:
        resp = requests.get(public_url)
        print(f"   Status Code: {resp.status_code}")
        if resp.status_code == 200:
            print("   ✅ Public access working.")
        else:
            print("   ❌ Public access FAILED.")
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        print(f"   ❌ Request failed: {e}")

if __name__ == "__main__":
    debug_advanced()
