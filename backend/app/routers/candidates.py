import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.constants.roles import ROLE_LABELS
from app.schemas.cv import CandidatePipelineStatus, CandidateResult
from app.services.pipeline import (
    create_pipeline_status,
    load_pipeline_status,
    load_result,
    mark_pipeline_error,
    process_cv,
    save_upload,
    status_from_result,
    update_stage,
)


router = APIRouter()
logger = logging.getLogger("devlens.api")


@router.get("/roles")
def roles():
    return {"roles": [{"key": key, "label": label} for key, label in ROLE_LABELS.items()]}


def _validate_upload(file: UploadFile, target_role: str) -> None:
    if target_role not in ROLE_LABELS:
        raise HTTPException(status_code=400, detail=f"Unsupported target_role '{target_role}'")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF CV.")


def _process_background(path, target_role: str, candidate_id: str) -> None:
    try:
        process_cv(path, target_role, candidate_id)
    except Exception:
        logger.exception("Background CV scoring failed candidate_id=%s", candidate_id)


@router.post("/candidates/upload", response_model=CandidateResult)
def upload_candidate(file: UploadFile = File(...), target_role: str = Form(...)):
    _validate_upload(file, target_role)
    candidate_id = str(uuid.uuid4())
    create_pipeline_status(candidate_id, target_role)
    logger.info("CV upload received candidate_id=%s target_role=%s mode=sync", candidate_id, target_role)
    update_stage(candidate_id, "cv_upload", "in_progress", "Receiving CV upload.", target_role=target_role)
    path = save_upload(file.file, file.filename)
    update_stage(candidate_id, "cv_upload", "completed", "CV uploaded successfully.", target_role=target_role)
    try:
        return process_cv(path, target_role, candidate_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CV scoring failed: {exc}") from exc


@router.post("/candidates/upload/start", response_model=CandidatePipelineStatus)
def start_candidate_upload(background_tasks: BackgroundTasks, file: UploadFile = File(...), target_role: str = Form(...)):
    _validate_upload(file, target_role)
    candidate_id = str(uuid.uuid4())
    create_pipeline_status(candidate_id, target_role)
    logger.info("CV upload received candidate_id=%s target_role=%s mode=async", candidate_id, target_role)
    update_stage(candidate_id, "cv_upload", "in_progress", "Receiving CV upload.", target_role=target_role)
    try:
        path = save_upload(file.file, file.filename)
        status = update_stage(candidate_id, "cv_upload", "completed", "CV uploaded successfully.", target_role=target_role)
    except Exception as exc:
        mark_pipeline_error(candidate_id, "cv_upload", "CV upload failed.", target_role=target_role)
        raise HTTPException(status_code=500, detail=f"CV upload failed: {exc}") from exc

    background_tasks.add_task(_process_background, path, target_role, candidate_id)
    return status


@router.get("/candidates/{candidate_id}/scores", response_model=CandidateResult)
def get_scores(candidate_id: str):
    result = load_result(candidate_id)
    if not result:
        raise HTTPException(status_code=404, detail="Candidate result not found")
    return result


@router.get("/candidates/{candidate_id}/status", response_model=CandidatePipelineStatus)
def get_status(candidate_id: str):
    status = load_pipeline_status(candidate_id)
    if status:
        return status
    result = load_result(candidate_id)
    if not result:
        return CandidatePipelineStatus(candidate_id=candidate_id, status="not_found")
    return status_from_result(result)
