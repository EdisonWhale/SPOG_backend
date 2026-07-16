import logging

from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

WEBHOOK_ROUTER = APIRouter(tags=["webhook"])


@WEBHOOK_ROUTER.post(
    "/sync-snow",
    summary="Sync ServiceNow webhook",
    description="Receives a webhook payload from ServiceNow and returns the same data.",
)
async def sync_snow(request: Request) -> JSONResponse:
    try:
        data = await request.json()
        logger.info("Received sync-snow webhook payload")
        return JSONResponse(content=data)
    except Exception as e:
        logger.exception(f"Error processing sync-snow webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook payload",
        )
