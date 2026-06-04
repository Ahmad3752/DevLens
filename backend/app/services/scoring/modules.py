import re

from app.schemas.cv import CandidateProfile, ModuleScore
from app.services.scoring.llm_modules import HYBRID_MODULES, LLM_MODULES, llm_score_module
from app.services.scoring.utils import contains_any, make_module


ROLE_SKILLS = {
    "backend": {"fastapi", "django", "flask", "node", "express", "spring", "postgres", "mysql", "redis", "api", "rest", "docker", "aws"},
    "frontend": {"react", "next", "vue", "angular", "typescript", "javascript", "css", "html", "accessibility", "responsive"},
    "full_stack": {"react", "next", "fastapi", "node", "postgres", "api", "docker", "aws", "typescript", "python"},
    "mobile": {"flutter", "react native", "kotlin", "swift", "android", "ios", "dart"},
    "ai_ml": {"python", "pytorch", "tensorflow", "scikit", "langchain", "langgraph", "rag", "huggingface", "bedrock", "mlflow"},
    "devops": {"aws", "docker", "kubernetes", "terraform", "ci/cd", "github actions", "linux", "monitoring", "nginx"},
    "data_engineer": {"sql", "spark", "kafka", "airflow", "dbt", "postgres", "warehouse", "python", "etl"},
    "data_scientist": {"python", "statistics", "pandas", "numpy", "scikit", "pytorch", "visualization", "experiment"},
    "qa_automation": {"selenium", "playwright", "cypress", "pytest", "jest", "postman", "ci/cd", "coverage"},
}

ROLE_CORE_SKILLS = {
    "backend": {"python", "java", "javascript", "typescript", "go", "php", "c#", "api", "rest"},
    "frontend": {"javascript", "typescript", "react", "next", "vue", "angular", "css", "html"},
    "full_stack": {"javascript", "typescript", "python", "react", "node", "fastapi", "api", "postgres"},
    "mobile": {"flutter", "react native", "kotlin", "swift", "android", "ios", "dart"},
    "ai_ml": {"python", "pytorch", "tensorflow", "scikit", "pandas", "numpy", "rag", "langchain", "huggingface"},
    "devops": {"aws", "docker", "kubernetes", "terraform", "ci/cd", "github actions", "linux"},
    "data_engineer": {"sql", "spark", "kafka", "airflow", "dbt", "warehouse", "etl", "python"},
    "data_scientist": {"python", "statistics", "pandas", "numpy", "scikit", "pytorch", "experiment"},
    "qa_automation": {"selenium", "playwright", "cypress", "pytest", "jest", "postman", "ci/cd"},
}


def _all_skills(profile: CandidateProfile) -> list[str]:
    return (
        profile.programming_languages + profile.frameworks_libraries + profile.databases
        + profile.cloud_devops_tools + profile.testing_tools + profile.ml_ai_tools
        + profile.architecture_practices + profile.other_skills
    )


def _norm(values: list[str]) -> set[str]:
    return {str(value).lower().replace("-", " ").strip() for value in values if value}


def _role_matches(values: list[str], role: str) -> list[str]:
    required = ROLE_SKILLS.get(role, set())
    return [s for s in values if any(req in s.lower().replace("-", " ") for req in required)]


def _project_role_matches(profile: CandidateProfile) -> list[str]:
    role_terms = ROLE_SKILLS.get(profile.target_role, set())
    titles = []
    for project in profile.projects:
        tech_text = " ".join(project.technologies).lower().replace("-", " ")
        desc_text = f"{project.title} {project.description}".lower().replace("-", " ")
        if any(term in tech_text or term in desc_text for term in role_terms):
            titles.append(project.title)
    return titles


