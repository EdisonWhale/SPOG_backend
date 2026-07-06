from abc import ABC, abstractmethod
import logging
from pydantic import ValidationError
from typing import AsyncGenerator, Optional, TypeVar, Generic, Type, List, Dict, Any, Tuple
from google.api_core import exceptions as GCPExceptions
from google.cloud.firestore import (
    AsyncClient, 
    AsyncDocumentReference, 
    AsyncCollectionReference,
    Query,
    AsyncQuery,
    DocumentSnapshot
)
from app.utils.cursor_utils import cursor_encoder
from typing import ClassVar, Dict

from google.protobuf.timestamp_pb2 import Timestamp
from app.models import (
    SpogBaseModel,
    CursorData
)

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=SpogBaseModel) # T must be a subclass of SpogBaseModel


class AsyncDocumentRepository(ABC, Generic[T]):
    """
    Abstract base class for async Firestore document repositories.
    Provides common async CRUD operations for `SpogBaseModel` instance models.
    """

    FIRESTORE_EXCLUDES: ClassVar[Dict[str, bool]] = {}

    def __init__(self, db: AsyncClient, model_type: Type[T], collection_ref: Optional[AsyncCollectionReference]=None):
        if model_type.COLLECTION_NAME is None and collection_ref is None:
            raise ValueError("Either `model_type` must have the property `COLLECTION_NAME` or `collection_ref` must be provided.")

        self.db = db
        self.model_type = model_type

        if collection_ref:
            self.collection_ref = collection_ref
        else:
            self.collection_ref: AsyncCollectionReference = db.collection(model_type.COLLECTION_NAME)

    def _to_firestore_document(self, model: T, excludes: Optional[Dict[str, bool]]=None) -> Dict[str, Any]:
        """
        Converts the `AITrainerBaseModel` model instance into a dictionary suitable for Firestore.
        This can be overridden for specific serialization needs.
        """
        if excludes is None:
            excludes = dict()
        excludes = {**excludes, **self.FIRESTORE_EXCLUDES}

        return model.to_dict(
            date_format_iso=False,
            to_exclude=excludes,
            include_document_id=False
        )
    
    def _to_json_dict(self, model: T, excludes: Dict[str, bool]={}) -> Dict[str, Any]:
        """
        Converts the `AITrainerBaseModel` model instance into a dictionary suitable for JSON serialization.
        """

        return model.to_dict(
            date_format_iso=True,
            include_document_id=True,
            to_camel=True,
            to_exclude=excludes,
        )
    
    async def _get_results_from_query(self, async_query: AsyncQuery) -> List[T]:
        if not async_query:
            return []
        
        results: List[T] = []
        doc_snapshots = async_query.stream()

        async for doc in doc_snapshots:
            item: T = self._from_firestore_document(doc.id, doc.to_dict())
            results.append(item)
        return results

    async def _get_generator_from_query(self, async_query: AsyncQuery) -> AsyncGenerator[T, None]:
        if not async_query or not isinstance(async_query, AsyncQuery):
            yield []
        
        async_generator = async_query.stream()
        async for doc_snapshot in async_generator:
            item: T = self._from_firestore_document(doc_snapshot.id, doc_snapshot.to_dict())
            yield item

    def _from_firestore_document(self, doc_id: str, doc_data: Dict[str, Any]) -> T:
        """
        Deserializes Firestore document data into a `AITrainerBaseModel` model instance.
        """
        return self.model_type(id=doc_id, **doc_data)

    def _get_document_ref(self, document_id: str) -> AsyncDocumentReference:
        """
        Gets the AsyncDocumentReference for the given document ID.
        """
        return self.collection_ref.document(document_id)

    async def create(self, model: T, excludes: Dict[str, bool]={}) -> T:
        """
        Creates a new document in Firestore from an `AITrainerBaseModel` model instance.
        If model.id is None, Firestore will generate an ID.
        """
        as_dict = self._to_firestore_document(model, excludes=excludes)
        if model.id:
            doc_ref = self._get_document_ref(model.id)
            await doc_ref.set(as_dict)
            return self._from_firestore_document(model.id, as_dict)
        else:
            updated_utc, doc_ref = await self.collection_ref.add(as_dict)
            return self._from_firestore_document(doc_ref.id, as_dict)

    async def get(self, document_id: str) -> Optional[T]:
        """
        Retrieves a document by its ID and deserializes it into an `AITrainerBaseModel` model instance.
        """
        doc_ref = self._get_document_ref(document_id)
        doc_snapshot: DocumentSnapshot = await doc_ref.get()
        if doc_snapshot.exists:
            return self._from_firestore_document(doc_snapshot.id, doc_snapshot.to_dict())
        return None

    async def update(self, model: T, excludes: Dict[str, bool]={}) -> T:
        """
        Updates an existing document in Firestore.
        Requires the `AITrainerBaseModel` model instance to have the field, `id`.
        """
        if not model.id:
            raise ValueError("Cannot update a document without an ID.")
        doc_ref = self._get_document_ref(model.id)
        await doc_ref.update(self._to_firestore_document(model, excludes=excludes))

        return model

    async def delete(self, document_id: str) -> bool:
        """
        Deletes a document by its ID.
        Returns True if deleted, False if not found.
        """
        doc_ref = self._get_document_ref(document_id)
        doc_snapshot: DocumentSnapshot = await doc_ref.get()
        
        if doc_snapshot.exists:
            await doc_ref.delete()
            return True
        return False

    async def get_by_field(self, field_name: str, operator: str, value: Any, limit: Optional[int] = None) -> List[T]:
        """
        Gets documents by a specific field, operator, and value.
        Example: get_by_field("status", "==", "active")
        """
        async_query: AsyncQuery = self.collection_ref.where(field_name, operator, value)
        if limit:
            async_query = async_query.limit(limit)

        results: List[T] = await self._get_results_from_query(async_query)
        return results
    
    async def get_by_field_generator(self, field_name: str, operator: str, value: Any, limit: Optional[int] = None) -> AsyncGenerator[T, None]:
        async_query: AsyncQuery = self.collection_ref.where(field_name, operator, value)
        if limit:
            async_query = async_query.limit(limit)
        return self._get_generator_from_query(async_query)
    
    async def get_all(self, limit: Optional[int] = None) -> List[T]:
        """
        Gets all documents in the collection, deserializing them into `AITrainerBaseModel` instance models.
        """
        async_query: AsyncQuery = self.collection_ref
        if limit:
            async_query = async_query.limit(limit)
        
        results: List[T] = await self._get_results_from_query(async_query)
        return results

    async def count_all(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count documents in the collection with optional filters.

        Returns:
            Total number of matching documents.
        """
        async_query: AsyncQuery = self.collection_ref
        if filters:
            for field_name, value in filters.items():
                if value is not None:
                    async_query = async_query.where(field_name, "==", value)

        try:
            aggregation_query = async_query.count()
            aggregation_results = await aggregation_query.get()
            if not aggregation_results:
                return 0

            first = aggregation_results[0]
            if hasattr(first, "value"):
                return int(first.value)
            if hasattr(first, "to_dict"):
                data = first.to_dict()
                if isinstance(data, dict) and data:
                    return int(next(iter(data.values())))
            if isinstance(first, (list, tuple)) and first:
                inner = first[0]
                if hasattr(inner, "value"):
                    return int(inner.value)

            return 0
        except (AttributeError, TypeError, ValueError, NotImplementedError) as exc:
            logger.warning(
                "Count aggregation unavailable or invalid, falling back to full scan: %s",
                exc,
                exc_info=True,
            )
            results: List[T] = await self._get_results_from_query(async_query)
            return len(results)
        except GCPExceptions.GoogleAPICallError as exc:
            logger.exception("Count aggregation failed due to Firestore error: %s", exc)
            raise
        except Exception as exc:
            logger.exception("Unexpected error during count aggregation: %s", exc)
            raise
    
    async def get_all_generator(self, limit: Optional[int] = None) -> AsyncGenerator[T, None]:
        async_query: AsyncQuery = self.collection_ref
        if limit:
            async_query = async_query.limit(limit)
        return self._get_generator_from_query(async_query)
    
    async def get_all_paginated(
        self, 
        page_size: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        cursor: Optional[str] = None,
        order_by: str = "created_utc",
        sort_direction = Query.DESCENDING,
    ) -> Tuple[List[T], Optional[str], Optional[str]]:
        """
        Gets all documents with optional filtering and encrypted cursor pagination.
        
        Args:
            page_size: Maximum number of documents to return
            filters: Dictionary of field filters {field_name: value}
            cursor: Encrypted pagination cursor
            order_by: Field to order results by (default: created_utc)
            sort_direction: Query.ASCENDING or Query.DESCENDING
        
        Returns:
            Tuple of (list of documents, next_cursor, prev_cursor)
        """
        
        cursor_data = CursorData(
            page=0,
            start_doc_id=None,
            end_doc_id=None,
            direction="next"
        )

        if cursor:
            try:
                cursor_data = cursor_encoder.decode_cursor_base64(cursor)
            except ValidationError as e:
                logger.warning(f"Cursor validation failed: {e.errors()}")
                raise ValueError("Invalid cursor data format")
            except ValueError as e:
                logger.warning(f"Cursor decoding failed: {str(e)}")
                raise ValueError("Invalid or tampered pagination cursor")
            except Exception as e:
                logger.error(f"Unexpected cursor decoding error: {str(e)}", exc_info=True)
                raise ValueError("Failed to process pagination cursor")
        
        doc_id = cursor_data.end_doc_id if cursor_data.direction == "next" else cursor_data.start_doc_id
        
        actual_sort_direction = sort_direction
        if cursor_data.direction == "prev":
            actual_sort_direction = Query.ASCENDING if sort_direction == Query.DESCENDING else Query.DESCENDING
        
        async_query: AsyncQuery = self.collection_ref.order_by(order_by, direction=actual_sort_direction)
        
        if filters:
            for field_name, value in filters.items():
                if value is not None:
                    async_query = async_query.where(field_name, "==", value)
        
        if doc_id:
            cursor_doc = await self._get_document_ref(doc_id).get()
            if cursor_doc.exists:
                if cursor_data.direction == "next":
                    async_query = async_query.start_after(cursor_doc)
                else:
                    async_query = async_query.start_at(cursor_doc)
        
        updated_page_size = (page_size + 1) if page_size else None
        if updated_page_size:
            async_query = async_query.limit(updated_page_size)
        
        results: List[T] = await self._get_results_from_query(async_query)
        
        if cursor_data.direction == "prev":
            results.reverse()
        
        next_cursor = None
        prev_cursor = None
        has_more = False
        
        if page_size and len(results) > page_size:
            has_more = True
            results = results[:page_size]
        
        if results:
            current_start_id = results[0].id
            current_end_id = results[-1].id
            
            current_page = cursor_data.page
            if cursor_data.direction == "next" and cursor_data.end_doc_id:
                current_page = cursor_data.page + 1
            elif cursor_data.direction == "prev" and cursor_data.start_doc_id:
                current_page = max(0, cursor_data.page - 1)
            
            if has_more:
                next_cursor = cursor_encoder.encode_cursor_base64(
                    page=current_page,
                    start_doc_id=current_start_id,
                    end_doc_id=current_end_id,
                    direction="next"
                )
            
            if cursor and current_page > 0:
                prev_cursor = cursor_encoder.encode_cursor_base64(
                    page=current_page,
                    start_doc_id=current_start_id,
                    end_doc_id=current_end_id,
                    direction="prev"
                )
        
        return results, next_cursor, prev_cursor
