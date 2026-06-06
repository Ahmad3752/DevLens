import hashlib
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import get_settings
from app.constants.roles import ROLE_LABELS
from app.schemas.cv import CandidateProfile, CandidateResult


logger = logging.getLogger("devlens.supabase_scores")


@dataclass(frozen=True)
class SupabaseScorePersistenceResult:
    user_id: str
    cv_score_id: str | None
    cv_hash: str


class SupabaseScorePersistenceError(RuntimeError):
    pass


def persist_candidate_score(
    result: CandidateResult,
    *,
    http_client: httpx.Client | None = None,
) -> SupabaseScorePersistenceResult | None:
    settings = get_settings()
    supabase_url = getattr(settings, "supabase_url", None)
    service_key = getattr(settings, "supabase_service_role_key", None)
    if not supabase_url or not service_key:
        logger.info("Supabase score persistence skipped because configuration is missing.")
        return None

    owns_client = http_client is None
    client = http_client or httpx.Client(timeout=12)
    try:
        headers = _headers(service_key)
        user = _get_or_create_user(client, supabase_url, headers, result.profile)
        cv_hash = compute_cv_hash(result.profile.raw_cv_text)
        score = _upsert_cv_score(client, supabase_url, headers, user["id"], cv_hash, result)
        return SupabaseScorePersistenceResult(
            user_id=str(user["id"]),
            cv_score_id=str(score.get("id")) if score else None,
            cv_hash=cv_hash,
        )
    finally:
        if owns_client:
            client.close()


def compute_cv_hash(raw_cv_text: str) -> str:
    normalized = "\n".join(line.strip() for line in str(raw_cv_text or "").splitlines() if line.strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _get_or_create_user(client: httpx.Client, supabase_url: str, headers: dict[str, str], profile: CandidateProfile) -> dict[str, Any]:
    email = _clean(profile.email)
    full_name = _clean(profile.name)
    role_key = profile.target_role

    if email:
        existing = _fetch_user_by_email(client, supabase_url, headers, email)
        if existing:
            return _update_user_preferences(client, supabase_url, headers, existing, full_name, role_key)

    payload = {
        "email": email,
        "full_name": full_name,
        "role_preferences": [role_key] if role_key else [],
    }
    response = client.post(
        f"{supabase_url}/rest/v1/users",
        params={"select": "id,email,full_name,role_preferences"},
        headers={**headers, "Prefer": "return=representation"},
        json=payload,
    )
    if response.status_code == 409 and email:
        existing = _fetch_user_by_email(client, supabase_url, headers, email)
        if existing:
            return _update_user_preferences(client, supabase_url, headers, existing, full_name, role_key)
    response.raise_for_status()
    rows = response.json()
    if not rows:
        raise SupabaseScorePersistenceError("Supabase user insert returned no rows.")
    return rows[0]


def _fetch_user_by_email(client: httpx.Client, supabase_url: str, headers: dict[str, str], email: str) -> dict[str, Any] | None:
    response = client.get(
        f"{supabase_url}/rest/v1/users",
        params={
            "select": "id,email,full_name,role_preferences",
            "email": f"eq.{email}",
            "limit": "1",
        },
        headers=headers,
    )
    response.raise_for_status()
    rows = response.json()
    return rows[0] if rows else None


def _update_user_preferences(
    client: httpx.Client,
    supabase_url: str,
    headers: dict[str, str],
    user: dict[str, Any],
    full_name: str | None,
    role_key: str,
) -> dict[str, Any]:
    preferences = list(user.get("role_preferences") or [])
    if role_key and role_key not in preferences:
        preferences.append(role_key)

    payload: dict[str, Any] = {"role_preferences": preferences}
    if full_name and not _clean(user.get("full_name")):
        payload["full_name"] = full_name

    response = client.patch(
        f"{supabase_url}/rest/v1/users",
        params={"id": f"eq.{user['id']}", "select": "id,email,full_name,role_preferences"},
        headers={**headers, "Prefer": "return=representation"},
        json=payload,
    )
    response.raise_for_status()
    rows = response.json()
    return rows[0] if rows else {**user, **payload}


def _upsert_cv_score(
    client: httpx.Client,
    supabase_url: str,
    headers: dict[str, str],
    user_id: str,
    cv_hash: str,
    result: CandidateResult,
) -> dict[str, Any]:
    payload = {
        "user_id": user_id,
        "cv_hash": cv_hash,
        "role_key": result.profile.target_role,
        "role_label": ROLE_LABELS.get(result.profile.target_role, result.profile.target_role),
        "score": result.summary.overall_score,
        "matched_skills": _candidate_skills(result.profile),
        "missing_skills": _missing_evidence(result),
        "recommendations": _recommendations_payload(result),
    }
    response = client.post(
        f"{supabase_url}/rest/v1/cv_scores",
        params={
            "on_conflict": "user_id,cv_hash,role_key",
            "select": "id,user_id,cv_hash,role_key,score",
        },
        headers={**headers, "Prefer": "resolution=merge-duplicates,return=representation"},
        json=payload,
    )
    response.raise_for_status()
    rows = response.json()
    return rows[0] if rows else {}


def _candidate_skills(profile: CandidateProfile) -> list[str]:
    values = [
        *profile.programming_languages,
        *profile.frameworks_libraries,
        *profile.databases,
        *profile.cloud_devops_tools,
        *profile.testing_tools,
        *profile.ml_ai_tools,
        *profile.architecture_practices,
        *profile.other_skills,
    ]
    seen: set[str] = set()
    skills: list[str] = []
    for value in values:
        skill = str(value or "").strip()
        key = skill.casefold()
        if skill and key not in seen:
            seen.add(key)
            skills.append(skill)
    return skills[:60]


def _missing_evidence(result: CandidateResult) -> list[str]:
    values: list[str] = []
    for category in result.categories:
        values.extend(category.missing_evidence[:3])
    if not values:
        for module in result.modules:
            values.extend(module.missing_evidence[:3])
    return list(dict.fromkeys(str(value) for value in values if str(value or "").strip()))[:60]


def _recommendations_payload(result: CandidateResult) -> dict[str, Any]:
    return {
        "candidate_id": result.candidate_id,
        "overall_grade": result.summary.overall_grade,
        "hiring_recommendation": result.summary.hiring_recommendation,
        "top_strengths": result.summary.top_strengths,
        "top_weaknesses": result.summary.top_weaknesses,
        "recommendations": result.summary.recommendations,
        "category_recommendations": [
            {
                "key": category.key,
                "name": category.name,
                "score": category.normalized_score,
                "recommendations": category.recommendations,
                "missing_evidence": category.missing_evidence,
            }
            for category in result.categories
        ],
    }


def _headers(service_key: str) -> dict[str, str]:
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
