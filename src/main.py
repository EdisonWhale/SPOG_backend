import atexit
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
import yaml
from app.config import load_cache_config
from app.models import CommonErrorResponse
from app.routers.project_intake_router import PROJECT_INTAKE_ROUTER
from app.routers.draft_project_router import DRAFT_PROJECT_ROUTER
from app.routers.use_case_router import USE_CASE_ROUTER
from app.routers.gitlab_sync_router import GITLAB_SYNC_ROUTER
from app.routers.webhook_router import WEBHOOK_ROUTER

# ---
from app.routers.auth_router import AUTH_ROUTER
# ---
from fastapi import FastAPI, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from google.cloud import logging as cloud_logging
from fastapi.openapi.utils import get_openapi
from app.utils.openapi_compliance import normalize_openapi_schema
from api_metadata import metadata

# Security scheme advertised in the OpenAPI document. Matches the HTTPBearer
# dependency used by the auth layer (``app/core/auth.py``).
_SECURITY_SCHEME_NAME = "HTTPBearer"
_SECURITY_SCHEMES = {
    _SECURITY_SCHEME_NAME: {"type": "http", "scheme": "bearer"},
}


def setup_logging():
    root_logger = logging.getLogger()  # Get ROOT logger
    root_logger.setLevel(logging.INFO)

    if os.getenv("K_SERVICE") or os.getenv("JOB_ENV"):
        client = cloud_logging.Client()
        handler = cloud_logging.handlers.StructuredLogHandler()

        atexit.register(lambda: client.close())
    else:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s,%(msecs)d - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s - %(message)s",
            datefmt="%Y-%m-%d:%H:%M:%S",
        )
        handler.setFormatter(formatter)

    root_logger.addHandler(handler)


cache_config = load_cache_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    FastAPICache.init(InMemoryBackend(), prefix=cache_config.prefix)
    yield

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version="3.0.1",
        description=app.description,
        routes=app.routes,
    )

    # Apply API governance lint compliance (same transforms as the static export)
    app.openapi_schema = normalize_openapi_schema(
        openapi_schema,
        security_scheme_name=_SECURITY_SCHEME_NAME,
    )
    return app.openapi_schema


app = FastAPI(
    **metadata,
    lifespan=lifespan,
)

app.openapi = custom_openapi

if os.getenv("K_SERVICE", None) is None:
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
setup_logging()
logger = logging.getLogger(__name__)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request, exc):
    """
    Handle Pydantic validation errors for invalid request payloads.

    Converts Pydantic RequestValidationError into CommonErrorResponse format
    with detailed field validation errors to help clients debug issues.
    Returns 400 Bad Request (not 422) with CommonErrorResponse schema.
    """
    # Extract field-level validation errors
    errors = []
    for error in exc.errors():
        field_path = ".".join(str(loc) for loc in error["loc"][1:])
        error_detail = f"{field_path}: {error['msg']}"
        errors.append(error_detail)

    error_message = "Invalid request payload - " + "; ".join(errors)

    logger.warning(f"Request validation error: {error_message}")

    return JSONResponse(
        status_code=400,
        content=CommonErrorResponse(
            error="Bad Request - Validation Error",
            errorType="Bad Request - Invalid Request Payload",
            errorMessage=error_message,
        ).model_dump(),
    )


@app.get("/openapi.yaml", include_in_schema=False)
async def get_openapi_yaml():
    """
    Serve OpenAPI specification in YAML format
    """
    yaml_content = yaml.dump(app.openapi(), sort_keys=False, default_flow_style=False)
    return Response(content=yaml_content, media_type="application/x-yaml")


# Register the draft router before the project router so that
# /projects/draft/... is matched by the draft endpoints rather than being
# captured by the /projects/{project_id} path parameter.
app.include_router(router=DRAFT_PROJECT_ROUTER, prefix="/projects/draft")
app.include_router(router=PROJECT_INTAKE_ROUTER, prefix="/projects")
app.include_router(router=USE_CASE_ROUTER, prefix="/use-cases")
app.include_router(router=AUTH_ROUTER, prefix="/auth")
app.include_router(router=WEBHOOK_ROUTER, prefix="/webhook")
app.include_router(router=GITLAB_SYNC_ROUTER, prefix="/gitlab")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)
