import threading
from typing import Any

import firebase_admin
from google.cloud.firestore import AsyncClient
from firebase_admin.firestore_async import client as async_firestore_client

from ..config import load_config

class FirestoreLimits():
    """
    Refer to https://firebase.google.com/docs/firestore/quotas#collections_documents_and_fields for more information
    
    Static fields
    -------------
    DOCUMENT_SIZE_BYTES : int
        1048487 is the official value, but the limit when comparing to `sys.getsizeof(json.dumps(doc))` seems to be `1085482`, which gives us some padding for error messages in the response.
    """
    DOCUMENT_SIZE_BYTES: int = 1048487
    BATCH_SIZE: int = 500

class FirestoreLimitException(Exception):
    """
    Exception class that reports the exceeded Firestore limit and its value.

    Instance fields
    ---------------
    exceeded_limit_name : str
    exceeded_limit_value : typing.Any
    """
    def __init__(self, exceeded_limit_name: str, exceeded_limit_value: Any):
        self.message = f"Firestore limit {exceeded_limit_name} was exceeded with value: {exceeded_limit_value}"
        self.exceeded_limit_name = exceeded_limit_name
        self.exceeded_limit_value = exceeded_limit_value
        super().__init__(self.message)
    
    @staticmethod
    def create_document_size_limit_exception(document_size_bytes: int):
        return FirestoreLimitException("document_size_bytes", document_size_bytes)
        
class FirestoreClient:
    """Singleton Firestore client for interacting with Google Firestore"""

    _client = None
    _instance = None
    _database_id = None
    _project_id = None
    _instantiation_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._instantiation_lock:
                if not cls._instance:
                    cls._initialize_client()
                    cls._instance = super(FirestoreClient, cls).__new__(cls, *args, **kwargs)
        return cls._instance
    
    @classmethod
    def _initialize_client(cls):
        config = load_config()
        cls._database_id = config.gcp_config.firestore_config.database_id
        cls._project_id = config.gcp_config.project_id
        if len(firebase_admin._apps) == 0:
            firebase_admin.initialize_app(options={
                'projectId': cls._project_id
            })
        cls._client = async_firestore_client(database_id=cls._database_id)

    @classmethod
    def InstanceClient(cls) -> AsyncClient:
        if not cls._database_id or not cls._client:
            FirestoreClient._initialize_client()
        return cls._client
