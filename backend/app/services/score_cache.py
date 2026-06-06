import json
import logging
import re
from typing import Any

from app.config import get_settings
from app.schemas.cv import CandidateResult


logger = logging.getLogger("devlens.score_cache")

SCORE_CACHE_TTL_SECONDS = 60 * 60 * 24 * 7


def build_score_cache_key(cv_hash: str, role_key: str) -> str:
    return f"devlens:score:{cv_hash}:{_slug(role_key)}"


def load_cached_score(
    cv_hash: str,
    role_key: str,
    candidate_id: str,
    *,
    redis_client: Any | None = None,
) -> CandidateResult | None:
    redis_conn = redis_client if redis_client is not None else _get_redis_client()
    if redis_conn is None:
        return None

    key = build_score_cache_key(cv_hash, role_key)
    try:
        cached = redis_conn.get(key)
        if not cached:
            return None
        result = CandidateResult.model_validate(json.loads(cached))
        return result.model_copy(update={"candidate_id": candidate_id})
    except Exception:
        logger.warning("CV score cache read failed key=%s", key, exc_info=True)
        return None


def store_score_cache(
    cv_hash: str,
    role_key: str,
    result: CandidateResult,
    *,
    redis_client: Any | None = None,
) -> bool:
    redis_conn = redis_client if redis_client is not None else _get_redis_client()
    if redis_conn is None:
        return False

    key = build_score_cache_key(cv_hash, role_key)
    try:
        redis_conn.setex(key, SCORE_CACHE_TTL_SECONDS, result.model_dump_json())
        return True
    except Exception:
        logger.warning("CV score cache write failed key=%s", key, exc_info=True)
        return False


def _get_redis_client() -> Any | None:
    settings = get_settings()
    redis_url = getattr(settings, "devlens_redis_url", None) or getattr(settings, "redis_url", None)
    if not redis_url:
        return None
    try:
        import redis
    except ImportError:
        logger.info("Redis package is not installed; CV score cache disabled.")
        return None
    try:
        return redis.from_url(redis_url, decode_responses=True, socket_timeout=5, socket_connect_timeout=5)
    except Exception:
        logger.warning("Redis client setup failed; CV score cache disabled.", exc_info=True)
        return None


def _slug(value: str) -> str:
    text = str(value or "").casefold().strip()
    text = re.sub(r"[^a-z0-9_]+", "-", text)
    return text.strip("-") or "unknown"
