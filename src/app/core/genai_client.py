import threading
import os
from typing import Optional

from google import genai
from google.genai import types
from google.cloud import storage

from ..config.config import load_config


class GenAIClient:
    """Singleton GenAI client for Vertex AI"""
    
    _client: Optional[genai.Client] = None
    _storage_client: Optional[storage.Client] = None
    _instance = None
    _instantiation_lock = threading.Lock()
    _project_id = ""
    _location = ""
    _model_name = ""

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._instantiation_lock:
                if not cls._instance:
                    cls._initialize_client()
                    cls._instance = super(GenAIClient, cls).__new__(cls, *args, **kwargs)
        return cls._instance
    
    @classmethod
    def _initialize_client(cls):
        config = load_config()
        
        cls._project_id = config.gcp_config.project_id
        cls._location = config.genai_config.location
        cls._model_name = config.genai_config.model_name
        
        # Initialize the genai client
        cls._client = genai.Client(
            http_options=types.HttpOptions(api_version="v1"),
            vertexai=True,
            project=cls._project_id,
            location=cls._location
        )
        
        # Initialize GCS client
        cls._storage_client = storage.Client(project=cls._project_id)

    @classmethod
    def InstanceClient(cls) -> genai.Client:
        if not cls._project_id or not cls._client:
            cls._initialize_client()
        return cls._client
    
    @classmethod
    def StorageClient(cls) -> storage.Client:
        if not cls._storage_client:
            cls._initialize_client()
        return cls._storage_client
    
    @classmethod
    def ProjectId(cls) -> str:
        if not cls._project_id:
            cls._initialize_client()
        return cls._project_id
    
    @classmethod
    def Location(cls) -> str:
        if not cls._location:
            cls._initialize_client()
        return cls._location
    
    @classmethod
    def ModelName(cls) -> str:
        if not cls._model_name:
            cls._initialize_client()
        return cls._model_name
