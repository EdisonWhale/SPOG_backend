import base64
import json
from typing import Optional, Literal
from cryptography.fernet import Fernet
from app.config.config import load_config
from app.models.cursor.CursorData import CursorData 

class CursorEncoder:
    """Handles encryption/decryption of pagination cursors"""
    
    def __init__(self, secret_key: Optional[str] = None):
        config = load_config()
        # Use a secret key from settings or generate one
        key = secret_key or config.cursor_secret_key
        if not key:
            # Generate a key if none provided (store this in your settings!)
            key = Fernet.generate_key().decode()
        self.cipher = Fernet(key.encode() if isinstance(key, str) else key)
    
    def encode_cursor(
        self, 
        page: int = 0,
        start_doc_id: Optional[str] = None,
        end_doc_id: Optional[str] = None,
        direction: Literal["next", "prev"] = "next"
    ) -> bytes:
        """
        Encode cursor data into encrypted bytes.
        
        Args:
            page: Page number
            start_doc_id: First document ID of the page
            end_doc_id: Last document ID of the page
            direction: "next" or "prev"
            
        Returns:
            Encrypted bytes
        """
        cursor_data = CursorData(
            page=page,
            start_doc_id=start_doc_id,
            end_doc_id=end_doc_id,
            direction=direction
        )
        
        json_data = cursor_data.model_dump_json()
        encrypted = self.cipher.encrypt(json_data.encode())
        return encrypted
    
    def encode_cursor_base64(
        self, 
        page: int = 0,
        start_doc_id: Optional[str] = None,
        end_doc_id: Optional[str] = None,
        direction: Literal["next", "prev"] = "next"
    ) -> str:
        """
        Encode cursor data into a base64 string without encryption.
        
        Args:
            page: Page number
            start_doc_id: First document ID of the page
            end_doc_id: Last document ID of the page
            direction: "next" or "prev"
            
        Returns:
            URL-safe base64 encoded cursor string (unencrypted)
        """
        cursor_data = CursorData(
            page=page,
            start_doc_id=start_doc_id,
            end_doc_id=end_doc_id,
            direction=direction
        )

        json_data = cursor_data.model_dump_json()
        return base64.urlsafe_b64encode(json_data.encode()).decode()
    
    def decode_cursor(self, cursor: str) -> CursorData:
        """
        Decode an encrypted cursor string.
        
        Args:
            cursor: Encrypted cursor string (base64 encoded)
            
        Returns:
            CursorData object with validated pagination data
            
        Raises:
            ValueError: If cursor is invalid or tampered with
        """
        try:
            # Base64 decode
            encrypted = base64.urlsafe_b64decode(cursor.encode())
            
            # Decrypt
            decrypted = self.cipher.decrypt(encrypted)

            cursor_data = CursorData.model_validate_json(decrypted.decode())
            return cursor_data

        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"Invalid cursor format: {str(e)}")
        except Exception as e:
            raise ValueError(f"Invalid cursor: {str(e)}")


    def decode_cursor_base64(self, cursor: str) -> CursorData:
        """
        Decode a base64 cursor string (unencrypted).
        
        Args:
            cursor: Base64 encoded cursor string
            
        Returns:
            CursorData object with validated pagination data
            
        Raises:
            ValueError: If cursor is invalid
        """
        try:
            # Base64 decode
            decoded = base64.urlsafe_b64decode(cursor.encode())
            
            # Parse and validate with Pydantic
            cursor_data = CursorData.model_validate_json(decoded.decode())
            return cursor_data
            
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"Invalid cursor format: {str(e)}")
        except Exception as e:
            raise ValueError(f"Invalid cursor: {str(e)}")


# Singleton instance
cursor_encoder = CursorEncoder()
