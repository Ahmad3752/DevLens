import re
from datetime import date
from typing import Iterable

from app.schemas.cv import CandidateProfile, Project, Publication
from app.services.llm_client import invoke_model_openrouter_first


VOCAB = {
    "programming_languages": ["Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Rust", "PHP", "Ruby", "Kotlin", "Swift", "Dart", "R", "SQL", "HTML", "CSS"],
    "frameworks_libraries": ["FastAPI", "Django", "Flask", "React", "Next.js", "Node.js", "Express", "Spring", "Flutter", "React Native", "Streamlit", "LangChain", "LangGraph"],
    "databases": ["PostgreSQL", "MySQL", "MongoDB", "SQLite", "Redis", "DynamoDB", "Firebase", "ChromaDB", "FAISS", "Pinecone"],
    "cloud_devops_tools": ["AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "GitHub Actions", "GitLab CI", "Jenkins", "Linux", "Render", "Vercel", "Nginx"],
    "testing_tools": ["Pytest", "Jest", "Cypress", "Playwright", "Selenium", "JUnit", "Postman", "Unittest"],
    "ml_ai_tools": ["PyTorch", "TensorFlow", "Scikit-learn", "Pandas", "NumPy", "HuggingFace", "Transformers", "SBERT", "spaCy", "MLflow", "Bedrock", "OpenAI", "Claude", "RAG"],
    "architecture_practices": ["REST", "GraphQL", "Microservices", "MVC", "Clean Architecture", "SOLID", "JWT", "OAuth", "Caching", "Security", "Scalability", "CI/CD"],
}


SECTION_HEADERS = {
    "summary", "profile", "education", "experience", "work experience",
    "professional experience", "research", "research publications",
    "publications", "projects", "technical skills", "skills",
    "certifications", "certification", "awards", "coursework",
}

PROJECT_STOP_HEADERS = {
    "technical skills", "skills", "education", "experience", "work experience",
    "professional experience", "research", "research publications",
    "publications", "certifications", "certification", "awards",
}

INVALID_PROJECT_TITLES = {
    "project", "projects", "experience", "work experience", "professional experience",
    "summary", "technical skills", "skills", "education", "research publications",
    "publications", "certifications",
}

MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value or "").strip(" .,;:|")
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def _find_terms(text: str, terms: list[str]) -> list[str]:
    found = []
    for term in terms:
        pattern = r"(?<![A-Za-z0-9+#.])" + re.escape(term) + r"(?![A-Za-z0-9+#.])"
        if re.search(pattern, text, re.I):
            found.append(term)
    return _dedupe(found)


def _extract_links(text: str) -> list[str]:
    return _dedupe(re.findall(r"https?://[^\s<>)\]]+|(?:github|linkedin)\.com/[^\s<>)\]]+", text, re.I))


def _header_key(line: str) -> str:
    return re.sub(r"[^a-z ]+", "", line.lower()).strip()


def _is_header(line: str, headers: set[str] = SECTION_HEADERS) -> bool:
    return _header_key(line) in headers


def _section_lines(raw_text: str, start_headers: set[str], stop_headers: set[str]) -> list[str]:
    lines = [line.strip() for line in raw_text.splitlines()]
    start = None
    for idx, line in enumerate(lines):
        if _header_key(line) in start_headers:
            start = idx + 1
            break
    if start is None:
        return []

    end = len(lines)
    for idx in range(start, len(lines)):
        if _header_key(lines[idx]) in stop_headers:
            end = idx
            break
    return [line for line in lines[start:end] if line.strip()]


def _looks_like_project_title(line: str) -> bool:
    clean = line.strip(" -:|")
    if not clean or len(clean) > 180:
        return False
    if _is_header(clean) or _header_key(clean) in INVALID_PROJECT_TITLES:
        return False
    if clean.startswith(("•", "-", "*", "+")):
        return False
    if clean.endswith("."):
        return False
    if re.search(r"\b\d{4}\b", clean) and not re.search(r"\b(app|platform|system|assistant|pipeline|model|classifier|dashboard|project)\b", clean, re.I):
        return False
    title_markers = r"\||—|:|\b(app|platform|system|assistant|pipeline|model|classifier|dashboard|rag|learning|automation|api)\b"
    return bool(re.search(title_markers, clean, re.I))


