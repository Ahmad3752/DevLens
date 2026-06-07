import logging
from typing import Any

from app.constants.roles import MODULE_LABELS
from app.schemas.cv import ModuleScore

logger = logging.getLogger("devlens.scoring")

SCORE_TOLERANCE = 0.05

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


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def sanitize_sub_scores(key: str, max_score: float, sub_scores: dict[str, Any]) -> tuple[dict[str, Any], float]:
    sanitized: dict[str, Any] = {}
    max_total = 0.0
    score_total = 0.0

    for name, value in (sub_scores or {}).items():
        data = value if isinstance(value, dict) else {}
        sub_max = round(max(0.0, _number(data.get("max"))), 2)
        if sub_max <= 0:
            logger.warning("Ignoring sub-score with non-positive max.", extra={"module_key": key, "sub_score": name})
            continue

        raw_score = _number(data.get("score"))
        sub_score = clamp(raw_score, sub_max)
        if raw_score > sub_max:
            logger.warning(
                "Clamped sub-score above max.",
                extra={"module_key": key, "sub_score": name, "score": raw_score, "max": sub_max},
            )

        normalized = {**data, "score": sub_score, "max": sub_max}
        sanitized[name] = normalized
        score_total += sub_score
        max_total += sub_max

    if sanitized and abs(max_total - float(max_score or 0)) > SCORE_TOLERANCE:
        logger.error(
            "Sub-score max total does not match module max.",
            extra={"module_key": key, "sub_score_max_total": round(max_total, 2), "module_max": max_score},
        )

    return sanitized, round(score_total, 2)


def reconcile_sub_scores(
    key: str,
    llm_sub_scores: dict[str, Any],
    baseline_sub_scores: dict[str, Any],
) -> dict[str, Any]:
    if not baseline_sub_scores:
        return llm_sub_scores or {}

    reconciled: dict[str, Any] = {}
    incoming = llm_sub_scores or {}
    for name, baseline_value in baseline_sub_scores.items():
        baseline_data = baseline_value if isinstance(baseline_value, dict) else {}
        incoming_data = incoming.get(name) if isinstance(incoming.get(name), dict) else {}
        source = incoming_data or baseline_data
        reconciled[name] = {
            **baseline_data,
            **source,
            "max": baseline_data.get("max", source.get("max", 0)),
        }

    for name in incoming.keys() - baseline_sub_scores.keys():
        logger.warning("Ignoring unknown LLM sub-score key.", extra={"module_key": key, "sub_score": name})

    return reconciled


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
    sanitized_sub_scores, derived_score = sanitize_sub_scores(key, max_score, sub_scores)
    final = clamp(derived_score if sanitized_sub_scores else score, max_score)
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
        sub_scores=sanitized_sub_scores,
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