def technical_skill(profile: CandidateProfile, max_score: float) -> ModuleScore:
    skills = _all_skills(profile)
    required = ROLE_SKILLS.get(profile.target_role, set())
    core = ROLE_CORE_SKILLS.get(profile.target_role, required)
    matched = _role_matches(skills, profile.target_role)
    project_tech = _norm([t for p in profile.projects for t in p.technologies])
    demonstrated = [term for term in required if any(term in tech for tech in project_tech)]
    core_matches = [term for term in core if any(term in skill.lower().replace("-", " ") for skill in skills)]
    project_titles = _project_role_matches(profile)
    claimed_ratio = min(1.0, len(set(matched)) / 8)
    core_ratio = min(1.0, len(set(core_matches)) / 5)
    demonstrated_ratio = min(1.0, len(set(demonstrated)) / 5)
    project_evidence_ratio = min(1.0, len(project_titles) / 2)
    score = max_score * (
        claimed_ratio * 0.25
        + core_ratio * 0.25
        + demonstrated_ratio * 0.30
        + project_evidence_ratio * 0.20
    )
    evidence = [f"Role-matched skills: {', '.join(matched[:10])}"] if matched else []
    if project_tech:
        evidence.append(f"Project-level technology evidence: {', '.join(sorted(project_tech)[:10])}")
    missing = [] if matched else ["Few role-specific technical skills were found."]
    if not demonstrated:
        missing.append("Skills are not strongly tied to project evidence.")
    return make_module("technical_skill", score, max_score, evidence, missing, {
        "claimed_role_skill_overlap": {"score": round(max_score * claimed_ratio * 0.25, 2), "max": round(max_score * 0.25, 2), "reasoning": "Claimed skills that match the selected role."},
        "core_skill_coverage": {"score": round(max_score * core_ratio * 0.25, 2), "max": round(max_score * 0.25, 2), "reasoning": "Coverage of role-critical skills, not just adjacent tools."},
        "demonstrated_project_skills": {"score": round(max_score * demonstrated_ratio * 0.30, 2), "max": round(max_score * 0.30, 2), "reasoning": "Role skills appearing in valid project evidence."},
        "role_project_evidence": {"score": round(max_score * project_evidence_ratio * 0.20, 2), "max": round(max_score * 0.20, 2), "reasoning": "Valid projects that directly support the selected role."},
    }, ["Tie every major skill to a project bullet with outcome or deployment evidence."], "Deterministic baseline calibrated by role-specific skill overlap.", "deterministic")


def project_work(profile: CandidateProfile, max_score: float) -> ModuleScore:
    projects = profile.projects[:3]
    production = [p for p in projects if p.has_production_evidence]
    impact = [p for p in projects if p.has_measurable_impact]
    ownership = [p for p in projects if p.has_ownership_signal]
    complex_projects = [p for p in projects if p.complexity_level in {"high", "very_high"}]
    role_projects = _project_role_matches(profile)
    score = max_score * min(
        1.0,
        len(projects) / 3 * 0.12
        + len(production) / 3 * 0.18
        + len(impact) / 3 * 0.22
        + len(ownership) / 3 * 0.18
        + len(complex_projects) / 3 * 0.15
        + len(role_projects) / 3 * 0.15,
    )
    evidence = [f"{len(projects)} project/work item(s) extracted."] if projects else []
    if production:
        evidence.append(f"{len(production)} project(s) show deployment or production evidence.")
    if impact:
        evidence.append(f"{len(impact)} project(s) include measurable impact.")
    missing = []
    if len(projects) < 2:
        missing.append("Add at least 2-3 clearly named projects.")
    if not production:
        missing.append("No deployed/live/production evidence was found.")
    if not impact:
        missing.append("No measurable outcomes were found.")
    if not role_projects:
        missing.append("No valid project is clearly aligned with the selected role.")
    return make_module("project_work", score, max_score, evidence, missing, {
        "valid_project_count": {"score": round(min(max_score * 0.12, len(projects) / 3 * max_score * 0.12), 2), "max": round(max_score * 0.12, 2)},
        "production_evidence": {"score": round(min(max_score * 0.18, len(production) / 3 * max_score * 0.18), 2), "max": round(max_score * 0.18, 2)},
        "impact_evidence": {"score": round(min(max_score * 0.22, len(impact) / 3 * max_score * 0.22), 2), "max": round(max_score * 0.22, 2)},
        "ownership": {"score": round(min(max_score * 0.18, len(ownership) / 3 * max_score * 0.18), 2), "max": round(max_score * 0.18, 2)},
        "complexity": {"score": round(min(max_score * 0.15, len(complex_projects) / 3 * max_score * 0.15), 2), "max": round(max_score * 0.15, 2)},
        "role_project_alignment": {"score": round(min(max_score * 0.15, len(role_projects) / 3 * max_score * 0.15), 2), "max": round(max_score * 0.15, 2)},
    }, ["For each project, add stack, ownership, deployment link, and a metric."], "Project score rewards concrete shipped work over keyword density.", "deterministic")


