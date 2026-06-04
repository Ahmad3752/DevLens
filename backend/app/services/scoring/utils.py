from typing import Any

from app.constants.roles import MODULE_LABELS
from app.schemas.cv import ModuleScore


SCORE_TIERS = [
    (90, 100, "Senior Developer", "Strong senior or lead-level profile"),
    (80, 89, "Mid-Level Developer", "Ready for mid-level roles (2-5 yrs)"),
    (70, 79, "Junior Developer", "Ready for junior positions (0-2 yrs)"),
    (55, 69, "Intern / Trainee", "Ready for internship-level roles"),
    (40, 54, "Entry Candidate", "Some potential, but incomplete profile"),
    (0, 39, "Not Ready", "Significant gaps, needs foundational work"),
]


def clamp(value: float, maximum: float) -> float:
    return round(max(0.0, min(float(value or 0), float(maximum))), 2)


def score_tier(score: float) -> dict[str, str | int]:
    value = int(max(0, min(round(float(score or 0)), 100)))
    for low, high, label, verdict in SCORE_TIERS:
        if low <= value <= high:
            return {"min": low, "max": high, "label": label, "verdict": verdict}
    return {"min": 0, "max": 39, "label": "Not Ready", "verdict": "Significant gaps, needs foundational work"}


def grade(normalized_score: float) -> str:
    return str(score_tier(normalized_score)["label"])


def make_module(
    key: str,
    score: float,
    max_score: float,
    evidence: list[str],
    missing: list[str],
    sub_scores: dict[str, Any],
    recommendations: list[str],
    reasoning: str,
    method: str,
    confidence: str = "medium",
    raw: dict[str, Any] | None = None,
) -> ModuleScore:
    final = clamp(score, max_score)
    normalized = round((final / max_score) * 100, 2) if max_score else 0.0
    return ModuleScore(
        module_key=key,
        module_label=MODULE_LABELS[key],
        score=final,
        max_score=max_score,
        normalized_score=normalized,
        grade=grade(normalized),
        confidence=confidence,  # type: ignore[arg-type]
        evidence_found=evidence[:8],
        missing_evidence=missing[:8],
        sub_scores=sub_scores,
        recommendations=recommendations[:6],
        llm_reasoning=reasoning,
        scoring_method=method,  # type: ignore[arg-type]
        raw_module_json=raw or {},
    )


def split_points(total: float, parts: list[str]) -> dict[str, float]:
    share = total / max(1, len(parts))
    return {part: round(share, 2) for part in parts}


def contains_any(values: list[str], keywords: set[str]) -> bool:
    text = " ".join(values).lower()
    return any(k in text for k in keywords)
