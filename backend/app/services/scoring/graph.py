from typing import Annotated, Any, Callable, TypedDict

from app.constants.roles import ROLE_WEIGHTS
from app.schemas.cv import CandidateProfile, ModuleScore, ScoreSummary
from app.services.scoring.modules import score_one
from app.services.scoring.utils import grade, score_tier


def merge_scores(left: list[ModuleScore] | None, right: list[ModuleScore] | None) -> list[ModuleScore]:
    return (left or []) + (right or [])


class CVState(TypedDict, total=False):
    profile: CandidateProfile
    modules: Annotated[list[ModuleScore], merge_scores]
    summary: ScoreSummary


def _node(module_key: str):
    def run(state: CVState) -> dict[str, Any]:
        profile = state["profile"]
        max_score = ROLE_WEIGHTS[profile.target_role].get(module_key, 0)
        if max_score <= 0:
            return {"modules": []}
        return {"modules": [score_one(module_key, profile, max_score)]}
    return run


def _module_by_key(modules: list[ModuleScore], key: str) -> ModuleScore | None:
    return next((module for module in modules if module.module_key == key), None)


def _role_project_count(profile: CandidateProfile) -> int:
    role_terms = {
        "backend": {"fastapi", "django", "flask", "node", "express", "spring", "postgres", "mysql", "redis", "api", "rest", "docker", "aws"},
        "frontend": {"react", "next", "vue", "angular", "typescript", "javascript", "css", "html", "accessibility", "responsive"},
        "full_stack": {"react", "next", "fastapi", "node", "postgres", "api", "docker", "aws", "typescript", "python"},
        "mobile": {"flutter", "react native", "kotlin", "swift", "android", "ios", "dart"},
        "ai_ml": {"python", "pytorch", "tensorflow", "scikit", "langchain", "langgraph", "rag", "huggingface", "bedrock", "mlflow"},
        "devops": {"aws", "docker", "kubernetes", "terraform", "ci/cd", "github actions", "linux", "monitoring", "nginx"},
        "data_engineer": {"sql", "spark", "kafka", "airflow", "dbt", "postgres", "warehouse", "python", "etl"},
        "data_scientist": {"python", "statistics", "pandas", "numpy", "scikit", "pytorch", "visualization", "experiment"},
        "qa_automation": {"selenium", "playwright", "cypress", "pytest", "jest", "postman", "ci/cd", "coverage"},
    }.get(profile.target_role, set())
    count = 0
    for project in profile.projects:
        text = f"{project.title} {project.description} {' '.join(project.technologies)}".lower().replace("-", " ")
        if any(term in text for term in role_terms):
            count += 1
    return count


def _quality(module: ModuleScore | None) -> float:
    return max(0.0, min((module.normalized_score if module else 0.0) / 100, 1.0))


def _delivery_quality(profile: CandidateProfile) -> float:
    if not profile.projects:
        return 0.0
    deployed = sum(1 for project in profile.projects if project.has_production_evidence)
    impact = sum(1 for project in profile.projects if project.has_measurable_impact)
    ownership = sum(1 for project in profile.projects if project.has_ownership_signal)
    project_count = max(1, min(len(profile.projects), 3))
    return max(0.0, min(((deployed / project_count) * 0.35 + (impact / project_count) * 0.40 + (ownership / project_count) * 0.25), 1.0))


def _calibrate_total(profile: CandidateProfile, modules: list[ModuleScore], raw_total: float) -> tuple[float, list[str], dict[str, Any]]:
    band_low = 0.0
    band_high = 100.0
    reasons: list[str] = []
    project_work = _module_by_key(modules, "project_work")
    role_fit = _module_by_key(modules, "role_fit")
    experience = _module_by_key(modules, "professional_experience")
    technical = _module_by_key(modules, "technical_skill")
    role_projects = _role_project_count(profile)
    months = profile.total_experience_months or 0
    career_stage = (profile.career_stage or profile.seniority_level or "").lower()
    has_deployed = any(project.has_production_evidence for project in profile.projects)
    severe_mismatch = bool(profile.projects and role_projects == 0)

    def set_band(low: float, high: float, reason: str) -> None:
        nonlocal band_low, band_high
        band_low = max(band_low, low)
        if high < band_high:
            band_high = high
            reasons.append(reason)

    if profile.extraction_confidence == "low":
        set_band(0, 55, "Low extraction confidence limits the final score.")
    if not profile.projects:
        set_band(0, 45, "No valid project evidence was extracted.")
    if severe_mismatch:
        set_band(0, 39, "Major selected-role mismatch detected: no valid project clearly aligns with the selected role.")
    if months == 0 and not has_deployed:
        set_band(0, 54, "No professional experience and no deployed project evidence were found.")

    if role_fit is not None:
        if role_fit.normalized_score < 35:
            severe_mismatch = True
            set_band(0, 39, "Major selected-role mismatch detected.")
        elif role_fit.normalized_score < 50:
            set_band(40, 54, "Partial selected-role mismatch detected.")

    if not severe_mismatch:
        if career_stage in {"intern", "student", "early"} or months < 6:
            set_band(40, 69, "Career stage is student/intern/early-career, so scoring is calibrated inside the entry-to-intern range.")
        elif months < 24:
            set_band(55, 79, "Experience is under 2 years, so scoring is calibrated inside the intern-to-junior range.")
        elif months < 60:
            set_band(70, 89, "Experience is 2-5 years, so scoring is calibrated inside the junior-to-mid range.")
        else:
            set_band(80, 100, "Experience is 5+ years, so senior-level scores require strong evidence quality.")

    if experience is not None and experience.normalized_score < 25 and raw_total > 70:
        set_band(0, 69, "Professional experience evidence is too limited for junior-or-higher readiness.")

    band_high = max(band_low, band_high)
    evidence_quality = max(0.0, min(
        (raw_total / 100) * 0.24
        + _quality(project_work) * 0.22
        + _quality(experience) * 0.18
        + _quality(role_fit) * 0.18
        + _quality(technical) * 0.12
        + _delivery_quality(profile) * 0.06,
        1.0,
    ))
    band_score = band_low + evidence_quality * (band_high - band_low)
    final = round(band_score, 2)
    final_tier = score_tier(final)
    details = {
        "career_band": final_tier,
        "calibration_band": {"min": round(band_low, 2), "max": round(band_high, 2)},
        "band_score": round(band_score, 2),
        "evidence_quality": round(evidence_quality, 4),
    }
    return final, reasons, details


