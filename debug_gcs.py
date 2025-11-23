import sys
from google.cloud import storage
from app.core.config import settings

def debug_image():
    client = storage.Client(project=settings.PROJECT_ID)
    bucket = client.bucket(settings.GCS_BUCKET_NAME)
    
    # The path from the logs
    blob_path = "card_images/phrasal_verbs/break/break_card_0_def0.jpg"
    blob = bucket.blob(blob_path)
    
    print(f"🔍 Checking blob: {blob_path}")
    print(f"   Bucket: {settings.GCS_BUCKET_NAME}")
    
    if blob.exists():
        print("✅ Blob EXISTS in GCS")
        print(f"   Size: {blob.size} bytes")
        print(f"   Content Type: {blob.content_type}")
        print(f"   Public URL: {blob.public_url}")
        
        # Check ACLs
        print("   ACLs:")
        for entry in blob.acl:
            print(f"    - {entry}")
            
        # Try to make it explicitly public to be sure
        try:
            blob.make_public()
            print("   ✅ Made public explicitly just now.")
            print(f"   New Public URL: {blob.public_url}")
        except Exception as e:
            print(f"   ⚠️ Failed to make public: {e}")
            
    else:
        print("❌ Blob does NOT exist in GCS")
        
        # List nearby files to check for typos
        prefix = "card_images/phrasal_verbs/break/"
        print(f"   Listing files in {prefix}...")
        blobs = list(bucket.list_blobs(prefix=prefix))
        if blobs:
            for b in blobs:
                print(f"    - {b.name}")
        else:
            print("    (No files found in this folder)")

if __name__ == "__main__":
    debug_image()
