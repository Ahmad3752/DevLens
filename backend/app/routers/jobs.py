import logging

from fastapi import APIRouter, HTTPException, Query
from httpx import HTTPError

from app.constants.roles import ROLE_LABELS
from app.schemas.jobs import CandidateJobsResponse
from app.services.jobs import JobsConfigurationError, build_job_filters, fetch_relevant_jobs
from app.services.pipeline import load_result


router = APIRouter(prefix="/candidates", tags=["Relevant Jobs"])
logger = logging.getLogger("devlens.api.jobs")


@router.get("/{candidate_id}/jobs", response_model=CandidateJobsResponse)
def get_candidate_jobs(
    candidate_id: str,
    employment_type: str | None = Query(default=None),
    experience_level: str | None = Query(default=None),
    workplace_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
):
    result = load_result(candidate_id)
    if not result:
        raise HTTPException(status_code=404, detail="Candidate result not found")

    role_key = result.profile.target_role
    if role_key not in ROLE_LABELS:
        raise HTTPException(status_code=400, detail=f"Unsupported target role '{role_key}'")

    filters = build_job_filters(
        employment_type=employment_type,
        experience_level=experience_level,
        workplace_type=workplace_type,
        limit=limit,
    )

    try:
        jobs, cache_status, metadata = fetch_relevant_jobs(candidate_id, result.profile, filters)
    except JobsConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HTTPError as exc:
        logger.warning("Supabase jobs request failed candidate_id=%s", candidate_id, exc_info=True)
        raise HTTPException(status_code=502, detail="Could not load relevant jobs from Supabase.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return CandidateJobsResponse(
        candidate_id=candidate_id,
        role_key=role_key,
        role_label=ROLE_LABELS[role_key],
        filters=filters,
        cache_status=cache_status,
        jobs=jobs,
        metadata=metadata,
    )
