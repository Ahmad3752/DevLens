import hashlib
import json
import logging
import re
from typing import Any

import httpx

from app.config import get_settings
from app.constants.roles import ROLE_LABELS
from app.schemas.cv import CandidateProfile
from app.schemas.jobs import CacheStatus, JobFilters, RelevantJob


logger = logging.getLogger("devlens.jobs")

JOBS_CACHE_TTL_SECONDS = 30 * 60
JOB_SELECT_COLUMNS = ",".join([
    "id",
    "title",
    "company",
    "url",
    "platform",
    "platforms",
    "location_raw",
    "city",
    "country",
    "role_keys",
    "role_labels",
    "employment_type",
    "experience_level",
    "is_internship",
    "is_remote",
    "workplace_type",
    "tech_stack",
    "requirements",
    "responsibilities",
    "benefits",
    "salary_min",
    "salary_max",
    "salary_currency",
    "salary_period",
    "salary_raw",
    "posted_at",
    "scraped_at",
])

_SAFE_ARRAY_CHARS = re.compile(r"[^A-Za-z0-9_ .+#/-]")


class JobsConfigurationError(RuntimeError):
    pass


def normalize_filter_text(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def build_job_filters(
    *,
    employment_type: str | None = None,
    experience_level: str | None = None,
    workplace_type: str | None = None,
    limit: int = 50,
) -> JobFilters:
    safe_limit = max(1, min(int(limit or 50), 100))
    return JobFilters(
        employment_type=normalize_filter_text(employment_type),
        experience_level=normalize_filter_text(experience_level),
        workplace_type=normalize_filter_text(workplace_type),
        limit=safe_limit,
    )


def build_jobs_cache_key(role_key: str, filters: JobFilters) -> str:
    payload = filters.model_dump(mode="json")
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
    return f"devlens:jobs:{_slug(role_key)}:all:{digest}"


def build_supabase_params(role_key: str, filters: JobFilters) -> dict[str, str]:
    params = {
        "select": JOB_SELECT_COLUMNS,
        "is_active": "eq.true",
        "country": "eq.Pakistan",
        "role_keys": f"cs.{_array_literal([role_key])}",
        "order": "posted_at.desc.nullslast,scraped_at.desc",
        "limit": str(filters.limit),
    }
    if filters.employment_type:
        params["employment_type"] = f"eq.{filters.employment_type}"
    if filters.experience_level:
        params["experience_level"] = f"eq.{filters.experience_level}"
    if filters.workplace_type:
        params["workplace_type"] = f"eq.{filters.workplace_type}"
    return params


def fetch_relevant_jobs(
    candidate_id: str,
    profile: CandidateProfile,
    filters: JobFilters,
    *,
    http_client: httpx.Client | None = None,
    redis_client: Any | None = None,
) -> tuple[list[RelevantJob], CacheStatus, dict[str, Any]]:
    if profile.target_role not in ROLE_LABELS:
        raise ValueError(f"Unsupported target role '{profile.target_role}'")

    rows, cache_status = _load_job_rows(profile.target_role, filters, http_client=http_client, redis_client=redis_client)
    jobs = [_normalize_job(row) for row in rows]
    jobs.sort(key=_freshness_key, reverse=True)
    return jobs, cache_status, {"source_rows": len(rows)}


def _load_job_rows(
    role_key: str,
    filters: JobFilters,
    *,
    http_client: httpx.Client | None,
    redis_client: Any | None,
) -> tuple[list[dict[str, Any]], CacheStatus]:
    settings = get_settings()
    cache_key = build_jobs_cache_key(role_key, filters)
    cache_status: CacheStatus = "disabled"
    redis_conn = redis_client if redis_client is not None else _get_redis_client(settings)

    if redis_conn is not None:
        try:
            cached = redis_conn.get(cache_key)
            if cached:
                return json.loads(cached), "hit"
            cache_status = "miss"
        except Exception:
            cache_status = "error"
            logger.warning("Jobs cache read failed key=%s", cache_key, exc_info=True)

    rows = _query_supabase_jobs(role_key, filters, http_client=http_client)

    if redis_conn is not None:
        try:
            redis_conn.setex(cache_key, JOBS_CACHE_TTL_SECONDS, json.dumps(rows, default=str))
        except Exception:
            cache_status = "error"
            logger.warning("Jobs cache write failed key=%s", cache_key, exc_info=True)

    return rows, cache_status


def _query_supabase_jobs(role_key: str, filters: JobFilters, *, http_client: httpx.Client | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise JobsConfigurationError("Supabase jobs configuration is missing.")

    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }
    params = build_supabase_params(role_key, filters)
    url = f"{settings.supabase_url}/rest/v1/jobs"

    if http_client is not None:
        response = http_client.get(url, params=params, headers=headers)
    else:
        with httpx.Client(timeout=12) as client:
            response = client.get(url, params=params, headers=headers)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError("Supabase jobs response was not a list.")
    return [row for row in payload if isinstance(row, dict)]


def _normalize_job(row: dict[str, Any]) -> RelevantJob:
    job_skills = _clean_list(row.get("tech_stack"))
    requirement_terms = _clean_list(row.get("requirements"))

    payload = {
        **row,
        "id": str(row.get("id") or ""),
        "title": str(row.get("title") or "Untitled role"),
        "company": str(row.get("company") or "Unknown company"),
        "url": str(row.get("url") or ""),
        "platform": str(row.get("platform") or "unknown"),
        "platforms": _clean_list(row.get("platforms")),
        "country": str(row.get("country") or "Pakistan"),
        "role_keys": _clean_list(row.get("role_keys")),
        "role_labels": _clean_list(row.get("role_labels")),
        "employment_type": str(row.get("employment_type") or "unknown"),
        "experience_level": str(row.get("experience_level") or "unknown"),
        "is_internship": bool(row.get("is_internship", False)),
        "is_remote": bool(row.get("is_remote", False)),
        "workplace_type": str(row.get("workplace_type") or "unknown"),
        "tech_stack": job_skills,
        "requirements": requirement_terms,
        "responsibilities": _clean_list(row.get("responsibilities")),
        "benefits": _clean_list(row.get("benefits")),
        "salary_period": str(row.get("salary_period") or "unknown"),
    }
    return RelevantJob.model_validate(payload)


def _freshness_key(job: RelevantJob) -> tuple[int, str, str]:
    return (1 if job.posted_at else 0, job.posted_at or "", job.scraped_at or "")


def _get_redis_client(settings) -> Any | None:
    redis_url = settings.devlens_redis_url or settings.redis_url
    if not redis_url:
        return None
    try:
        import redis
    except ImportError:
        logger.info("Redis package is not installed; jobs cache disabled.")
        return None
    try:
        return redis.from_url(redis_url, decode_responses=True, socket_timeout=5, socket_connect_timeout=5)
    except Exception:
        logger.warning("Redis client setup failed; jobs cache disabled.", exc_info=True)
        return None


def _array_literal(values: list[str]) -> str:
    cleaned = []
    for value in values:
        safe = _SAFE_ARRAY_CHARS.sub("", str(value or "").strip())
        if safe:
            cleaned.append(safe)
    return "{" + ",".join(cleaned) + "}"


def _clean_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item or "").strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _slug(value: str) -> str:
    text = str(value or "").casefold().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "all"
