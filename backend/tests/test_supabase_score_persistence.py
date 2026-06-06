import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.schemas.cv import CandidateProfile, CandidateResult, ModuleScore, ScoreSummary, WorkspaceCategory
from app.services.supabase_scores import compute_cv_hash, persist_candidate_score


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSupabaseClient:
    def __init__(self, existing_users=None):
        self.existing_users = existing_users or []
        self.calls = []

    def get(self, url, *, params, headers):
        self.calls.append(("GET", url, params, headers, None))
        if url.endswith("/users"):
            return FakeResponse(self.existing_users[:1])
        return FakeResponse([])

    def post(self, url, *, params, headers, json):
        self.calls.append(("POST", url, params, headers, json))
        if url.endswith("/users"):
            return FakeResponse([{
                "id": "user-new",
                "email": json.get("email"),
                "full_name": json.get("full_name"),
                "role_preferences": json.get("role_preferences", []),
            }])
        if url.endswith("/cv_scores"):
            return FakeResponse([{
                "id": "score-1",
                "user_id": json["user_id"],
                "cv_hash": json["cv_hash"],
                "role_key": json["role_key"],
                "score": json["score"],
            }])
        return FakeResponse({})

    def patch(self, url, *, params, headers, json):
        self.calls.append(("PATCH", url, params, headers, json))
        return FakeResponse([{
            "id": params["id"].replace("eq.", ""),
            "email": "asif@example.com",
            "full_name": json.get("full_name", "Asif Khan"),
            "role_preferences": json.get("role_preferences", []),
        }])


def sample_result(email="asif@example.com"):
    profile = CandidateProfile(
        name="Asif Khan",
        email=email,
        target_role="ai_ml",
        raw_cv_text="Asif Khan\nPython FastAPI RAG",
        programming_languages=["Python"],
        frameworks_libraries=["FastAPI"],
        ml_ai_tools=["RAG"],
    )
    module = ModuleScore(
        module_key="technical_skill",
        module_label="Technical Skill Match",
        score=16,
        max_score=22,
        normalized_score=72.7,
        grade="Good",
        evidence_found=["Python and FastAPI"],
        missing_evidence=["Limited deployment evidence"],
        recommendations=["Add deployment metrics."],
        llm_reasoning="Solid technical evidence.",
    )
    summary = ScoreSummary(
        target_role="ai_ml",
        overall_score=74,
        overall_grade="Junior Developer",
        hiring_recommendation="Ready for junior positions",
        aggregate_confidence="high",
        top_strengths=["Python"],
        top_weaknesses=["Deployment evidence"],
        recommendations=["Add deployment metrics."],
        summary_narrative="This CV scores 74/100.",
    )
    return CandidateResult(
        candidate_id="candidate-1",
        status="complete",
        profile=profile,
        summary=summary,
        modules=[module],
        categories=[
            WorkspaceCategory(
                key="technical_skill",
                name="Technical Skill Match",
                normalized_score=72.7,
                grade_label="Good",
                verdict_sentence="Solid skill match.",
                evidence=["Python and FastAPI"],
                missing_evidence=["Limited deployment evidence"],
                recommendations=["Add deployment metrics."],
            )
        ],
    )


class SupabaseScorePersistenceTests(unittest.TestCase):
    def test_compute_cv_hash_is_stable_for_whitespace(self):
        self.assertEqual(
            compute_cv_hash("Asif\n\n Python "),
            compute_cv_hash("Asif\nPython"),
        )

    def test_creates_user_and_upserts_cv_score(self):
        client = FakeSupabaseClient()
        settings = SimpleNamespace(
            supabase_url="https://example.supabase.co",
            supabase_service_role_key="service-role-key",
        )

        with patch("app.services.supabase_scores.get_settings", return_value=settings):
            persisted = persist_candidate_score(sample_result(), http_client=client)

        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.user_id, "user-new")
        post_users = [call for call in client.calls if call[0] == "POST" and call[1].endswith("/users")]
        post_scores = [call for call in client.calls if call[0] == "POST" and call[1].endswith("/cv_scores")]
        self.assertEqual(post_users[0][4]["email"], "asif@example.com")
        self.assertEqual(post_users[0][4]["full_name"], "Asif Khan")
        self.assertEqual(post_users[0][4]["role_preferences"], ["ai_ml"])
        score_payload = post_scores[0][4]
        self.assertEqual(score_payload["user_id"], "user-new")
        self.assertEqual(score_payload["role_key"], "ai_ml")
        self.assertEqual(score_payload["role_label"], "AI/ML Engineer")
        self.assertEqual(score_payload["score"], 74)
        self.assertEqual(score_payload["matched_skills"], ["Python", "FastAPI", "RAG"])
        self.assertEqual(score_payload["missing_skills"], ["Limited deployment evidence"])
        self.assertEqual(score_payload["recommendations"]["candidate_id"], "candidate-1")

    def test_existing_user_preferences_are_merged(self):
        client = FakeSupabaseClient(existing_users=[{
            "id": "user-existing",
            "email": "asif@example.com",
            "full_name": "",
            "role_preferences": ["backend"],
        }])
        settings = SimpleNamespace(
            supabase_url="https://example.supabase.co",
            supabase_service_role_key="service-role-key",
        )

        with patch("app.services.supabase_scores.get_settings", return_value=settings):
            persist_candidate_score(sample_result(), http_client=client)

        patch_users = [call for call in client.calls if call[0] == "PATCH" and call[1].endswith("/users")]
        post_scores = [call for call in client.calls if call[0] == "POST" and call[1].endswith("/cv_scores")]
        self.assertEqual(patch_users[0][4]["role_preferences"], ["backend", "ai_ml"])
        self.assertEqual(patch_users[0][4]["full_name"], "Asif Khan")
        self.assertEqual(post_scores[0][4]["user_id"], "user-existing")

    def test_missing_config_skips_persistence(self):
        settings = SimpleNamespace(supabase_url=None, supabase_service_role_key=None)

        with patch("app.services.supabase_scores.get_settings", return_value=settings):
            persisted = persist_candidate_score(sample_result(), http_client=FakeSupabaseClient())

        self.assertIsNone(persisted)


if __name__ == "__main__":
    unittest.main()
