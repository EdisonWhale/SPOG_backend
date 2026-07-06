import logging, os
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import jwt

logger = logging.getLogger(__name__)

auto_error = os.getenv("K_SERVICE") is not None
security = HTTPBearer(auto_error=auto_error)

AuthCredentials = Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)]
class MockAuthService:
    """
    To be used for either unit tests or local runs where Authorization data may not be present
    """
    def __init__(self):
        self.auth_data = {}
        self.auth_token = "mock_token"
        self.current_user = "local_dev@mock.org"

    async def get_auth_token(self, credentials: AuthCredentials = None) -> str:
        return self.auth_token
    
    async def get_auth_data(self, credentials: AuthCredentials = None) -> dict:
        return self.auth_data

    async def get_current_user(self, credentials: AuthCredentials = None) -> str:
        return self.current_user

class AuthService:
    """
    To be used within a single request/response context
    """
    def __init__(self):
        self.auth_data = {}
        self.auth_token = None
        self.current_user = ""

    async def get_auth_token(self, credentials: AuthCredentials = None) -> str:
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="You are not authorized to access this resource or action."
            )
        
        await self._verify_and_decode_auth_data(credentials.credentials)
        return self.auth_token

    async def get_auth_data(self, credentials: AuthCredentials = None) -> dict:
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="You are not authorized to access this resource or action."
            )
        
        auth_data = await self._verify_and_decode_auth_data(credentials.credentials)
        return auth_data

    async def get_current_user(self, credentials: AuthCredentials = None) -> str:
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="You are not authorized to access this resource or action."
            )

        auth_data: dict = await self.get_auth_data(credentials=credentials)

        user_email: str = self._extract_user_email(auth_data=auth_data)

        self.current_user = user_email
        return user_email

    @staticmethod
    def _extract_user_email(auth_data: dict) -> str:
        claim_candidates = [
            "mail",
            "email",
            "preferred_username",
            "upn",
            "unique_name",
        ]

        for claim_key in claim_candidates:
            claim_value = auth_data.get(claim_key, "")
            if not isinstance(claim_value, str):
                continue

            normalized = claim_value.strip().lower()
            if normalized and "@" in normalized:
                return normalized

        return ""
    
    async def _verify_and_decode_auth_data(self, auth_token: str) -> dict:
        try:
            auth_data: dict = jwt.decode(auth_token, options={
                "verify_signature": False,
                "verify_exp": True,
            })
            
            self.auth_token = auth_token
            self.auth_data = auth_data
            return auth_data
        except jwt.exceptions.PyJWTError as pje:
            logger.exception(f"Encountered {type(pje)} error while decoding auth token: {pje}")
            raise

def auth_service_factory():
    if os.getenv("K_SERVICE", None) is None:
        return MockAuthService()
    else:
        return AuthService()
    
class UserRequiredFilter:
    def __init__(self):
        pass

    async def __call__(
        self, 
        auth_service: Annotated[AuthService, Depends(auth_service_factory)],
        credentials: AuthCredentials
    ):
        aitr_user = await auth_service.get_current_user(credentials)

        if not aitr_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="You are not authorized to access this resource or action."
            )
        
        return aitr_user