def professional_experience(profile: CandidateProfile, max_score: float) -> ModuleScore:
    months = profile.total_experience_months
    text = profile.raw_cv_text.lower()
    inferred_months = months or (2 if "intern" in text else 0)
    duration = min(max_score * 0.55, inferred_months / 60 * max_score * 0.55)
    role_projects = _project_role_matches(profile)
    relevance = max_score * (0.20 if role_projects else 0.08 if contains_any(_all_skills(profile), ROLE_SKILLS.get(profile.target_role, set())) else 0)
    seniority = max_score * (
        0.20 if profile.seniority_level in {"senior", "lead"}
        else 0.12 if profile.seniority_level == "mid"
        else 0.07 if profile.seniority_level == "junior"
        else 0.03 if profile.seniority_level == "intern"
        else 0.02
    )
    clarity = max_score * 0.05 if profile.current_role and inferred_months else 0
    score = duration + relevance + seniority + clarity
    return make_module("professional_experience", score, max_score, [f"Estimated relevant experience: {inferred_months} month(s)."], ["Limited professional duration evidence."] if inferred_months < 12 else [], {
        "duration": {"score": round(duration, 2), "max": round(max_score * 0.55, 2)},
        "role_relevance": {"score": round(relevance, 2), "max": round(max_score * 0.20, 2)},
        "seniority_signal": {"score": round(seniority, 2), "max": round(max_score * 0.2, 2)},
        "date_and_role_clarity": {"score": round(clarity, 2), "max": round(max_score * 0.05, 2)},
    }, ["Add dates, role scope, team context, and production responsibilities for each experience."], "Hybrid baseline uses duration and relevance signals; LLM can adjust quality.", "hybrid")


def engineering_practices(profile: CandidateProfile, max_score: float) -> ModuleScore:
    skills = _all_skills(profile)
    raw = profile.raw_cv_text.lower()
    checks = {
        "testing": any(x.lower() in raw for x in profile.testing_tools) or bool(re.search(r"\b(test|testing|coverage|pytest|jest|unit test)\b", raw)),
        "version_control": profile.has_github or "git" in raw,
        "ci_cd": "github actions" in raw or "ci/cd" in raw or "pipeline" in raw,
        "architecture": bool(profile.architecture_practices) or bool(re.search(r"\b(architecture|orchestration|microservices|reranking|fallback|caching)\b", raw)),
        "security_performance": any(k in raw for k in ["security", "auth", "jwt", "performance", "cache", "redis"]),
        "deployment": any(k in " ".join(skills).lower() for k in ["docker", "aws", "kubernetes", "render", "vercel"]),
    }
    earned = sum(1 for ok in checks.values() if ok)
    evidence = [name.replace("_", " ").title() for name, ok in checks.items() if ok]
    missing = [f"No {name.replace('_', ' ')} evidence found." for name, ok in checks.items() if not ok]
    score = max_score * earned / len(checks)
    return make_module("engineering_practices", score, max_score, evidence, missing, {k: {"score": max_score / len(checks) if v else 0, "max": max_score / len(checks)} for k, v in checks.items()}, ["Add testing, CI/CD, deployment, monitoring, and security bullets where true."], "Engineering practice score checks whether the CV proves professional delivery habits.", "deterministic")


def role_fit(profile: CandidateProfile, max_score: float) -> ModuleScore:
    role_terms = ROLE_SKILLS.get(profile.target_role, set())
    skills = _all_skills(profile)
    overlap = _role_matches(skills, profile.target_role)
    project_overlap = _project_role_matches(profile)
    core = ROLE_CORE_SKILLS.get(profile.target_role, role_terms)
    core_overlap = [s for s in skills if any(term in s.lower().replace("-", " ") for term in core)]
    score = max_score * min(1.0, len(set(overlap)) / 8 * 0.35 + len(set(core_overlap)) / 5 * 0.30 + len(project_overlap) / 2 * 0.35)
    return make_module("role_fit", score, max_score, [f"Target-role overlap: {', '.join(overlap[:8])}"] if overlap else [], ["CV does not strongly signal the selected role."] if len(overlap) < 3 else [], {
        "skill_overlap": {"score": round(min(max_score * 0.35, len(set(overlap)) / 8 * max_score * 0.35), 2), "max": round(max_score * 0.35, 2)},
        "core_role_overlap": {"score": round(min(max_score * 0.30, len(set(core_overlap)) / 5 * max_score * 0.30), 2), "max": round(max_score * 0.30, 2)},
        "project_overlap": {"score": round(min(max_score * 0.35, len(project_overlap) / 2 * max_score * 0.35), 2), "max": round(max_score * 0.35, 2)},
    }, ["Rewrite the summary and top projects around the selected target role."], "Role fit compares the extracted profile with the selected role vocabulary.", "hybrid")


