import threading
from typing import Optional

from google.cloud import storage

from ..config.config import load_config

class GCSLimitException(Exception):
    pass


class CloudStorageClient:
    """Singleton GCS client"""
    _client: Optional[storage.Client] = None
    _instance = None
    _instantiation_lock = threading.Lock()
    _project_id = ""
    _bucket_id = ""
    _service_account = ""

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._instantiation_lock:
                if not cls._instance:
                    cls._initialize_client()
                    cls._instance = super(CloudStorageClient, cls).__new__(cls, *args, **kwargs)
        return cls._instance
    
    @classmethod
    def _initialize_client(cls):
        config = load_config()
        
        cls._project_id = config.gcp_config.project_id
        cls._client = storage.Client(project=cls._project_id)
        cls._bucket_id = config.gcp_config.gcs_config.bucket_id
        cls._service_account = config.gcp_config.gcs_config.file_signed_url_sa

    @classmethod
    def InstanceClient(cls) -> storage.Client:
        if not cls._project_id or not cls._client:
            cls._initialize_client()
        return cls._client
    
    @classmethod
    def BucketId(cls) -> str:
        if not cls._bucket_id:
            cls._initialize_client()
        return cls._bucket_id
    
    @classmethod
    def ServiceAccount(cls) -> str:  # Add this method
        if not cls._service_account:
            cls._initialize_client()
        return cls._service_account
