import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.schemas.cv import CandidateProfile, CandidateResult, Project, ScoreSummary
from app.services.category_views import apply_workspace_fields, build_category_views
from app.services.pipeline import create_pipeline_status, load_pipeline_status, process_cv, update_stage
from app.services.scoring.utils import make_module


class DummySettings:
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir


class PipelineStatusTests(unittest.TestCase):
    def test_status_transitions_are_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("app.services.pipeline.get_settings", return_value=DummySettings(Path(tmp))):
                create_pipeline_status("candidate-1", "backend")
                update_stage("candidate-1", "cv_upload", "completed", "CV uploaded successfully.", target_role="backend")
                update_stage("candidate-1", "extraction", "in_progress", "Parsing CV text.", target_role="backend")

                status = load_pipeline_status("candidate-1")

        self.assertIsNotNone(status)
        self.assertEqual(status.status, "processing")
        stages = {stage.key: stage for stage in status.stages}
        self.assertEqual(stages["cv_upload"].status, "completed")
        self.assertEqual(stages["extraction"].status, "in_progress")
        self.assertEqual(stages["extraction"].message, "Parsing CV text.")


class CategoryViewTests(unittest.TestCase):
    def test_category_views_include_extracted_project_content_and_narrative(self):
        profile = CandidateProfile(
            target_role="ai_ml",
            raw_cv_text="Built a deployed RAG platform with Python.",
            programming_languages=["Python"],
            ml_ai_tools=["LangChain", "RAG"],
            projects=[
                Project(
                    title="RAG Platform",
                    description="Built and deployed a RAG platform with measurable answer-quality improvements.",
                    technologies=["Python", "LangChain", "RAG"],
                    has_production_evidence=True,
                    has_measurable_impact=True,
                    has_ownership_signal=True,
                )
            ],
        )
        module = make_module(
            "project_work",
            18,
            22,
            ["Deployed RAG project"],
            ["Limited usage metrics"],
            {"impact": {"score": 4, "max": 5, "reasoning": "Some measurable signal"}},
            ["Add exact user or accuracy metrics."],
            "Project evidence is strong but metrics can be clearer.",
            "llm",
        )

        views = build_category_views(profile, [module])

        self.assertEqual(len(views), 1)
        self.assertEqual(views[0].key, "project_work")
        self.assertEqual(views[0].extracted_items[0].title, "RAG Platform")
        self.assertIn("Deployed RAG project", views[0].score_narrative)
        self.assertIn("Limited usage metrics", views[0].score_narrative)

    def test_workspace_fields_include_dynamic_role_fit_score(self):
        profile = CandidateProfile(
            target_role="ai_ml",
            raw_cv_text="Python RAG projects.",
            name="Asif Khan",
            programming_languages=["Python"],
        )
        project_module = make_module(
            "project_work",
            18,
            22,
            ["Project evidence"],
            [],
            {},
            [],
            "Project reasoning.",
            "deterministic",
        )
        role_fit_module = make_module(
            "role_fit",
            13.12,
            16,
            ["AI/ML overlap"],
            ["Limited production scale"],
            {},
            ["Add deployment metrics."],
            "Role-fit reasoning.",
            "hybrid",
        )
        summary = ScoreSummary(
            target_role="ai_ml",
            overall_score=74,
            overall_grade="Junior Developer",
            hiring_recommendation="Ready for junior positions",
            aggregate_confidence="high",
            summary_narrative="Strong project portfolio.",
        )
        category_views = build_category_views(profile, [project_module, role_fit_module])
        payload = apply_workspace_fields(
            candidate_id="candidate-workspace",
            profile=profile,
            summary=summary,
            modules=[project_module, role_fit_module],
            category_views=category_views,
        )

        self.assertEqual(payload["candidate_name"], "Asif Khan")
        self.assertEqual(payload["target_role"], "AI/ML Engineer")
        self.assertEqual(payload["total_score"], 74)
        self.assertEqual(payload["role_fit_score"], 82.0)
        self.assertEqual(payload["role_match_label"], "Strong Match")
        self.assertEqual([category.key for category in payload["categories"]], ["project_work", "role_fit"])