def summarizer(state: CVState) -> dict[str, Any]:
    profile = state["profile"]
    modules = sorted(state.get("modules", []), key=lambda m: m.max_score, reverse=True)
    raw_total = round(sum(m.score for m in modules), 2)
    total, calibration_reasons, calibration_details = _calibrate_total(profile, modules, raw_total)
    overall_grade = grade(total)
    tier = score_tier(total)
    recommendation = str(tier["verdict"])

    strengths = []
    weaknesses = []
    recommendations = []
    for module in modules:
        if module.normalized_score >= 70:
            strengths.extend(module.evidence_found[:2])
        if module.normalized_score < 70:
            weaknesses.extend(module.missing_evidence[:2])
        recommendations.extend(module.recommendations[:1])
    weaknesses.extend(calibration_reasons)

    summary = ScoreSummary(
        target_role=profile.target_role,
        overall_score=total,
        overall_grade=overall_grade,
        hiring_recommendation=recommendation,
        aggregate_confidence="high" if all(m.confidence != "low" for m in modules[:4]) else "medium",
        top_strengths=list(dict.fromkeys(strengths))[:6],
        top_weaknesses=list(dict.fromkeys(weaknesses))[:6],
        recommendations=list(dict.fromkeys(recommendations))[:6],
        summary_narrative=f"This CV scores {total}/100 for the selected role: {overall_grade}. {recommendation}. The result is calibrated by module evidence, career stage, role alignment, and missing evidence.",
        raw_summary_json={
            "module_count": len(modules),
            "raw_total_before_calibration": raw_total,
            "career_band": calibration_details["career_band"],
            "band_score": calibration_details["band_score"],
            "evidence_quality": calibration_details["evidence_quality"],
            "calibration_band": calibration_details["calibration_band"],
            "calibration_reasons": calibration_reasons,
        },
    )
    return {"summary": summary}


try:
    from langgraph.graph import END, START, StateGraph

    _g = StateGraph(CVState)
    for key in ROLE_WEIGHTS["backend"].keys():
        _g.add_node(key, _node(key))
        _g.add_edge(START, key)
        _g.add_edge(key, "summarizers")
    _g.add_node("summarizers", summarizer)
    _g.add_edge("summarizers", END)
    app = _g.compile()
except Exception:
    app = None


ProgressCallback = Callable[[str, str | None, ModuleScore | None], None]


def _run_scoring_sequential(profile: CandidateProfile, progress_callback: ProgressCallback) -> tuple[list[ModuleScore], ScoreSummary]:
    modules: list[ModuleScore] = []
    for key, max_score in ROLE_WEIGHTS[profile.target_role].items():
        if max_score <= 0:
            continue
        progress_callback("module_start", key, None)
        module = score_one(key, profile, max_score)
        modules.append(module)
        progress_callback("module_complete", key, module)

    progress_callback("summarizer_start", None, None)
    result = summarizer({"profile": profile, "modules": modules})
    progress_callback("summarizer_complete", None, None)
    return modules, result["summary"]


def run_scoring_graph(profile: CandidateProfile, progress_callback: ProgressCallback | None = None) -> tuple[list[ModuleScore], ScoreSummary]:
    if progress_callback is not None:
        return _run_scoring_sequential(profile, progress_callback)

    if app is not None:
        result = app.invoke({"profile": profile, "modules": []})
        return result["modules"], result["summary"]

    modules = [
        score_one(key, profile, max_score)
        for key, max_score in ROLE_WEIGHTS[profile.target_role].items()
        if max_score > 0
    ]
    result = summarizer({"profile": profile, "modules": modules})
    return modules, result["summary"]