def _project_flags(block: str) -> tuple[bool, bool, bool, str]:
    production = bool(re.search(
        r"\b(deployed|production|live|users?|render|vercel|netlify|app store|play store|hosted|public demo|live demo)\b",
        block,
        re.I,
    ))
    impact = bool(re.search(
        r"\b\d+%|\b\d+x|\b\d+[,+]?\s*(users?|records?|clients?|requests?|documents?|categories?|tables?)\b|"
        r"\baccuracy\b|\bf1\b|\blatency\b|\breduced\b|\bimproved\b|\boutperformed\b",
        block,
        re.I,
    ))
    ownership = bool(re.search(r"\b(built|designed|implemented|led|owned|created|developed|engineered|architected)\b", block, re.I))
    return production, impact, ownership, block


def _valid_project(title: str, description: str, candidate_name: str | None, technologies: list[str]) -> bool:
    title_key = _header_key(title)
    name_key = _header_key(candidate_name or "")
    if title_key in INVALID_PROJECT_TITLES or (name_key and title_key == name_key):
        return False
    if len(description) > 1400 and re.search(r"\b(summary|education|experience|technical skills)\b", description, re.I):
        return False
    if len(description) < 50 and len(technologies) < 2:
        return False
    return True


def _parse_projects(raw_text: str, candidate_name: str | None) -> list[Project]:
    lines = _section_lines(raw_text, {"projects"}, PROJECT_STOP_HEADERS)
    projects: list[Project] = []
    current_title: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_lines
        if not current_title:
            current_lines = []
            return
        block = " ".join([current_title, *current_lines]).strip()
        tech: list[str] = []
        for terms in VOCAB.values():
            tech.extend(_find_terms(block, terms))
        tech = _dedupe(tech)
        if not _valid_project(current_title, block, candidate_name, tech):
            current_title = None
            current_lines = []
            return
        production, impact, ownership, _ = _project_flags(block)
        bullet_count = len([line for line in current_lines if line.startswith(("•", "-", "*"))])
        complexity = "very_high" if len(tech) >= 8 and bullet_count >= 3 else "high" if len(tech) >= 4 and len(block) >= 220 else "medium"
        projects.append(Project(
            title=current_title[:90],
            description=re.sub(r"\s+", " ", block).strip()[:900],
            technologies=tech,
            evidence_source="Projects section",
            has_production_evidence=production,
            has_measurable_impact=impact,
            has_ownership_signal=ownership,
            complexity_level=complexity,
        ))
        current_title = None
        current_lines = []

    for line in lines:
        if _looks_like_project_title(line):
            flush()
            current_title = line.strip(" -:")
        elif current_title:
            current_lines.append(line)
    flush()

    seen: set[str] = set()
    unique: list[Project] = []
    for project in projects:
        key = _header_key(project.title)
        if key not in seen:
            seen.add(key)
            unique.append(project)
    return unique[:5]


def _sanitize_projects(projects: list[Project], raw_text: str, candidate_name: str | None) -> list[Project]:
    sanitized: list[Project] = []
    for project in projects:
        block = f"{project.title} {project.description}".strip()
        tech = _dedupe(project.technologies)
        if not tech:
            for terms in VOCAB.values():
                tech.extend(_find_terms(block, terms))
            tech = _dedupe(tech)
        if not _valid_project(project.title, block, candidate_name, tech):
            continue
        production, impact, ownership, _ = _project_flags(block)
        project.technologies = tech
        project.has_production_evidence = bool(project.has_production_evidence or production)
        project.has_measurable_impact = bool(project.has_measurable_impact or impact)
        project.has_ownership_signal = bool(project.has_ownership_signal or ownership)
        project.evidence_source = project.evidence_source or "LLM extraction"
        sanitized.append(project)

    seen: set[str] = set()
    unique: list[Project] = []
    for project in sanitized:
        key = _header_key(project.title)
        if key not in seen:
            seen.add(key)
            unique.append(project)
    return unique[:5]


