"""
Microsoft Entra (Azure AD) authentication.

Routes are called with an ``Authorization: Bearer <token>`` header where the
token is a Microsoft Entra access token. This module decodes and validates that
token and extracts the calling user (the *author*).

Two ways to consume it on a route:

1. As a FastAPI dependency (recommended, type-safe and shows up in OpenAPI):

    from app.core.auth import get_current_author

    @router.post("")
    async def create_project(author: str = Depends(get_current_author)):
        ...

2. As a decorator (per request), for handlers that prefer it:

    from app.core.auth import require_author

    @router.post("")
    @require_author
    async def create_project(request: Request, author: str):
        ...

Both resolve the author from the validated token's claims.
"""

import logging
from typing import Any, Dict, Optional
import json
import jwt
from jwt import PyJWKClient
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import load_entra_config, EntraConfig

logger = logging.getLogger(__name__)

# Claims that may carry the user's identity, in order of preference.
# An Entra *access token* for a custom API may not include the human-readable
# UPN/email claims, so we fall back to stable identifiers (oid/sub) and, for
# app-only tokens, the calling app id (appid/azp).
_AUTHOR_CLAIMS = (
    "preferred_username",
    "upn",
    "email",
    "unique_name",
    "name",
    "oid",
    "sub",
    "appid",
    "azp",
)

# Reusable bearer-token extractor (adds the lock icon in OpenAPI/Swagger).
# ``auto_error=False`` so a missing header does not 403 before our dependency
# runs; we decide the behaviour (reject vs. local-dev fallback) ourselves.
_bearer_scheme = HTTPBearer(auto_error=False)

# Author used for local development when auth is disabled and no token is sent.
_LOCAL_DEV_AUTHOR = "system@email.com"

# Cache one JWKS client per JWKS URI so signing keys are fetched/cached once.
_jwks_clients: Dict[str, PyJWKClient] = {}


class AuthError(Exception):
    """Raised when a token is missing, malformed, or fails validation."""


def _get_jwks_client(jwks_uri: str) -> PyJWKClient:
    client = _jwks_clients.get(jwks_uri)
    if client is None:
        client = PyJWKClient(jwks_uri)
        _jwks_clients[jwks_uri] = client
    return client


def _extract_author(claims: Dict[str, Any]) -> str:
    """Pull the author identifier (email/UPN) from token claims."""
    for claim in _AUTHOR_CLAIMS:
        value = claims.get(claim)
        if value:
            return str(value).strip().lower()
    raise AuthError("Token does not contain a recognizable user identity claim")


def decode_entra_token(token: str, config: Optional[EntraConfig] = None) -> Dict[str, Any]:
    """
    Decode and validate a Microsoft Entra access token.

    When ``config.verify_signature`` is true, the token signature is verified
    against the tenant's JWKS and the issuer/audience/expiry are validated.

    Returns:
        The decoded token claims.

    Raises:
        AuthError: If the token is invalid or cannot be validated.
    """
    config = config or load_entra_config()

    try:
        if config.verify_signature:
            signing_key = _get_jwks_client(config.default_jwks_uri).get_signing_key_from_jwt(token)
            options = {"verify_aud": bool(config.audience)}
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=config.audience or None,
                issuer=config.issuer,
                options=options,
            )
        else:
            # Signature not verified (local/testing). Still reject expired tokens.
            claims = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": True},
            )
        return claims
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError(f"Invalid token: {exc}") from exc
    except Exception as exc:  # JWKS fetch / network / key errors
        logger.exception("Failed to validate Entra token: %s", exc)
        raise AuthError("Unable to validate authorization token") from exc


def get_author_from_token(token: str, config: Optional[EntraConfig] = None) -> str:
    """Validate a token and return the author identifier."""
    claims = decode_entra_token(token, config)
    return _extract_author(claims)


# Claims that may carry the user's display name, in order of preference.
_NAME_CLAIMS = ("name", "given_name")
# Claims that may carry the user's email address, in order of preference.
_EMAIL_CLAIMS = ("email", "preferred_username", "upn", "unique_name")


def _extract_first(claims: Dict[str, Any], names) -> Optional[str]:
    """Return the first present, non-empty claim value as a string."""
    for name in names:
        value = claims.get(name)
        if value:
            return str(value).strip()
    return None