def education_certifications(profile: CandidateProfile, max_score: float) -> ModuleScore:
    degree = max_score * 0.45 if profile.degree_is_cs_related else max_score * 0.25 if profile.highest_degree else 0
    cert = min(max_score * 0.35, len(profile.certifications) * max_score * 0.12)
    learning = max_score * 0.2 if (profile.certifications or profile.publications or "course" in profile.raw_cv_text.lower()) else 0
    evidence = []
    if profile.highest_degree:
        evidence.append(f"Education found: {profile.highest_degree}")
    if profile.certifications:
        evidence.append(f"Certifications found: {len(profile.certifications)}")
    missing = [] if evidence else ["No education or certification evidence found."]
    return make_module("education_certifications", degree + cert + learning, max_score, evidence, missing, {
        "degree_relevance": {"score": round(degree, 2), "max": round(max_score * 0.45, 2)},
        "certifications": {"score": round(cert, 2), "max": round(max_score * 0.35, 2)},
        "continuous_learning": {"score": round(learning, 2), "max": round(max_score * 0.2, 2)},
    }, ["Add relevant courses, certifications, and expected graduation date if applicable."], "Education score is deterministic because these are objective CV facts.", "deterministic")


def research(profile: CandidateProfile, max_score: float) -> ModuleScore:
    pubs = profile.publications
    indexed = [p for p in pubs if p.is_indexed or (p.indexing and p.indexing.lower() in {"ieee", "acm", "springer"})]
    score = max_score * min(1.0, len(pubs) / 3 * 0.35 + len(indexed) / 2 * 0.35 + (0.20 if profile.target_role in {"ai_ml", "data_scientist", "data_engineer"} else 0) + (0.10 if any(p.authorship_role for p in pubs) else 0))
    evidence = [f"{len(pubs)} publication/research item(s) detected."] if pubs else []
    if indexed:
        evidence.append(f"{len(indexed)} indexed publication signal(s).")
    missing = ["No publications or research outputs found."] if not pubs else []
    return make_module("research", score, max_score, evidence, missing, {
        "publication_volume": {"score": round(score * 0.55, 2), "max": round(max_score * 0.55, 2)},
        "indexing_quality": {"score": round(score * 0.3, 2), "max": round(max_score * 0.3, 2)},
        "role_relevance": {"score": round(score * 0.15, 2), "max": round(max_score * 0.15, 2)},
    }, ["Mention venue, year, indexing, authorship role, and paper topic relevance."], "Research score rewards publications and indexed venues, especially for AI/data roles.", "deterministic")


def cv_quality(profile: CandidateProfile, max_score: float) -> ModuleScore:
    raw = profile.raw_cv_text
    checks = {
        "contact": bool(profile.email or profile.phone),
        "links": bool(profile.github_url or profile.linkedin_url or profile.portfolio_url),
        "projects": len(profile.projects) >= 1,
        "metrics": bool(re.search(r"\b\d+%|\b\d+x|\busers?\b|\baccuracy\b|\breduced\b|\bimproved\b", raw, re.I)),
        "readability": 600 <= len(raw) <= 12000,
    }
    score = max_score * sum(checks.values()) / len(checks)
    evidence = [name.title() for name, ok in checks.items() if ok]
    missing = [f"Missing or weak {name} evidence." for name, ok in checks.items() if not ok]
    return make_module("cv_quality", score, max_score, evidence, missing, {k: {"score": max_score / len(checks) if v else 0, "max": max_score / len(checks)} for k, v in checks.items()}, ["Keep bullets impact-first and make links/contact easy to scan."], "CV quality uses objective completeness and communication signals.", "deterministic")


SCORERS = {
    "technical_skill": technical_skill,
    "project_work": project_work,
    "professional_experience": professional_experience,
    "engineering_practices": engineering_practices,
    "role_fit": role_fit,
    "education_certifications": education_certifications,
    "research": research,
    "cv_quality": cv_quality,
}


def score_one(key: str, profile: CandidateProfile, max_score: float) -> ModuleScore:
    baseline = SCORERS[key](profile, max_score)
    if key not in LLM_MODULES and key not in HYBRID_MODULES:
        return baseline
    try:
        return llm_score_module(key, profile, max_score, baseline)
    except Exception as exc:
        baseline.llm_reasoning += f" LLM scoring unavailable; baseline used. Reason: {exc}"
        return baseline