def _parse_month(value: str) -> date | None:
    match = re.search(r"\b([A-Za-z]{3,9})\s+(\d{4})\b", value)
    if not match:
        return None
    month = MONTHS.get(match.group(1).lower())
    if not month:
        return None
    return date(int(match.group(2)), month, 1)


def _month_span(start: date, end: date) -> int:
    return max(1, (end.year - start.year) * 12 + (end.month - start.month) + 1)


def _experience_months(raw_text: str) -> int:
    lines = _section_lines(raw_text, {"experience", "work experience", "professional experience"}, {
        "projects", "education", "technical skills", "skills", "certifications", "research", "research publications", "publications",
    })
    text = "\n".join(lines)
    total = 0
    date_pattern = (
        r"\b([A-Za-z]{3,9}\s+\d{4})\s*(?:-|–|—|to)\s*"
        r"([A-Za-z]{3,9}\s+\d{4}|present|current|now)\b"
    )
    for start_raw, end_raw in re.findall(date_pattern, text, re.I):
        start = _parse_month(start_raw)
        end = date.today() if end_raw.lower() in {"present", "current", "now"} else _parse_month(end_raw)
        if start and end:
            total += _month_span(start, end)
    return total


def _current_role(raw_text: str) -> str | None:
    lines = _section_lines(raw_text, {"experience", "work experience", "professional experience"}, {
        "projects", "education", "technical skills", "skills", "certifications", "research", "research publications", "publications",
    })
    for line in lines:
        if re.search(r"\b\d{4}\b|pakistan|islamabad|rawalpindi|lab|university|company", line, re.I):
            continue
        if 3 <= len(line) <= 80:
            return line.strip(" -:")
    return None


def _career_stage(raw_text: str, seniority: str | None, months: int) -> str:
    raw = raw_text.lower()
    if seniority == "intern" or months < 6 and re.search(r"\bintern(ship)?\b", raw):
        return "intern"
    if re.search(r"\b(undergraduate|student|expected|present)\b", raw) and re.search(r"\b(bs|b\.s|bachelor|data science|computer science)\b", raw):
        return "student"
    if months >= 60 or seniority in {"senior", "lead"}:
        return "senior"
    if months >= 24:
        return "mid"
    if months >= 6:
        return "junior"
    return "early"


