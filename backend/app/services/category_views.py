from typing import Any

from app.constants.roles import ROLE_LABELS
from app.schemas.cv import CandidateProfile, CategoryView, ExtractedCategoryItem, ModuleScore
from app.schemas.cv import ScoreSummary, WorkspaceCategory


def _clean(values: list[str | None]) -> list[str]:
    return [str(value).strip() for value in values if str(value or "").strip()]


def _join(values: list[str]) -> str:
    return ", ".join(_clean(values))


def _skill_items(profile: CandidateProfile) -> list[ExtractedCategoryItem]:
    groups = [
        ("Programming languages", profile.programming_languages),
        ("Frameworks and libraries", profile.frameworks_libraries),
        ("Databases", profile.databases),
        ("Cloud and DevOps tools", profile.cloud_devops_tools),
        ("Testing tools", profile.testing_tools),
        ("ML and AI tools", profile.ml_ai_tools),
        ("Architecture practices", profile.architecture_practices),
        ("Other skills", profile.other_skills),
    ]
    return [
        ExtractedCategoryItem(title=title, body=_join(values), badges=values[:8])
        for title, values in groups
        if values
    ]


def _project_items(profile: CandidateProfile) -> list[ExtractedCategoryItem]:
    items: list[ExtractedCategoryItem] = []
    for project in profile.projects:
        badges = list(project.technologies[:8])
        flags = []
        if project.has_production_evidence:
            flags.append("Production evidence")
        if project.has_measurable_impact:
            flags.append("Measurable impact")
        if project.has_ownership_signal:
            flags.append("Ownership signal")
        items.append(ExtractedCategoryItem(
            title=project.title,
            subtitle=project.evidence_source,
            body=project.description,
            meta=_clean([
                f"Complexity: {project.complexity_level.replace('_', ' ')}",
                f"Duration: {project.duration_months} month(s)" if project.duration_months else None,
                project.impact_description,
            ]),
            badges=[*badges, *flags],
            details={
                "technologies": project.technologies,
                "production_evidence": project.has_production_evidence,
                "measurable_impact": project.has_measurable_impact,
                "ownership_signal": project.has_ownership_signal,
                "github_url": project.github_url,
                "live_url": project.live_url,
            },
        ))
    return items


def _experience_items(profile: CandidateProfile) -> list[ExtractedCategoryItem]:
    body_parts = _clean([
        f"Current role: {profile.current_role}" if profile.current_role else None,
        f"Current company: {profile.current_company}" if profile.current_company else None,
        f"Seniority signal: {profile.seniority_level}" if profile.seniority_level else None,
        f"Career stage: {profile.career_stage}" if profile.career_stage else None,
        f"Relevant experience: {profile.total_experience_months} month(s)",
    ])
    if not body_parts:
        return []
    return [ExtractedCategoryItem(
        title="Experience summary extracted from CV",
        body=". ".join(body_parts),
        badges=_clean([profile.current_role, profile.seniority_level, profile.career_stage]),
    )]


def _engineering_items(profile: CandidateProfile) -> list[ExtractedCategoryItem]:
    items: list[ExtractedCategoryItem] = []
    for title, values in [
        ("Testing evidence", profile.testing_tools),
        ("Cloud and deployment evidence", profile.cloud_devops_tools),
        ("Architecture and delivery practices", profile.architecture_practices),
    ]:
        if values:
            items.append(ExtractedCategoryItem(title=title, body=_join(values), badges=values[:8]))
    link_badges = _clean([
        "GitHub detected" if profile.has_github else None,
        "Portfolio/link detected" if profile.has_portfolio else None,
        "Deployed project evidence" if profile.has_deployed_projects else None,
    ])
    if link_badges:
        items.append(ExtractedCategoryItem(
            title="Delivery signals",
            body=", ".join(link_badges),
            badges=link_badges,
        ))
    return items


def _role_fit_items(profile: CandidateProfile, module: ModuleScore) -> list[ExtractedCategoryItem]:
    items = []
    if module.evidence_found:
        items.append(ExtractedCategoryItem(
            title="Role-fit evidence used by scoring",
            body=" ".join(module.evidence_found),
            badges=[profile.target_role],
        ))
    if profile.projects:
        items.append(ExtractedCategoryItem(
            title="Projects considered for role alignment",
            body=", ".join(project.title for project in profile.projects),
            badges=[profile.target_role],
        ))
    return items


def _education_items(profile: CandidateProfile) -> list[ExtractedCategoryItem]:
    items = []
    if profile.highest_degree or profile.degree_field or profile.degree_institution:
        items.append(ExtractedCategoryItem(
            title=profile.highest_degree or "Education entry",
            subtitle=profile.degree_institution,
            body=_join(_clean([profile.degree_field, "CS-related" if profile.degree_is_cs_related else None])),
            badges=_clean([profile.degree_field, profile.degree_institution]),
        ))
    for certification in profile.certifications:
        items.append(ExtractedCategoryItem(title=certification, subtitle="Certification"))
    return items


def _research_items(profile: CandidateProfile) -> list[ExtractedCategoryItem]:
    return [
        ExtractedCategoryItem(
            title=publication.title,
            subtitle=publication.venue,
            body=_join(_clean([publication.type, str(publication.year) if publication.year else None, publication.authorship_role])),
            badges=_clean([publication.indexing, "Indexed" if publication.is_indexed else None]),
        )
        for publication in profile.publications
    ]


