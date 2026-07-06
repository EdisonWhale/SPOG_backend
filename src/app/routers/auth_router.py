"""
Auth Router

Endpoints exposing information about the currently authenticated user, derived
from the Microsoft Entra access token in the ``Authorization`` header.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user_info
from app.models.schemas.AuthSchemas import CurrentUserResponse
from app.models.schemas.CommonSchemas import COMMON_ERROR_RESPONSES

logger = logging.getLogger(__name__)

AUTH_ROUTER = APIRouter(tags=["Auth"])


@AUTH_ROUTER.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Get the current user",
    description=(
        "Returns information about the currently authenticated user (name, "
        "email) extracted from the Authorization bearer token."
    ),
    responses={
        **COMMON_ERROR_RESPONSES,
    },
)
async def get_me(
    user_info: Dict[str, Any] = Depends(get_current_user_info),
) -> CurrentUserResponse:
    """Resolve and return the current user's information from the token."""
    logger.info(f"Resolved current user: {user_info.get('user')}")
    return CurrentUserResponse(**user_info)