def extract_user_info(claims: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a user-info dictionary (user, name, email) from token claims.

    ``user`` resolves to the stable ``oid`` (object ID) claim; ``name`` and
    ``email`` are best-effort and may be ``None`` for access tokens that omit
    human-readable claims.
    """
    user = claims.get("oid")
    if not user:
        raise AuthError("Token does not contain an 'oid' claim")
    email = _extract_first(claims, _EMAIL_CLAIMS)
    email = email.lower() if email else None
    return {
        "user": str(user).strip(),
        "name": _extract_first(claims, _NAME_CLAIMS),
        "email": email,
    }


def get_user_info_from_token(
    token: str, config: Optional[EntraConfig] = None
) -> Dict[str, Any]:
    """Validate a token and return the current user's information."""
    claims = decode_entra_token(token, config)
    return extract_user_info(claims)


async def get_current_author(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> str:
    """
    FastAPI dependency that resolves the calling user (author) from the
    ``Authorization: Bearer <access-token>`` header.

    Behaviour:
    - Auth disabled (local dev): if no token is sent (or it cannot be decoded),
      fall back to ``system@email.com`` so local development works without a
      header.
    - Auth enabled: a missing or invalid token is rejected with 401.

    Returns:
        The author email / identifier extracted from the validated token.

    Raises:
        HTTPException(401): If auth is enabled and the token is missing or invalid.
    """
    from fastapi import HTTPException, status

    config = load_entra_config()

    if not config.enabled:
        # Auth disabled (e.g. local dev). With no header, use the local-dev author.
        if credentials is None or not credentials.credentials:
            return _LOCAL_DEV_AUTHOR
        # A token was sent: best-effort decode without signature verification.
        try:
            return get_author_from_token(
                credentials.credentials,
                config.model_copy(update={"verify_signature": False}),
            )
        except AuthError:
            return _LOCAL_DEV_AUTHOR

    # Auth enabled: a token is required.
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return get_author_from_token(credentials.credentials, config)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_info(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Dict[str, Any]:
    """
    FastAPI dependency that resolves the calling user's information (user,
    name, email) from the ``Authorization: Bearer <access-token>``
    header.

    Behaviour mirrors :func:`get_current_author`:
    - Auth disabled (local dev): if no token is sent (or it cannot be decoded),
      fall back to a minimal local-dev user.
    - Auth enabled: a missing or invalid token is rejected with 401.

    Raises:
        HTTPException(401): If auth is enabled and the token is missing or invalid.
    """
    from fastapi import HTTPException, status

    config = load_entra_config()

    def _local_dev_user() -> Dict[str, Any]:
        return {"user": _LOCAL_DEV_AUTHOR, "name": None, "email": _LOCAL_DEV_AUTHOR}

    if not config.enabled:
        # Auth disabled (e.g. local dev). With no header, use the local-dev user.
        if credentials is None or not credentials.credentials:
            return _local_dev_user()
        # A token was sent: best-effort decode without signature verification.
        try:
            return get_user_info_from_token(
                credentials.credentials,
                config.model_copy(update={"verify_signature": False}),
            )
        except AuthError:
            return _local_dev_user()

    # Auth enabled: a token is required.
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return get_user_info_from_token(credentials.credentials, config)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_author(handler):
    """
    Decorator alternative to the ``get_current_author`` dependency.

    Resolves the author from the request's Authorization header and injects it
    into the handler as the ``author`` keyword argument. The decorated handler
    must accept a ``request: Request`` parameter and an ``author`` parameter.
    """
    import functools

    @functools.wraps(handler)
    async def wrapper(*args, request: Request, **kwargs):
        from fastapi import HTTPException, status

        auth_header = request.headers.get("Authorization", "")
        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or malformed Authorization header",
                headers={"WWW-Authenticate": "Bearer"},
            )

        config = load_entra_config()
        try:
            verify_cfg = config if config.enabled else config.model_copy(
                update={"verify_signature": False}
            )
            kwargs["author"] = get_author_from_token(token, verify_cfg)
        except AuthError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await handler(*args, request=request, **kwargs)

    return wrapper