def deterministic_extract(raw_text: str, target_role: str) -> CandidateProfile:
    links = _extract_links(raw_text)
    lower = raw_text.lower()
    email = (re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", raw_text) or [None])[0]
    phone = (re.search(r"(?:\+?\d[\d\s().-]{7,}\d)", raw_text) or [None])[0]
    name = next((line.strip() for line in raw_text.splitlines() if 2 <= len(line.strip()) <= 70), None)

    projects = _parse_projects(raw_text, name)
    experience_months = _experience_months(raw_text)
    current_role = _current_role(raw_text)

    publications = [
        Publication(title=line.strip(" -"), is_indexed="ieee" in line.lower(), indexing="IEEE" if "ieee" in line.lower() else None)
        for line in raw_text.splitlines()
        if not _is_header(line) and re.search(r"\b(paper|conference|journal|ieee|acm|springer)\b", line, re.I)
    ][:5]

    degree_match = re.search(r"\b(PhD|M\.?S\.?|Master|B\.?S\.?|Bachelor|MBA)\b[^\n,;]*", raw_text, re.I)
    degree_text = degree_match.group(0) if degree_match else None
    certs = [line.strip(" -") for line in raw_text.splitlines() if re.search(r"\b(certification|specialization|certificate|aws certified|coursera|udemy)\b", line, re.I)][:8]

    profile = CandidateProfile(
        target_role=target_role,
        raw_cv_text=raw_text,
        name=name,
        email=email,
        phone=phone,
        github_url=next((x for x in links if "github" in x.lower()), None),
        linkedin_url=next((x for x in links if "linkedin" in x.lower()), None),
        portfolio_url=next((x for x in links if not any(k in x.lower() for k in ["github", "linkedin"])), None),
        programming_languages=_find_terms(raw_text, VOCAB["programming_languages"]),
        frameworks_libraries=_find_terms(raw_text, VOCAB["frameworks_libraries"]),
        databases=_find_terms(raw_text, VOCAB["databases"]),
        cloud_devops_tools=_find_terms(raw_text, VOCAB["cloud_devops_tools"]),
        testing_tools=_find_terms(raw_text, VOCAB["testing_tools"]),
        ml_ai_tools=_find_terms(raw_text, VOCAB["ml_ai_tools"]),
        architecture_practices=_find_terms(raw_text, VOCAB["architecture_practices"]),
        projects=projects,
        total_experience_months=experience_months,
        current_role=current_role,
        highest_degree=degree_text,
        degree_field=degree_text,
        degree_is_cs_related=bool(degree_text and re.search(r"computer|software|data|ai|machine|information|engineering|math|statistics", degree_text, re.I)),
        certifications=certs,
        publications=publications,
        has_github=any("github" in x.lower() for x in links),
        has_portfolio=bool(links),
        has_deployed_projects=any(p.has_production_evidence for p in projects),
        extraction_confidence="high" if len(raw_text) > 1200 and (projects or links) else "medium",
    )
    if not profile.projects:
        profile.extraction_warnings.append("No clearly separated project section was detected.")
    if not profile.has_github:
        profile.extraction_warnings.append("No GitHub link was detected.")
    if "intern" in lower:
        profile.seniority_level = "intern"
    elif "senior" in lower or "lead" in lower:
        profile.seniority_level = "senior"
    else:
        profile.seniority_level = "junior" if profile.projects else None
    profile.career_stage = _career_stage(raw_text, profile.seniority_level, profile.total_experience_months)
    return profile


def llm_extract(raw_text: str, target_role: str, baseline: CandidateProfile) -> CandidateProfile:
    prompt = f"""
Extract a developer CV profile for target_role "{target_role}".
Use the schema fields exactly. Use only evidence from the CV. Preserve explainability warnings.

Baseline heuristic extraction:
{baseline.model_dump_json()}

CV text:
{raw_text[:18000]}
"""
    profile = invoke_model_openrouter_first(prompt, CandidateProfile)
    profile.target_role = target_role
    profile.raw_cv_text = raw_text
    profile.projects = _sanitize_projects(profile.projects, raw_text, profile.name) or baseline.projects
    profile.total_experience_months = profile.total_experience_months or baseline.total_experience_months
    profile.current_role = profile.current_role or baseline.current_role
    profile.seniority_level = profile.seniority_level or baseline.seniority_level
    profile.career_stage = _career_stage(raw_text, profile.seniority_level, profile.total_experience_months)
    profile.has_github = bool(profile.has_github or baseline.has_github)
    profile.has_portfolio = bool(profile.has_portfolio or baseline.has_portfolio)
    profile.has_deployed_projects = any(p.has_production_evidence for p in profile.projects)
    profile.raw_extraction_json = profile.model_dump()
    return profile


def extract_profile(raw_text: str, target_role: str) -> CandidateProfile:
    baseline = deterministic_extract(raw_text, target_role)
    try:
        return llm_extract(raw_text, target_role, baseline)
    except Exception as exc:
        baseline.extraction_warnings.append(f"LLM extraction unavailable; deterministic extraction used. Reason: {exc}")
        baseline.raw_extraction_json = baseline.model_dump()
        return baseline
