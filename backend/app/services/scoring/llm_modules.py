import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.constants.roles import ROLE_FOCUS
from app.schemas.cv import CandidateProfile, ModuleScore
from app.services.llm_client import invoke_model_bedrock_first
from app.services.scoring.utils import make_module


LLM_MODULES = {"technical_skill", "project_work", "engineering_practices", "research"}
HYBRID_MODULES = {"professional_experience", "role_fit"}
BEDROCK_FIRST_MODULES = {"project_work", "professional_experience"}


class StructuredModuleScore(BaseModel):
    """Structured CV module score."""

    score: float = Field(description="Module score.")
    confidence: Literal["low", "medium", "high"] = Field(default="medium", description="Evidence confidence.")
    evidence_found: list[str] = Field(default_factory=list, description="Evidence found.")
    missing_evidence: list[str] = Field(default_factory=list, description="Missing evidence.")
    sub_scores: dict[str, Any] = Field(default_factory=dict, description="Criterion scores.")
    recommendations: list[str] = Field(default_factory=list, description="Improvement recommendations.")
    llm_reasoning: str = Field(default="", description="Brief scoring reasoning.")


BEDROCK_SCORING_SYSTEM = (
    "You are a strict senior engineering interviewer evaluating developer CV evidence. "
    "Return only valid JSON. Do not include markdown or prose outside JSON. "
    "Use only the supplied CV/profile evidence. Never invent dates, ownership, impact, deployment, or role relevance."
)


def _bedrock_prompt(key: str, profile: CandidateProfile, max_score: float, baseline: ModuleScore) -> str:
    module_focus = {
        "project_work": (
            "Judge project depth for the selected role. Evaluate valid named projects only. "
            "Reward demonstrated ownership, deployment/live evidence, measurable outcomes, technical complexity, "
            "role alignment, and credible engineering detail. Penalize vague project claims, keyword lists, "
            "generic section headers, and projects unrelated to the selected role."
        ),
        "professional_experience": (
            "Judge professional experience realistically. Evaluate duration, role scope, relevance to selected role, "
            "team/product responsibility, production exposure, progression, and clarity of dates. "
            "Student/intern experience should not receive junior/mid/senior-level scores unless the CV proves unusually strong shipped work."
        ),
    }[key]
    return f"""
Score module "{key}" for target role "{profile.target_role}".
Role focus: {ROLE_FOCUS.get(profile.target_role, profile.target_role)}
Max score: {max_score}

Module judging instructions:
{module_focus}

Required JSON shape:
{{
  "score": number from 0 to {max_score},
  "confidence": "low" | "medium" | "high",
  "evidence_found": ["short evidence strings"],
  "missing_evidence": ["short missing evidence strings"],
  "sub_scores": {{
    "criterion_name": {{"score": number, "max": number, "reasoning": "short reason"}}
  }},
  "recommendations": ["short actionable improvements"],
  "llm_reasoning": "brief explanation of why the score is fair"
}}

Strict rules:
- Score only the selected role, not general software potential.
- Reward demonstrated work more than listed keywords.
- Avoid senior-level scores for student/intern evidence.
- If evidence is missing, score conservatively.
- Keep score dynamic; do not snap to a fixed career-stage number.

Deterministic baseline for calibration:
{baseline.model_dump_json()}

Profile without raw CV text:
{json.dumps(profile.model_dump(exclude={"raw_cv_text"}), ensure_ascii=True)}
"""


def _generic_prompt(key: str, profile: CandidateProfile, max_score: float, baseline: ModuleScore) -> str:
    return f"""
Score the CV module "{key}" for target role "{profile.target_role}".
Role focus: {ROLE_FOCUS.get(profile.target_role, profile.target_role)}

Return JSON with:
score number from 0 to {max_score},
confidence one of low, medium, high,
evidence_found array,
missing_evidence array,
sub_scores object where each item has score, max, reasoning,
recommendations array,
llm_reasoning string.

Be honest. Reward project-level evidence more than keyword lists. Do not invent evidence.
Do not give senior-level module scores for student/intern evidence unless the CV proves unusually strong shipped work.
For role mismatch, score the selected role only; do not reward unrelated general software strength as selected-role fit.
Treat invalid or generic project titles such as "Projects", "Experience", or the candidate name as weak evidence.

Baseline score to calibrate from:
{baseline.model_dump_json()}

Profile:
{json.dumps(profile.model_dump(exclude={"raw_cv_text"}), ensure_ascii=True)}
"""


def llm_score_module(key: str, profile: CandidateProfile, max_score: float, baseline: ModuleScore) -> ModuleScore:
    prompt = _bedrock_prompt(key, profile, max_score, baseline) if key in BEDROCK_FIRST_MODULES else _generic_prompt(key, profile, max_score, baseline)
    structured = invoke_model_bedrock_first(prompt, StructuredModuleScore, BEDROCK_SCORING_SYSTEM)
    raw = structured.model_dump()
    return make_module(
        key=key,
        score=structured.score,
        max_score=max_score,
        evidence=structured.evidence_found,
        missing=structured.missing_evidence,
        sub_scores=structured.sub_scores,
        recommendations=structured.recommendations,
        reasoning=structured.llm_reasoning,
        method="hybrid" if key in HYBRID_MODULES else "llm",
        confidence=structured.confidence,
        raw=raw,
    )
