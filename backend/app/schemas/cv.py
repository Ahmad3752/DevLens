from typing import Any, Literal
from pydantic import BaseModel, Field


Confidence = Literal["low", "medium", "high"]


class Project(BaseModel):
    title: str = "Untitled project"
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    evidence_source: str | None = None
    has_production_evidence: bool = False
    has_measurable_impact: bool = False
    has_ownership_signal: bool = False
    impact_description: str | None = None
    github_url: str | None = None
    live_url: str | None = None
    duration_months: int | None = None
    complexity_level: Literal["low", "medium", "high", "very_high"] = "medium"


class Publication(BaseModel):
    title: str
    venue: str | None = None
    type: str | None = None
    year: int | None = None
    authorship_role: str | None = None
    is_indexed: bool = False
    indexing: str | None = None


class CandidateProfile(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    other_links: list[dict[str, str]] = Field(default_factory=list)
    target_role: str
    raw_cv_text: str
    programming_languages: list[str] = Field(default_factory=list)
    frameworks_libraries: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    cloud_devops_tools: list[str] = Field(default_factory=list)
    testing_tools: list[str] = Field(default_factory=list)
    ml_ai_tools: list[str] = Field(default_factory=list)
    architecture_practices: list[str] = Field(default_factory=list)
    other_skills: list[str] = Field(default_factory=list)
    seniority_level: str | None = None
    total_experience_months: int = 0
    current_role: str | None = None
    current_company: str | None = None
    career_stage: str | None = None
    projects: list[Project] = Field(default_factory=list)
    highest_degree: str | None = None
    degree_field: str | None = None
    degree_institution: str | None = None
    degree_is_cs_related: bool = False
    certifications: list[str] = Field(default_factory=list)
    publications: list[Publication] = Field(default_factory=list)
    has_github: bool = False
    has_portfolio: bool = False
    has_deployed_projects: bool = False
    extraction_confidence: Confidence = "medium"
    extraction_warnings: list[str] = Field(default_factory=list)
    raw_extraction_json: dict[str, Any] = Field(default_factory=dict)


class ModuleScore(BaseModel):
    module_key: str
    module_label: str
    score: float
    max_score: float
    normalized_score: float
    grade: str
    confidence: Confidence = "medium"
    evidence_found: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    sub_scores: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    llm_reasoning: str = ""
    scoring_method: Literal["llm", "deterministic", "hybrid"] = "deterministic"
    raw_module_json: dict[str, Any] = Field(default_factory=dict)


class ScoreSummary(BaseModel):
    target_role: str
    overall_score: float
    overall_grade: str
    hiring_recommendation: str
    aggregate_confidence: Confidence
    top_strengths: list[str] = Field(default_factory=list)
    top_weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    summary_narrative: str
    raw_summary_json: dict[str, Any] = Field(default_factory=dict)


class ExtractedCategoryItem(BaseModel):
    title: str
    subtitle: str | None = None
    body: str = ""
    meta: list[str] = Field(default_factory=list)
    badges: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class CategoryView(BaseModel):
    key: str
    label: str
    score: float
    max_score: float
    normalized_score: float
    grade: str
    verdict: str
    confidence: Confidence = "medium"
    scoring_method: Literal["llm", "deterministic", "hybrid"] = "deterministic"
    extracted_items: list[ExtractedCategoryItem] = Field(default_factory=list)
    evidence_found: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    sub_scores: dict[str, Any] = Field(default_factory=dict)
    score_narrative: str = ""


class WorkspaceCategory(BaseModel):
    key: str
    name: str
    normalized_score: float
    weight: float | None = None
    grade_label: str
    verdict_sentence: str
    extracted_items: list[ExtractedCategoryItem] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    score_narrative: str = ""
    sub_scores: dict[str, Any] = Field(default_factory=dict)


class CandidateResult(BaseModel):
    candidate_id: str
    status: str
    profile: CandidateProfile
    summary: ScoreSummary
    modules: list[ModuleScore]
    category_views: list[CategoryView] = Field(default_factory=list)
    candidate_name: str | None = None
    target_role: str | None = None
    total_score: float | None = None
    role_fit_score: float | None = None
    tier: str | None = None
    role_match_label: str | None = None
    overall_summary: str | None = None
    categories: list[WorkspaceCategory] = Field(default_factory=list)


PipelineStageState = Literal["idle", "in_progress", "completed", "error"]


class PipelineStage(BaseModel):
    key: str
    label: str
    status: PipelineStageState = "idle"
    message: str = ""
    started_at: str | None = None
    completed_at: str | None = None


class CandidatePipelineStatus(BaseModel):
    candidate_id: str
    status: Literal["queued", "processing", "complete", "error", "not_found"] = "queued"
    target_role: str | None = None
    stages: list[PipelineStage] = Field(default_factory=list)
    error_message: str | None = None
    overall_score: float | None = None
    overall_grade: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
