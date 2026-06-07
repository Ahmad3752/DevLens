import unittest
from unittest.mock import patch

from app.schemas.cv import CandidateProfile, Project, Publication
from app.constants.roles import ROLE_WEIGHTS
from app.services.scoring import llm_modules
from app.services.scoring.graph import run_scoring_graph
from app.services.scoring.modules import engineering_practices, professional_experience, project_work, score_one
from app.services.scoring.utils import grade, score_tier


class DynamicScoringTests(unittest.TestCase):
    def setUp(self):
        self._llm_modules = set(llm_modules.LLM_MODULES)
        self._hybrid_modules = set(llm_modules.HYBRID_MODULES)
        llm_modules.LLM_MODULES.clear()
        llm_modules.HYBRID_MODULES.clear()

    def tearDown(self):
        llm_modules.LLM_MODULES.clear()
        llm_modules.HYBRID_MODULES.clear()
        llm_modules.LLM_MODULES.update(self._llm_modules)
        llm_modules.HYBRID_MODULES.update(self._hybrid_modules)

    def _profile(self, *, role="ai_ml", stage="intern", months=2, projects=None, rich=False):
        projects = projects if projects is not None else [
            Project(
                title="Production RAG Platform",
                description="Built and deployed RAG platform with LangChain, PyTorch, FastAPI, and improved answer accuracy 20%.",
                technologies=["Python", "PyTorch", "LangChain", "RAG", "FastAPI"],
                has_production_evidence=True,
                has_measurable_impact=True,
                has_ownership_signal=True,
                complexity_level="high",
            ),
            Project(
                title="Computer Vision Model",
                description="Built PyTorch classifier and achieved 85% accuracy.",
                technologies=["Python", "PyTorch"],
                has_measurable_impact=True,
                has_ownership_signal=True,
            ),
        ]
        return CandidateProfile(
            target_role=role,
            raw_cv_text=("testing github actions docker aws security performance accuracy users course " * 300) if rich else ("student ai ml " * 300),
            programming_languages=["Python", "SQL"] if rich else ["Python"],
            frameworks_libraries=["FastAPI"] if rich else [],
            databases=["PostgreSQL"] if rich else [],
            cloud_devops_tools=["Docker", "AWS", "GitHub Actions"] if rich else [],
            testing_tools=["Pytest"] if rich else [],
            ml_ai_tools=["PyTorch", "Scikit-learn", "TensorFlow", "Pandas", "NumPy", "LangChain", "RAG"] if rich else ["PyTorch", "Scikit-learn"],
            architecture_practices=["CI/CD", "Security", "Performance"] if rich else [],
            projects=projects,
            total_experience_months=months,
            seniority_level=stage if stage in {"intern", "junior", "mid", "senior"} else None,
            career_stage=stage,
            extraction_confidence="high",
            highest_degree="BS Computer Science",
            degree_is_cs_related=True,
            certifications=["AWS ML"] if rich else [],
            publications=[Publication(title="ML paper", indexing="IEEE", is_indexed=True)] if rich else [],
            has_github=rich,
            has_deployed_projects=any(project.has_production_evidence for project in projects),
        )

    def test_score_tier_labels_match_product_bands(self):
        cases = [
            (39, "Not Ready"),
            (40, "Entry Candidate"),
            (55, "Intern / Trainee"),
            (70, "Junior Developer"),
            (80, "Mid-Level Developer"),
            (90, "Senior Developer"),
        ]
        for score, label in cases:
            with self.subTest(score=score):
                self.assertEqual(grade(score), label)
                self.assertEqual(score_tier(score)["label"], label)

    def test_ai_ml_intern_scores_dynamically_inside_intern_band(self):
        strong = self._profile()
        weak = self._profile(
            stage="student",
            months=0,
            projects=[
                Project(
                    title="ML Classifier",
                    description="Built a small Python classifier for a course project.",
                    technologies=["Python", "Scikit-learn"],
                    has_ownership_signal=True,
                )
            ],
        )

        _, strong_summary = run_scoring_graph(strong)
        _, weak_summary = run_scoring_graph(weak)

        self.assertGreater(strong_summary.overall_score, weak_summary.overall_score)
        self.assertEqual(strong_summary.overall_grade, grade(strong_summary.overall_score))
        self.assertEqual(weak_summary.overall_grade, grade(weak_summary.overall_score))

    def test_role_mismatch_stays_not_ready(self):
        profile = self._profile(role="mobile")
        _, summary = run_scoring_graph(profile)
        self.assertLess(summary.overall_score, 40)
        self.assertEqual(summary.overall_grade, "Not Ready")

    def test_professional_profiles_gain_raw_score_with_stronger_experience(self):
        rich_projects = [
            Project(
                title="AI API Service",
                description="Built deployed ML API with Python FastAPI PyTorch and monitoring improved latency 20%.",
                technologies=["Python", "PyTorch", "FastAPI", "PostgreSQL", "Docker", "AWS"],
                has_production_evidence=True,
                has_measurable_impact=True,
                has_ownership_signal=True,
                complexity_level="high",
            ),
            Project(
                title="RAG Assistant",
                description="Built LangChain RAG system deployed for users with source cited retrieval.",
                technologies=["Python", "LangChain", "RAG", "FAISS"],
                has_production_evidence=True,
                has_measurable_impact=True,
                has_ownership_signal=True,
                complexity_level="high",
            ),
            Project(
                title="Model Ops Pipeline",
                description="Led MLflow deployment pipeline with Docker and measurable reliability gains.",
                technologies=["Python", "MLflow", "Docker"],
                has_production_evidence=True,
                has_measurable_impact=True,
                has_ownership_signal=True,
                complexity_level="high",
            ),
        ]
        summaries = []
        for stage, months in [("junior", 18), ("mid", 36), ("senior", 72)]:
            with self.subTest(stage=stage):
                _, summary = run_scoring_graph(self._profile(stage=stage, months=months, projects=rich_projects, rich=True))
                self.assertEqual(summary.overall_grade, grade(summary.overall_score))
                summaries.append(summary)

        self.assertLess(summaries[0].overall_score, summaries[1].overall_score)
        self.assertLess(summaries[1].overall_score, summaries[2].overall_score)

    def test_engineering_practices_uses_strict_partial_credit(self):
        profile = CandidateProfile(
            target_role="ai_ml",
            raw_cv_text=(
                "GitHub Actions CI/CD pipelines MLOps LLMOps REST GraphQL Microservices "
                "LangChain architecture AWS SageMaker Bedrock Lambda Azure App Services "
                "GCP Vertex AI Cloud Run deployed identity fraud reduction 70%"
            ),
            cloud_devops_tools=["AWS", "Azure", "GCP", "Docker", "GitHub Actions"],
            architecture_practices=["REST", "GraphQL", "Microservices"],
            has_deployed_projects=True,
        )

        scored = engineering_practices(profile, 12)

        self.assertEqual(scored.score, 5.5)
        self.assertEqual(scored.normalized_score, 45.83)
        self.assertEqual(scored.sub_scores["testing"]["score"], 0)
        self.assertEqual(scored.sub_scores["version_control"]["score"], 0.5)
        self.assertEqual(scored.sub_scores["ci_cd"]["score"], 1.0)
        self.assertEqual(scored.sub_scores["architecture"]["score"], 1.5)
        self.assertEqual(scored.sub_scores["security_performance"]["score"], 0.5)
        self.assertEqual(scored.sub_scores["deployment"]["score"], 2.0)

    def test_all_modules_obey_sub_score_invariants(self):
        profile = self._profile(stage="senior", months=72, rich=True)
        modules = [
            score_one(key, max_score=max_score, profile=profile)
            for key, max_score in ROLE_WEIGHTS[profile.target_role].items()
            if max_score > 0
        ]

        self.assertEqual(len(modules), 8)
        for module in modules:
            with self.subTest(module=module.module_key):
                sub_scores = module.sub_scores.values()
                self.assertTrue(module.sub_scores)
                self.assertTrue(all(float(item["score"]) <= float(item["max"]) for item in sub_scores))
                self.assertAlmostEqual(sum(float(item["score"]) for item in module.sub_scores.values()), module.score, places=2)
                self.assertAlmostEqual(sum(float(item["max"]) for item in module.sub_scores.values()), module.max_score, places=2)

    def test_overall_score_is_raw_sum_of_module_scores(self):
        profile = self._profile(stage="senior", months=72, rich=True)
        modules, summary = run_scoring_graph(profile)
        expected = round((sum(module.score for module in modules) / sum(module.max_score for module in modules)) * 100, 2)

        self.assertEqual(summary.overall_score, expected)
        self.assertEqual(summary.overall_grade, grade(expected))


