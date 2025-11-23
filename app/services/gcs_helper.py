"""
Google Cloud Storage Helper Module

Provides centralized utilities for interacting with GCS bucket.
Handles blob operations, virtual directory listing, and error handling.
"""

import logging
from typing import List, Optional
from google.cloud import storage
from google.cloud.exceptions import NotFound
from app.core.config import settings


class GCSHelper:
    """Singleton helper class for Google Cloud Storage operations."""
    
    _client: Optional[storage.Client] = None
    _bucket: Optional[storage.Bucket] = None
    
    @classmethod
    def _get_client(cls) -> storage.Client:
        """Get or create storage client (singleton pattern)."""
        if cls._client is None:
            cls._client = storage.Client(project=settings.PROJECT_ID)
            logging.info("✅ GCS Client initialized")
        return cls._client
    
    @classmethod
    def _get_bucket(cls) -> storage.Bucket:
        """Get or create bucket reference (singleton pattern)."""
        if cls._bucket is None:
            client = cls._get_client()
            cls._bucket = client.bucket(settings.GCS_BUCKET_NAME)
            logging.info(f"✅ GCS Bucket reference created: {settings.GCS_BUCKET_NAME}")
        return cls._bucket
    
    @classmethod
    def list_virtual_directories(cls, prefix: str) -> List[str]:
        """
        List virtual directories (prefixes) in GCS using delimiter.
        
        Args:
            prefix: The prefix to search under (e.g., "data/json/")
            
        Returns:
            List of directory prefixes (e.g., ["data/json/category1/", "data/json/category2/"])
        """
        try:
            bucket = cls._get_bucket()
            # Use delimiter to get "virtual directories"
            blobs = bucket.list_blobs(prefix=prefix, delimiter="/")
            
            # Consume the iterator to populate prefixes
            list(blobs)  # This is necessary to populate blobs.prefixes
            
            # Return the prefixes (virtual directories)
            return list(blobs.prefixes) if blobs.prefixes else []
        except Exception as e:
            logging.error(f"Error listing virtual directories with prefix '{prefix}': {e}")
            return []
    
    @classmethod
    def list_blobs_with_prefix(cls, prefix: str, extension: Optional[str] = None) -> List[str]:
        """
        List all blob names with a given prefix, optionally filtered by extension.
        
        Args:
            prefix: The prefix to search under (e.g., "data/json/phrasal_verbs/")
            extension: Optional file extension to filter (e.g., ".json")
            
        Returns:
            List of blob names (full paths)
        """
        try:
            bucket = cls._get_bucket()
            blobs = bucket.list_blobs(prefix=prefix)
            
            blob_names = [blob.name for blob in blobs]
            
            # Filter by extension if provided
            if extension:
                blob_names = [name for name in blob_names if name.endswith(extension)]
            
            return blob_names
        except Exception as e:
            logging.error(f"Error listing blobs with prefix '{prefix}': {e}")
            return []
    
    @classmethod
    def blob_exists(cls, blob_path: str) -> bool:
        """
        Check if a blob exists in the bucket.
        
        Args:
            blob_path: Full path to the blob (e.g., "card_images/get/get_card_0.jpg")
            
        Returns:
            True if blob exists, False otherwise
        """
        try:
            bucket = cls._get_bucket()
            blob = bucket.blob(blob_path)
            return blob.exists()
        except Exception as e:
            logging.error(f"Error checking blob existence '{blob_path}': {e}")
            return False
    
    @classmethod
    def download_blob_as_string(cls, blob_path: str) -> str:
        """
        Download blob content as string (for JSON files).
        
        Args:
            blob_path: Full path to the blob
            
        Returns:
            Blob content as string
            
        Raises:
            NotFound: If blob doesn't exist
            Exception: For other errors
        """
        try:
            bucket = cls._get_bucket()
            blob = bucket.blob(blob_path)
            
            if not blob.exists():
                raise NotFound(f"Blob not found: {blob_path}")
            
            content = blob.download_as_string()
            return content.decode('utf-8')
        except NotFound:
            logging.error(f"Blob not found: {blob_path}")
            raise
        except Exception as e:
            logging.error(f"Error downloading blob '{blob_path}': {e}")
            raise
    
    @classmethod
    def download_blob_as_bytes(cls, blob_path: str) -> bytes:
        """
        Download blob content as bytes (for binary files like images/audio).
        
        Args:
            blob_path: Full path to the blob
            
        Returns:
            Blob content as bytes
            
        Raises:
            NotFound: If blob doesn't exist
            Exception: For other errors
        """
        try:
            bucket = cls._get_bucket()
            blob = bucket.blob(blob_path)
            
            if not blob.exists():
                raise NotFound(f"Blob not found: {blob_path}")
            
            return blob.download_as_bytes()
        except NotFound:
            logging.error(f"Blob not found: {blob_path}")
            raise
        except Exception as e:
            logging.error(f"Error downloading blob '{blob_path}': {e}")
            raise
    
    @classmethod
    def upload_blob_from_string(cls, blob_path: str, content: str, content_type: str = "application/json") -> bool:
        """
        Upload string content to a blob (for JSON files).
        
        Args:
            blob_path: Full path where blob should be stored
            content: String content to upload
            content_type: MIME type of the content
            
        Returns:
            True if successful, False otherwise
        """
        try:
            bucket = cls._get_bucket()
            blob = bucket.blob(blob_path)
            
            blob.upload_from_string(
                content,
                content_type=content_type
            )
            
            logging.info(f"✅ Uploaded blob: {blob_path}")
            return True
        except Exception as e:
            logging.error(f"Error uploading blob '{blob_path}': {e}")
            return False
    
    @classmethod
    def upload_blob_from_bytes(cls, blob_path: str, content: bytes, content_type: str = "application/octet-stream") -> bool:
        """
        Upload bytes content to a blob (for images, audio, etc.).
        
        Args:
            blob_path: Full path where blob should be stored
            content: Bytes content to upload
            content_type: MIME type of the content
            
        Returns:
            True if successful, False otherwise
        """
        try:
            bucket = cls._get_bucket()
            blob = bucket.blob(blob_path)
            
            blob.upload_from_string(
                content,
                content_type=content_type
            )
            
            logging.info(f"✅ Uploaded blob: {blob_path}")
            return True
        except Exception as e:
            logging.error(f"Error uploading blob '{blob_path}': {e}")
            return False
    
    @classmethod
    def delete_blob(cls, blob_path: str) -> bool:
        """
        Delete a blob from the bucket.
        
        Args:
            blob_path: Full path to the blob to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            bucket = cls._get_bucket()
            blob = bucket.blob(blob_path)
            
            if blob.exists():
                blob.delete()
                logging.info(f"🗑️ Deleted blob: {blob_path}")
                return True
            else:
                logging.warning(f"Blob not found for deletion: {blob_path}")
                return False
        except Exception as e:
            logging.error(f"Error deleting blob '{blob_path}': {e}")
            return False
    
    @classmethod
    def get_public_url(cls, blob_path: str) -> str:
        """
        Get the public URL for a blob.
        
        Args:
            blob_path: Full path to the blob
            
        Returns:
            Public URL string
        """
        bucket = cls._get_bucket()
        blob = bucket.blob(blob_path)
        return blob.public_url
    
    @classmethod
    def generate_signed_url(cls, blob_path: str, expiration_minutes: int = 60) -> str:
        """
        Generate a signed URL for private blob access.
        
        Args:
            blob_path: Full path to the blob
            expiration_minutes: URL expiration time in minutes
            
        Returns:
            Signed URL string
        """
        from datetime import timedelta
        
        try:
            bucket = cls._get_bucket()
            blob = bucket.blob(blob_path)
            
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=expiration_minutes),
                method="GET"
            )
            
            return url
        except Exception as e:
            logging.error(f"Error generating signed URL for '{blob_path}': {e}")
            raise
