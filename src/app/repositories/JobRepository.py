import logging

from google.cloud.firestore import AsyncClient

from app.models.job.GitLabSyncJob import GitLabSyncJob
from app.repositories.AsyncDocumentRepository import AsyncDocumentRepository

logger = logging.getLogger(__name__)


class JobRepository(AsyncDocumentRepository[GitLabSyncJob]):
    """
    Repository for UseCase entities.
    Handles all database operations for use cases.
    """

    def __init__(self, db: AsyncClient):
        """Initialize JobRepository with Firestore client."""
        super().__init__(db, GitLabSyncJob)