class PipelineLoggingTests(unittest.TestCase):
    def _cached_result(self, candidate_id: str) -> CandidateResult:
        profile = CandidateProfile(
            target_role="ai_ml",
            raw_cv_text="Cached CV text",
            programming_languages=["Python"],
        )
        summary = ScoreSummary(
            target_role="ai_ml",
            overall_score=82,
            overall_grade="Mid-Level Developer",
            hiring_recommendation="Ready for interviews",
            aggregate_confidence="high",
            summary_narrative="Cached score.",
        )
        return CandidateResult(
            candidate_id=candidate_id,
            status="complete",
            profile=profile,
            summary=summary,
            modules=[],
            categories=[],
        )

    def test_process_cv_cache_hit_skips_extraction_and_scoring(self):
        raw_text = "Cached CV text"
        cached = self._cached_result("candidate-cache")

        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "cv.pdf"
            pdf_path.write_bytes(b"%PDF")
            with patch("app.services.pipeline.get_settings", return_value=DummySettings(Path(tmp))):
                with patch("app.services.pipeline.extract_pdf_text", return_value=raw_text):
                    with patch("app.services.pipeline.load_cached_score", return_value=cached) as load_cache:
                        with patch("app.services.pipeline.extract_profile") as extract_profile:
                            with patch("app.services.pipeline.run_scoring_graph") as run_graph:
                                with patch("app.services.pipeline.store_score_cache") as store_cache:
                                    with patch("app.services.pipeline.persist_candidate_score") as persist_score:
                                        result = process_cv(pdf_path, "ai_ml", "candidate-cache")

                status = load_pipeline_status("candidate-cache")

        self.assertEqual(result.summary.overall_score, 82)
        self.assertEqual(status.status, "complete")
        load_cache.assert_called_once()
        self.assertEqual(load_cache.call_args.args[1:], ("ai_ml", "candidate-cache"))
        extract_profile.assert_not_called()
        run_graph.assert_not_called()
        store_cache.assert_not_called()
        persist_score.assert_not_called()

    def test_process_cv_logs_milestones_without_raw_cv_text(self):
        secret_raw_text = "SECRET_RAW_CV_TEXT candidate private details"
        profile = CandidateProfile(
            target_role="ai_ml",
            raw_cv_text=secret_raw_text,
            programming_languages=["Python"],
            projects=[
                Project(
                    title="RAG Platform",
                    description="Built a RAG platform.",
                    technologies=["Python", "RAG"],
                )
            ],
            extraction_confidence="high",
        )
        module = make_module(
            "technical_skill",
            15,
            22,
            ["Python skill evidence"],
            ["Limited deployment evidence"],
            {},
            ["Tie skills to shipped work."],
            "Technical evidence found.",
            "deterministic",
        )
        summary = ScoreSummary(
            target_role="ai_ml",
            overall_score=61,
            overall_grade="Intern / Trainee",
            hiring_recommendation="Ready for internship-level roles",
            aggregate_confidence="high",
            top_strengths=["Python skill evidence"],
            top_weaknesses=["Limited deployment evidence"],
            recommendations=["Tie skills to shipped work."],
            summary_narrative="This CV scores 61/100 for the selected role.",
        )

        def fake_graph(_profile):
            return [module], summary

        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "cv.pdf"
            pdf_path.write_bytes(b"%PDF")
            with patch("app.services.pipeline.get_settings", return_value=DummySettings(Path(tmp))):
                with patch("app.services.pipeline.extract_pdf_text", return_value=secret_raw_text):
                    with patch("app.services.pipeline.load_cached_score", return_value=None) as load_cache:
                        with patch("app.services.pipeline.extract_profile", return_value=profile):
                            with patch("app.services.pipeline.run_scoring_graph", side_effect=fake_graph) as run_graph:
                                with patch("app.services.pipeline.store_score_cache", return_value=True) as store_cache:
                                    with patch("app.services.pipeline.persist_candidate_score", return_value=None) as persist_score:
                                        with self.assertLogs("devlens.pipeline", level="INFO") as logs:
                                            result = process_cv(pdf_path, "ai_ml", "candidate-logs")

        joined = "\n".join(logs.output)
        self.assertEqual(result.status, "complete")
        load_cache.assert_called_once()
        run_graph.assert_called_once_with(profile)
        store_cache.assert_called_once()
        persist_score.assert_called_once()
        self.assertIn("Extraction started", joined)
        self.assertIn("Scoring completed", joined)
        self.assertIn("CV pipeline completed", joined)
        self.assertNotIn("SECRET_RAW_CV_TEXT", joined)


if __name__ == "__main__":
    unittest.main()
