import asyncio
import logging
from datetime import timedelta
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

import google.auth
from google.auth import impersonated_credentials
from google.auth.transport import requests
from google.cloud import storage
from google.cloud.exceptions import NotFound as GCSNotFound

from pydantic import BaseModel

from app.core.gcs_client import CloudStorageClient

logger = logging.getLogger(__name__)

class GCSBucketInfo(BaseModel):
    bucket_name: str
    signed_url_service_account: str

class SignedUrlResult(BaseModel):
    signed_url: str
    gcs_path: str

class SignedUrlGenerationError(Exception):
    def __init__(self, blob_path):
        self.message = f"Failed to generate signed url to upload to {blob_path}"
        super().__init__(self.message)

class CloudStorageService:

    SIGNED_URL_VERSION = "v4"
    SIGNED_URL_EXPIRATION_MINUTES = 45

    def __init__(self):
        storage_client = CloudStorageClient()
        self._persistence_client = storage_client.InstanceClient()
        self._bucket_id = storage_client.BucketId()
        self._service_account = storage_client.ServiceAccount()
        self._executor = ThreadPoolExecutor(max_workers=10)

    def get_bucket(self) -> storage.Bucket:
        """Returns a handle to the GCS Bucket"""
        return self._persistence_client.bucket(self._bucket_id)
    
    async def get_blob_list(
        self,
        filter_prefix: str
    ):
        """Get blob list asynchronously"""
        loop = asyncio.get_event_loop()
        bucket = self.get_bucket()
        return await loop.run_in_executor(
            self._executor,
            lambda: list(bucket.list_blobs(prefix=filter_prefix))
        )
    
    async def get_files(
        self,
        project_id: str,
        subfolder: str,
        file_extensions: Optional[tuple] = None,
        file_name: str = None
    ) -> list[str]:
        """
        Get all files for a specific session in a given subfolder (async).
        
        Parameters
        ----------
        project_id : str
            The session identifier
        subfolder : str
            Subfolder name (e.g., 'recording', 'report', 'transcripts')
        file_extensions : Optional[tuple]
            Tuple of file extensions to filter
            
        Returns
        -------
        list[str]
            List of GCS URIs (excludes folder paths)
        """
        bucket = self.get_bucket()
        prefix = f"project/{project_id}/{subfolder}/"
        
        if file_name:
            blob_path = f"{prefix}{file_name}"
            blob = bucket.blob(blob_path)

            exists = await asyncio.to_thread(blob.exists)
            if exists:
                return [f"gs://{bucket.name}/{blob_path}"]
            return []

        blobs = await self.get_blob_list(prefix)
        
        gcs_uris = []
        for blob in blobs:
            # Skip folder markers (blobs ending with /)
            if blob.name.endswith('/'):
                continue
                
            # Skip if filtering by extension and blob doesn't match
            if file_extensions and not blob.name.lower().endswith(file_extensions):
                continue
            
            gcs_uri = f"gs://{bucket.name}/{blob.name}"
            gcs_uris.append(gcs_uri)
        
        return gcs_uris

    async def create_upload_signed_url(
        self,
        blob_path: str,
        mime_type: str,
        service_account: str,
        expiration_delta: timedelta = timedelta(minutes=SIGNED_URL_EXPIRATION_MINUTES),
    ) -> SignedUrlResult:
        """
        `create_upload_signed_url` generates a signed URL that can be used
        to upload a file to a GCS bucket, `bucket` to `blob_path` (async)

        Parameters
        ----------
        `bucket` : storage.Bucket
        `blob_path` : str
        `mime_type` : str
        `service_account`: str
            Name of the GCP service account that will be used to create the signed url
        `expiration_delta`: timedelta
            How long from now the resulting signed url will be valid for. Defaults to 45 minutes
        
        Raises
        ------
        `SignedUrlGenerationError`
            Wraps the underlying error that caused the signed url generation to fail

        Returns
        -------
        `SignedUrlResult`
        """
        def _generate_signed_url():
            try:
                credentials, project_id = google.auth.default()
                target_scopes = [
                    "https://www.googleapis.com/auth/cloud-platform",
                    "https://www.googleapis.com/auth/devstorage.read_write",
                ]
                if credentials.token is None:
                    credentials.refresh(requests.Request())
                impersonated_creds = impersonated_credentials.Credentials(
                    source_credentials=credentials,
                    target_principal=service_account,
                    target_scopes=target_scopes,
                )
                if impersonated_creds.token is None:
                    impersonated_creds.refresh(requests.Request())

                bucket = self.get_bucket()
                blob = bucket.blob(blob_path)
                signed_url = blob.generate_signed_url(
                    version=self.SIGNED_URL_VERSION,
                    expiration=expiration_delta,
                    service_account_email=service_account,
                    method="PUT",
                    access_token=impersonated_creds.token,
                    content_type=mime_type
                )
                gcs_path = f"gs://{blob.bucket.name}/{blob.name}"
                return SignedUrlResult(
                    signed_url=signed_url,
                    gcs_path=gcs_path
                )
            except Exception as e:
                logger.error(f"Error generating signed URL for {blob_path}: {e}", exc_info=True)
                raise SignedUrlGenerationError(blob_path) from e
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _generate_signed_url)
        
    async def download_blob(
        self,
        blob_path: str,
        local_path: str,
    ) -> bool:
        """Download blob asynchronously"""
        def _download():
            try:
                bucket = self.get_bucket()
                blob = bucket.blob(blob_path)
                blob.download_to_filename(local_path)
                return True
            except Exception as e:
                return False
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _download)
        
    async def delete_blob(
        self,
        blob_path: str,
    ) -> bool:
        """Delete blob asynchronously"""
        def _delete():
            try:
                bucket = self.get_bucket()
                blob = bucket.blob(blob_path)

                generation_match_precondition = None
                blob.reload()
                generation_match_precondition = blob.generation

                blob.delete(if_generation_match=generation_match_precondition)
                return True
            except GCSNotFound as nfe:
                return True # just consider it a no-op
            except Exception as e:
                raise # unexpected
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _delete)

    async def blob_exists(
        self,
        blob_path: str
    ) -> bool:
        """Check if blob exists asynchronously"""
        def _exists():
            try:
                bucket = self.get_bucket()
                blob = bucket.blob(blob_path)
                return blob.exists()
            except Exception:
                return False
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _exists)
    
    async def upload_blob(
        self,
        blob_path: str,
        data: bytes,
        content_type: str = "application/octet-stream"
    ) -> str:
        """Upload blob asynchronously"""
        def _upload():
            bucket = self.get_bucket()
            blob = bucket.blob(blob_path)
            blob.upload_from_string(data, content_type=content_type)
            return f"gs://{bucket.name}/{blob_path}"
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _upload)
    
    def __del__(self):
        """Cleanup executor on deletion"""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)

    async def create_download_signed_url(
        self,
        blob_path: str,
        service_account: str = None,
        expiration_delta: timedelta = timedelta(minutes=SIGNED_URL_EXPIRATION_MINUTES),
    ) -> SignedUrlResult:
        """
        Generate a signed URL for temporary file download access.
        
        Parameters
        ----------
        bucket : storage.Bucket
            The GCS bucket containing the file
        blob_path : str
            Path to the file in the bucket
        service_account : str
            GCP service account for signing the URL
        expiration_delta : timedelta
            URL validity period (default: 45 minutes)
        
        Returns
        -------
        SignedUrlResult
            Contains the signed URL and GCS path
            
        Raises
        ------
        SignedUrlGenerationError
            If URL generation fails
        """
        def _generate_signed_url():
            try:
                credentials, project_id = google.auth.default()
                auth_request = requests.Request()
                target_scopes = [
                    "https://www.googleapis.com/auth/cloud-platform",
                    "https://www.googleapis.com/auth/devstorage.read_only",
                ]

                if not credentials.valid:
                    credentials.refresh(auth_request)
                
                target_email = service_account or self._service_account
                impersonated_creds = impersonated_credentials.Credentials(
                    source_credentials=credentials,
                    target_principal=target_email,
                    target_scopes=target_scopes,
                )

                if not impersonated_creds.valid:
                    impersonated_creds.refresh(auth_request)
                target_token = impersonated_creds.token

                bucket = self.get_bucket()
                blob = bucket.blob(blob_path)
                
                if not blob.exists():
                    raise FileNotFoundError(f"Blob not found: {blob_path}")
                
                signed_url = blob.generate_signed_url(
                    version=self.SIGNED_URL_VERSION,
                    expiration=expiration_delta,
                    service_account_email=target_email,
                    method="GET",
                    access_token=target_token,
                )
                
                gcs_path = f"gs://{blob.bucket.name}/{blob.name}"
                return SignedUrlResult(
                    signed_url=signed_url,
                    gcs_path=gcs_path
                )
            except Exception as e:
                logger.error(f"Error generating signed URL for {blob_path}: {e}", exc_info=True)
                raise SignedUrlGenerationError(blob_path) from e
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _generate_signed_url)