class BedrockScoringTests(unittest.TestCase):
    def _baseline_profile(self):
        return CandidateProfile(
            target_role="ai_ml",
            raw_cv_text="Built deployed RAG project with Python PyTorch LangChain.",
            programming_languages=["Python"],
            ml_ai_tools=["PyTorch", "LangChain", "RAG"],
            projects=[
                Project(
                    title="RAG Platform",
                    description="Built and deployed RAG project with LangChain and PyTorch.",
                    technologies=["Python", "PyTorch", "LangChain", "RAG"],
                    has_production_evidence=True,
                    has_ownership_signal=True,
                )
            ],
        )

    def test_project_work_uses_bedrock_first_structured_response(self):
        profile = self._baseline_profile()
        baseline = project_work(profile, 22)
        response = {
            "score": 12.5,
            "confidence": "high",
            "evidence_found": ["Valid deployed RAG project"],
            "missing_evidence": ["Limited metrics"],
            "sub_scores": {"valid_project_count": {"score": 2.2, "max": 10, "reasoning": "Solid but not complete"}},
            "recommendations": ["Add measurable impact"],
            "llm_reasoning": "Bedrock judged the project evidence.",
        }
        with patch("app.services.scoring.llm_modules.invoke_model_bedrock_first", return_value=llm_modules.StructuredModuleScore.model_validate(response)):
            scored = llm_modules.llm_score_module("project_work", profile, 22, baseline)
        self.assertAlmostEqual(scored.score, sum(item["score"] for item in scored.sub_scores.values()), places=2)
        self.assertEqual(scored.scoring_method, "llm")
        self.assertEqual(scored.confidence, "high")

    def test_llm_sub_scores_are_clamped_and_drive_module_score(self):
        profile = CandidateProfile(
            target_role="ai_ml",
            raw_cv_text="Senior AI engineer from 2020 to 2024 building deployed RAG systems.",
            programming_languages=["Python"],
            total_experience_months=48,
            seniority_level="mid",
            current_role="Machine Learning Engineer",
            projects=[
                Project(
                    title="RAG Platform",
                    description="Built deployed RAG project with LangChain and PyTorch.",
                    technologies=["Python", "PyTorch", "LangChain", "RAG"],
                    has_production_evidence=True,
                )
            ],
        )
        baseline = professional_experience(profile, 18)
        response = {
            "score": 18,
            "confidence": "high",
            "evidence_found": ["Professional AI work"],
            "missing_evidence": [],
            "sub_scores": {
                "date_and_role_clarity": {"score": 1.7, "max": 99, "reasoning": "LLM over-scored this field."},
                "unknown_extra": {"score": 10, "max": 10, "reasoning": "Should be ignored."},
            },
            "recommendations": [],
            "llm_reasoning": "LLM top-level score should not control final score.",
        }

        with self.assertLogs("devlens.scoring", level="WARNING"):
            with patch("app.services.scoring.llm_modules.invoke_model_bedrock_first", return_value=llm_modules.StructuredModuleScore.model_validate(response)):
                scored = llm_modules.llm_score_module("professional_experience", profile, 18, baseline)

        self.assertEqual(scored.sub_scores["date_and_role_clarity"]["score"], scored.sub_scores["date_and_role_clarity"]["max"])
        self.assertEqual(scored.sub_scores["date_and_role_clarity"]["max"], 0.9)
        self.assertNotIn("unknown_extra", scored.sub_scores)
        self.assertAlmostEqual(scored.score, sum(item["score"] for item in scored.sub_scores.values()), places=2)
        self.assertAlmostEqual(sum(item["max"] for item in scored.sub_scores.values()), scored.max_score, places=2)

    def test_invalid_bedrock_response_falls_back_in_score_one(self):
        llm_modules.LLM_MODULES.add("project_work")
        profile = self._baseline_profile()
        with patch("app.services.scoring.llm_modules.invoke_model_bedrock_first", side_effect=ValueError("invalid structured output")):
            scored = score_one("project_work", profile, 22)
        self.assertEqual(scored.scoring_method, "deterministic")
        self.assertIn("LLM scoring unavailable", scored.llm_reasoning)

    def test_unavailable_bedrock_falls_back_in_score_one(self):
        llm_modules.HYBRID_MODULES.add("professional_experience")
        profile = self._baseline_profile()
        with patch("app.services.scoring.llm_modules.invoke_model_bedrock_first", side_effect=RuntimeError("aws and openrouter unavailable")):
            scored = score_one("professional_experience", profile, 18)
        self.assertEqual(scored.scoring_method, "hybrid")
        self.assertIn("LLM scoring unavailable", scored.llm_reasoning)


if __name__ == "__main__":
    unittest.main()