def _quality_items(profile: CandidateProfile) -> list[ExtractedCategoryItem]:
    contact = _clean([
        "Email detected" if profile.email else None,
        "Phone detected" if profile.phone else None,
        "GitHub detected" if profile.github_url else None,
        "LinkedIn detected" if profile.linkedin_url else None,
        "Portfolio detected" if profile.portfolio_url else None,
    ])
    items = []
    if contact:
        items.append(ExtractedCategoryItem(title="Contact and link completeness", body=", ".join(contact), badges=contact))
    if profile.extraction_warnings:
        items.append(ExtractedCategoryItem(
            title="Extraction warnings",
            body=" ".join(profile.extraction_warnings),
            badges=[profile.extraction_confidence],
        ))
    else:
        items.append(ExtractedCategoryItem(
            title="Extraction confidence",
            body=f"The structured CV extraction completed with {profile.extraction_confidence} confidence.",
            badges=[profile.extraction_confidence],
        ))
    return items


def _fallback_items(module: ModuleScore) -> list[ExtractedCategoryItem]:
    if module.evidence_found:
        return [ExtractedCategoryItem(title="Evidence used by scoring", body=" ".join(module.evidence_found))]
    if module.missing_evidence:
        return [ExtractedCategoryItem(title="Missing evidence noted by scoring", body=" ".join(module.missing_evidence))]
    return []


def _items_for_module(profile: CandidateProfile, module: ModuleScore) -> list[ExtractedCategoryItem]:
    mapping = {
        "technical_skill": _skill_items(profile),
        "project_work": _project_items(profile),
        "professional_experience": _experience_items(profile),
        "engineering_practices": _engineering_items(profile),
        "role_fit": _role_fit_items(profile, module),
        "education_certifications": _education_items(profile),
        "research": _research_items(profile),
        "cv_quality": _quality_items(profile),
    }
    return mapping.get(module.module_key) or _fallback_items(module)


def _verdict(module: ModuleScore) -> str:
    label = module.module_label.lower()
    score = module.normalized_score
    if score >= 80:
        return f"Strong {label} with clear supporting evidence."
    if score >= 65:
        return f"Solid {label}, with a few gaps to strengthen."
    if score >= 40:
        return f"Developing {label}; the CV shows some useful signals but lacks depth."
    return f"Limited {label}; the score is constrained by missing or weak evidence."


def _narrative(module: ModuleScore) -> str:
    positives = "; ".join(module.evidence_found[:3]) if module.evidence_found else "No strong positive evidence was extracted for this category"
    gaps = "; ".join(module.missing_evidence[:3]) if module.missing_evidence else "no major missing evidence was flagged"
    reasoning = module.llm_reasoning.strip() or f"The {module.scoring_method} scorer evaluated the extracted CV evidence for this category."
    recommendation = f" Recommended next step: {module.recommendations[0]}" if module.recommendations else ""
    return (
        f"This category scored {module.score}/{module.max_score} ({module.normalized_score}%). "
        f"Positive signals: {positives}. Missing or weaker signals: {gaps}. "
        f"{reasoning}{recommendation}"
    )


def build_category_views(profile: CandidateProfile, modules: list[ModuleScore]) -> list[CategoryView]:
    views: list[CategoryView] = []
    for module in modules:
        views.append(CategoryView(
            key=module.module_key,
            label=module.module_label,
            score=module.score,
            max_score=module.max_score,
            normalized_score=module.normalized_score,
            grade=module.grade,
            verdict=_verdict(module),
            confidence=module.confidence,
            scoring_method=module.scoring_method,
            extracted_items=_items_for_module(profile, module),
            evidence_found=module.evidence_found,
            missing_evidence=module.missing_evidence,
            recommendations=module.recommendations,
            sub_scores=module.sub_scores,
            score_narrative=_narrative(module),
        ))
    return views


def workspace_grade_label(score: float) -> str:
    value = float(score or 0)
    if value >= 90:
        return "Excellent"
    if value >= 80:
        return "Strong"
    if value >= 70:
        return "Good"
    if value >= 55:
        return "Moderate"
    return "Critical"


def role_match_label(score: float | None) -> str:
    value = float(score or 0)
    if value >= 90:
        return "Elite Match"
    if value >= 80:
        return "Strong Match"
    if value >= 70:
        return "Good Match"
    if value >= 55:
        return "Partial Match"
    return "Weak Match"


def build_workspace_categories(category_views: list[CategoryView]) -> list[WorkspaceCategory]:
    return [
        WorkspaceCategory(
            key=category.key,
            name=category.label,
            normalized_score=category.normalized_score,
            weight=round((category.max_score or 0) / 100, 4),
            grade_label=workspace_grade_label(category.normalized_score),
            verdict_sentence=category.verdict,
            extracted_items=category.extracted_items,
            evidence=category.evidence_found,
            missing_evidence=category.missing_evidence,
            recommendations=category.recommendations,
            score_narrative=category.score_narrative,
            sub_scores=category.sub_scores,
        )
        for category in category_views
    ]


def apply_workspace_fields(
    *,
    candidate_id: str,
    profile: CandidateProfile,
    summary: ScoreSummary,
    modules: list[ModuleScore],
    category_views: list[CategoryView],
) -> dict[str, Any]:
    categories = build_workspace_categories(category_views)
    role_fit = next((category for category in categories if category.key == "role_fit"), None)
    return {
        "candidate_id": candidate_id,
        "status": "complete",
        "profile": profile,
        "summary": summary,
        "modules": modules,
        "category_views": category_views,
        "candidate_name": profile.name,
        "target_role": ROLE_LABELS.get(profile.target_role, profile.target_role),
        "total_score": summary.overall_score,
        "role_fit_score": role_fit.normalized_score if role_fit else None,
        "tier": summary.overall_grade,
        "role_match_label": role_match_label(role_fit.normalized_score if role_fit else None),
        "overall_summary": summary.summary_narrative,
        "categories": categories,
    }
