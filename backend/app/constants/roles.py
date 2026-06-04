ROLE_LABELS = {
    "backend": "Backend Developer",
    "frontend": "Frontend Developer",
    "full_stack": "Full Stack Developer",
    "mobile": "Mobile Developer",
    "ai_ml": "AI/ML Engineer",
    "devops": "DevOps Engineer",
    "data_engineer": "Data Engineer",
    "data_scientist": "Data Scientist",
    "qa_automation": "QA Automation Engineer",
}

ROLE_FOCUS = {
    "backend": "API design, database depth, server-side frameworks, security, performance, deployment.",
    "frontend": "UI frameworks, CSS, accessibility, responsiveness, state management, live portfolio evidence.",
    "full_stack": "Frontend and backend breadth, API integration, databases, deployment, end-to-end ownership.",
    "mobile": "iOS, Android, Flutter, React Native, app architecture, release evidence, performance.",
    "ai_ml": "Python, ML frameworks, model training/deployment, RAG/agents, math, research, datasets.",
    "devops": "CI/CD, infrastructure as code, containers, cloud, monitoring, security, reliability.",
    "data_engineer": "Pipelines, SQL, warehouses, orchestration, Spark/Kafka, data modeling.",
    "data_scientist": "Statistics, experimentation, ML, visualization, research, communication of findings.",
    "qa_automation": "Test frameworks, CI integration, coverage, API/browser/performance testing, bug workflow.",
}

ROLE_WEIGHTS = {
    "backend": {"technical_skill": 20, "project_work": 25, "professional_experience": 20, "engineering_practices": 15, "role_fit": 15, "education_certifications": 3, "research": 0, "cv_quality": 2},
    "frontend": {"technical_skill": 20, "project_work": 25, "professional_experience": 20, "engineering_practices": 15, "role_fit": 15, "education_certifications": 3, "research": 0, "cv_quality": 2},
    "full_stack": {"technical_skill": 20, "project_work": 25, "professional_experience": 20, "engineering_practices": 15, "role_fit": 15, "education_certifications": 3, "research": 0, "cv_quality": 2},
    "mobile": {"technical_skill": 20, "project_work": 25, "professional_experience": 20, "engineering_practices": 15, "role_fit": 15, "education_certifications": 3, "research": 0, "cv_quality": 2},
    "ai_ml": {"technical_skill": 22, "project_work": 22, "professional_experience": 18, "engineering_practices": 12, "role_fit": 16, "education_certifications": 3, "research": 5, "cv_quality": 2},
    "devops": {"technical_skill": 20, "project_work": 20, "professional_experience": 20, "engineering_practices": 25, "role_fit": 12, "education_certifications": 1, "research": 0, "cv_quality": 2},
    "data_engineer": {"technical_skill": 20, "project_work": 24, "professional_experience": 20, "engineering_practices": 16, "role_fit": 15, "education_certifications": 3, "research": 0, "cv_quality": 2},
    "data_scientist": {"technical_skill": 20, "project_work": 22, "professional_experience": 18, "engineering_practices": 12, "role_fit": 16, "education_certifications": 3, "research": 5, "cv_quality": 2},
    "qa_automation": {"technical_skill": 20, "project_work": 22, "professional_experience": 20, "engineering_practices": 25, "role_fit": 10, "education_certifications": 1, "research": 0, "cv_quality": 2},
}

MODULE_LABELS = {
    "technical_skill": "Technical Skill Match",
    "project_work": "Project & Work Evidence",
    "professional_experience": "Professional Experience",
    "engineering_practices": "Engineering Practices",
    "role_fit": "Role-Specific Fit",
    "education_certifications": "Education & Certifications",
    "research": "Research & Publications",
    "cv_quality": "CV Quality & Communication",
}
