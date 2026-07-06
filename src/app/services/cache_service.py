import asyncio, logging

from fastapi_cache import FastAPICache

from app.config import load_cache_config

logger = logging.getLogger(__name__)
cache_config = load_cache_config()

class CacheService:

    async def invalidate_course_list_cache(self) -> None:
        if cache_config.course_list_ttl_seconds <= 0:
            return

        try:
            clear_fn = getattr(FastAPICache, "clear", None)
            if callable(clear_fn):
                result = clear_fn(namespace=cache_config.course_list_namespace)
                if asyncio.iscoroutine(result):
                    await result
                return
            try:
                backend = FastAPICache.get_backend()
            except Exception:
                return
            if backend is None:
                return
            result = backend.clear(namespace=cache_config.course_list_namespace)
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:
            logger.warning("Failed to clear course list cache: %s", exc, exc_info=True)
