import json
import logging
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.schemas.cv import CandidatePipelineStatus, CandidateResult, PipelineStage
from app.services.category_views import apply_workspace_fields, build_category_views
from app.services.extractor import extract_profile
from app.services.pdf_parser import extract_pdf_text
from app.services.score_cache import SCORE_CACHE_TTL_SECONDS, load_cached_score, store_score_cache
from app.services.scoring.graph import run_scoring_graph
from app.services.supabase_scores import compute_cv_hash, persist_candidate_score


logger = logging.getLogger("devlens.pipeline")

STAGE_DEFINITIONS = [
    ("cv_upload", "CV Upload", "Waiting for CV upload."),
    ("extraction", "Extraction Agent", "Waiting for extraction agent."),
    ("scoring", "Scoring Agent", "Waiting for scoring agent."),
    ("summarizer", "Summarizer Agent", "Waiting for summarizer agent."),
    ("results_ready", "Results Ready", "Waiting for final results."),
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _result_path(candidate_id: str) -> Path:
    return get_settings().storage_dir / f"{candidate_id}.json"


def _status_path(candidate_id: str) -> Path:
    jobs = get_settings().storage_dir / "jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    return jobs / f"{candidate_id}.json"


def _default_stages() -> list[PipelineStage]:
    return [
        PipelineStage(key=key, label=label, status="idle", message=message)
        for key, label, message in STAGE_DEFINITIONS
    ]


def _stage_map(status: CandidatePipelineStatus) -> dict[str, PipelineStage]:
    return {stage.key: stage for stage in status.stages}


def save_pipeline_status(status: CandidatePipelineStatus) -> CandidatePipelineStatus:
    status.updated_at = _utc_now()
    _status_path(status.candidate_id).write_text(status.model_dump_json(indent=2), encoding="utf-8")
    return status


def create_pipeline_status(candidate_id: str, target_role: str) -> CandidatePipelineStatus:
    now = _utc_now()
    status = CandidatePipelineStatus(
        candidate_id=candidate_id,
        status="queued",
        target_role=target_role,
        stages=_default_stages(),
        created_at=now,
        updated_at=now,
    )
    return save_pipeline_status(status)


def load_pipeline_status(candidate_id: str) -> CandidatePipelineStatus | None:
    path = _status_path(candidate_id)
    if not path.exists():
        return None
    return CandidatePipelineStatus.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _ensure_pipeline_status(candidate_id: str, target_role: str) -> CandidatePipelineStatus:
    return load_pipeline_status(candidate_id) or create_pipeline_status(candidate_id, target_role)


def update_stage(
    candidate_id: str,
    stage_key: str,
    stage_status: str,
    message: str,
    *,
    target_role: str | None = None,
) -> CandidatePipelineStatus:
    status = load_pipeline_status(candidate_id)
    if status is None:
        status = create_pipeline_status(candidate_id, target_role or "")
    if target_role and not status.target_role:
        status.target_role = target_role
    status.status = "processing" if stage_status != "error" else "error"
    stages = _stage_map(status)
    stage = stages.get(stage_key)
    if stage is None:
        stage = PipelineStage(key=stage_key, label=stage_key.replace("_", " ").title())
        status.stages.append(stage)

    stage.status = stage_status  # type: ignore[assignment]
    stage.message = message
    if stage_status == "in_progress" and not stage.started_at:
        stage.started_at = _utc_now()
    if stage_status in {"completed", "error"}:
        stage.completed_at = _utc_now()
    if stage_status == "error":
        status.error_message = message
    return save_pipeline_status(status)


def mark_pipeline_complete(candidate_id: str, result: CandidateResult) -> CandidatePipelineStatus:
    status = load_pipeline_status(candidate_id) or create_pipeline_status(candidate_id, result.profile.target_role)
    status.status = "complete"
    status.error_message = None
    status.overall_score = result.summary.overall_score
    status.overall_grade = result.summary.overall_grade
    stages = _stage_map(status)
    for key, label, _ in STAGE_DEFINITIONS:
        stage = stages.get(key)
        if stage is None:
            stage = PipelineStage(key=key, label=label)
            status.stages.append(stage)
            stages[key] = stage
        stage.status = "completed"
        stage.completed_at = stage.completed_at or _utc_now()
    stages["results_ready"].message = "Results are ready for review."
    return save_pipeline_status(status)


def mark_pipeline_error(candidate_id: str, stage_key: str, message: str, *, target_role: str | None = None) -> CandidatePipelineStatus:
    status = update_stage(candidate_id, stage_key, "error", message, target_role=target_role)
    status.status = "error"
    status.error_message = message
    return save_pipeline_status(status)


def status_from_result(result: CandidateResult) -> CandidatePipelineStatus:
    now = _utc_now()
    return CandidatePipelineStatus(
        candidate_id=result.candidate_id,
        status="complete",
        target_role=result.profile.target_role,
        stages=[
            PipelineStage(key=key, label=label, status="completed", message="Completed.", completed_at=now)
            for key, label, _ in STAGE_DEFINITIONS
        ],
        overall_score=result.summary.overall_score,
        overall_grade=result.summary.overall_grade,
        created_at=now,
        updated_at=now,
    )


def process_cv(pdf_path: Path, target_role: str, candidate_id: str | None = None, *, track_status: bool = True) -> CandidateResult:
    candidate_id = candidate_id or str(uuid.uuid4())
    started = time.perf_counter()
    current_stage = "extraction"
    if track_status:
        _ensure_pipeline_status(candidate_id, target_role)
    logger.info("CV pipeline started candidate_id=%s target_role=%s", candidate_id, target_role)
    try:
        if track_status:
            update_stage(candidate_id, "extraction", "in_progress", "Parsing CV text and extracting structured profile.", target_role=target_role)
        logger.info("Extraction started candidate_id=%s", candidate_id)
        raw_text = extract_pdf_text(pdf_path)
        cv_hash = compute_cv_hash(raw_text)
        cached_result = load_cached_score(cv_hash, target_role, candidate_id)
        if cached_result:
            logger.info(
                "CV score cache hit candidate_id=%s target_role=%s cv_hash=%s",
                candidate_id,
                target_role,
                cv_hash[:12],
            )
            _result_path(candidate_id).write_text(cached_result.model_dump_json(indent=2), encoding="utf-8")
            if track_status:
                update_stage(candidate_id, "extraction", "completed", "CV matched a cached score.", target_role=target_role)
                update_stage(candidate_id, "scoring", "completed", "Cached CV score reused.", target_role=target_role)
                update_stage(candidate_id, "summarizer", "completed", "Cached summary reused.", target_role=target_role)
                update_stage(candidate_id, "results_ready", "completed", "Results are ready for review.", target_role=target_role)
                mark_pipeline_complete(candidate_id, cached_result)
            duration = time.perf_counter() - started
            logger.info(
                "CV pipeline completed from cache candidate_id=%s overall_score=%.2f grade=%s duration_seconds=%.2f",
                candidate_id,
                cached_result.summary.overall_score,
                cached_result.summary.overall_grade,
                duration,
            )
            return cached_result

        logger.info(
            "CV score cache miss candidate_id=%s target_role=%s cv_hash=%s",
            candidate_id,
            target_role,
            cv_hash[:12],
        )
        profile = extract_profile(raw_text, target_role)
        logger.info(
            "Extraction completed candidate_id=%s confidence=%s projects=%s skills=%s",
            candidate_id,
            profile.extraction_confidence,
            len(profile.projects),
            len(profile.programming_languages) + len(profile.frameworks_libraries) + len(profile.ml_ai_tools),
        )
        if track_status:
            update_stage(candidate_id, "extraction", "completed", "Structured profile extracted from the CV.", target_role=target_role)

        current_stage = "scoring"
        if track_status:
            update_stage(candidate_id, "scoring", "in_progress", "Scoring is running across all categories.", target_role=target_role)
        logger.info("Scoring started candidate_id=%s", candidate_id)

        modules, summary = run_scoring_graph(profile)
        logger.info("Scoring completed candidate_id=%s module_count=%s", candidate_id, len(modules))
        current_stage = "summarizer"
        logger.info("Summarizer completed candidate_id=%s", candidate_id)
        if track_status:
            update_stage(candidate_id, "scoring", "completed", "All scoring categories completed in parallel.", target_role=target_role)
            update_stage(candidate_id, "summarizer", "completed", "Final summary generated.", target_role=target_role)
        category_views = build_category_views(profile, modules)
        result = CandidateResult(**apply_workspace_fields(
            candidate_id=candidate_id,
            profile=profile,
            summary=summary,
            modules=modules,
            category_views=category_views,
        ))
        _result_path(candidate_id).write_text(result.model_dump_json(indent=2), encoding="utf-8")
        if store_score_cache(cv_hash, target_role, result):
            logger.info(
                "CV score cached in Redis candidate_id=%s target_role=%s cv_hash=%s ttl_seconds=%s",
                candidate_id,
                target_role,
                cv_hash[:12],
                SCORE_CACHE_TTL_SECONDS,
            )
        try:
            persisted = persist_candidate_score(result)
            if persisted:
                logger.info(
                    "CV score persisted to Supabase candidate_id=%s user_id=%s cv_hash=%s",
                    candidate_id,
                    persisted.user_id,
                    persisted.cv_hash[:12],
                )
        except Exception:
            logger.warning("CV score Supabase persistence failed candidate_id=%s", candidate_id, exc_info=True)
        if track_status:
            update_stage(candidate_id, "results_ready", "completed", "Results are ready for review.", target_role=target_role)
            mark_pipeline_complete(candidate_id, result)
        duration = time.perf_counter() - started
        logger.info(
            "CV pipeline completed candidate_id=%s overall_score=%.2f grade=%s duration_seconds=%.2f",
            candidate_id,
            result.summary.overall_score,
            result.summary.overall_grade,
            duration,
        )
        return result
    except Exception as exc:
        safe_message = f"CV scoring failed during {current_stage}."
        if track_status:
            mark_pipeline_error(candidate_id, current_stage, safe_message, target_role=target_role)
        logger.exception("CV pipeline failed candidate_id=%s stage=%s error=%s", candidate_id, current_stage, type(exc).__name__)
        raise


def save_upload(fileobj, filename: str) -> Path:
    uploads = get_settings().storage_dir / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix or ".pdf"
    path = uploads / f"{uuid.uuid4()}{suffix}"
    with path.open("wb") as out:
        shutil.copyfileobj(fileobj, out)
    logger.info("CV upload saved upload_file=%s", path.name)
    return path


def load_result(candidate_id: str) -> CandidateResult | None:
    path = _result_path(candidate_id)
    if not path.exists():
        return None
    result = CandidateResult.model_validate(json.loads(path.read_text(encoding="utf-8")))
    if not result.category_views:
        result.category_views = build_category_views(result.profile, result.modules)
    if not result.categories or result.total_score is None or result.role_fit_score is None:
        result = CandidateResult(**apply_workspace_fields(
            candidate_id=result.candidate_id,
            profile=result.profile,
            summary=result.summary,
            modules=result.modules,
            category_views=result.category_views,
        ))
    return result
