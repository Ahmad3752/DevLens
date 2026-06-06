import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.cv import CandidateProfile
from app.schemas.jobs import RelevantJob
from app.services.jobs import (
    JOB_SELECT_COLUMNS,
    JOBS_CACHE_TTL_SECONDS,
    build_job_filters,
    build_jobs_cache_key,
    build_supabase_params,
    fetch_relevant_jobs,
)


class DummySettings:
    supabase_url = "https://example.supabase.co"
    supabase_service_role_key = "service-role-key"
    devlens_redis_url = None
    redis_url = None


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


class FakeHttpClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, *, params, headers):
        self.calls.append({"url": url, "params": params, "headers": headers})
        return FakeResponse(self.payload)


class FakeRedis:
    def __init__(self, cached=None, fail_get=False, fail_set=False):
        self.cached = cached
        self.fail_get = fail_get
        self.fail_set = fail_set
        self.get_calls = []
        self.setex_calls = []

    def get(self, key):
        self.get_calls.append(key)
        if self.fail_get:
            raise RuntimeError("redis down")
        return self.cached

    def setex(self, key, ttl, value):
        self.setex_calls.append((key, ttl, value))
        if self.fail_set:
            raise RuntimeError("redis down")
        return True


def sample_profile(role="ai_ml"):
    return CandidateProfile(
        target_role=role,
        raw_cv_text="Python FastAPI LangChain RAG projects.",
        programming_languages=["Python"],
        frameworks_libraries=["FastAPI", "LangChain"],
        databases=["PostgreSQL"],
        ml_ai_tools=["RAG"],
        seniority_level="junior",
    )


def sample_job(**overrides):
    payload = {
        "id": "job-1",
        "title": "AI Engineer",
        "company": "Example AI",
        "url": "https://example.com/job",
        "platform": "indeed",
        "platforms": ["indeed"],
        "city": "Karachi",
        "country": "Pakistan",
        "role_keys": ["ai_ml"],
        "role_labels": ["AI/ML Engineer"],
        "employment_type": "full-time",
        "experience_level": "junior",
        "is_internship": False,
        "is_remote": False,
        "workplace_type": "hybrid",
        "tech_stack": ["Python", "FastAPI", "PyTorch"],
        "requirements": ["Build ML APIs"],
        "responsibilities": ["Ship models"],
        "benefits": [],
        "salary_period": "unknown",
        "posted_at": "2026-06-01T00:00:00+00:00",
        "scraped_at": "2026-06-02T00:00:00+00:00",
    }
    payload.update(overrides)
    return payload


class RelevantJobsServiceTests(unittest.TestCase):
    def test_supabase_query_params_are_role_and_filter_scoped(self):
        filters = build_job_filters(
            employment_type="full-time",
            experience_level="junior",
            workplace_type="hybrid",
            limit=25,
        )

        params = build_supabase_params("ai_ml", filters)

        self.assertEqual(params["is_active"], "eq.true")
        self.assertEqual(params["country"], "eq.Pakistan")
        self.assertEqual(params["role_keys"], "cs.{ai_ml}")
        self.assertEqual(params["employment_type"], "eq.full-time")
        self.assertEqual(params["experience_level"], "eq.junior")
        self.assertEqual(params["workplace_type"], "eq.hybrid")
        self.assertNotIn("city", params)
        self.assertNotIn("is_remote", params)
        self.assertNotIn("is_internship", params)
        self.assertNotIn("tech_stack", params)
        self.assertEqual(params["limit"], "25")
        self.assertIn("posted_at.desc.nullslast", params["order"])
        self.assertNotIn("raw_payload", JOB_SELECT_COLUMNS)

    def test_cache_hit_returns_cached_rows_without_supabase(self):
        filters = build_job_filters(limit=10)
        cached = json.dumps([sample_job()])
        redis = FakeRedis(cached=cached)
        http_client = FakeHttpClient([])

        jobs, cache_status, metadata = fetch_relevant_jobs("candidate-1", sample_profile(), filters, http_client=http_client, redis_client=redis)

        self.assertEqual(cache_status, "hit")
        self.assertEqual(len(http_client.calls), 0)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "AI Engineer")
        self.assertEqual(jobs[0].city, "Karachi")
        self.assertEqual(metadata["source_rows"], 1)

    def test_cache_miss_queries_supabase_and_writes_ttl(self):
        filters = build_job_filters(employment_type="full-time", limit=5)
        redis = FakeRedis()
        http_client = FakeHttpClient([sample_job(city="Lahore")])

        with patch("app.services.jobs.get_settings", return_value=DummySettings()):
            jobs, cache_status, _ = fetch_relevant_jobs("candidate-1", sample_profile(), filters, http_client=http_client, redis_client=redis)

        self.assertEqual(cache_status, "miss")
        self.assertEqual(len(http_client.calls), 1)
        self.assertEqual(http_client.calls[0]["url"], "https://example.supabase.co/rest/v1/jobs")
        self.assertEqual(http_client.calls[0]["params"]["employment_type"], "eq.full-time")
        self.assertNotIn("city", http_client.calls[0]["params"])
        self.assertEqual(len(redis.setex_calls), 1)
        self.assertEqual(redis.setex_calls[0][1], JOBS_CACHE_TTL_SECONDS)
        self.assertEqual(jobs[0].city, "Lahore")

    def test_redis_failure_falls_back_to_supabase(self):
        filters = build_job_filters(limit=5)
        redis = FakeRedis(fail_get=True, fail_set=True)
        http_client = FakeHttpClient([sample_job()])

        with patch("app.services.jobs.get_settings", return_value=DummySettings()):
            jobs, cache_status, _ = fetch_relevant_jobs("candidate-1", sample_profile(), filters, http_client=http_client, redis_client=redis)

        self.assertEqual(cache_status, "error")
        self.assertEqual(len(http_client.calls), 1)
        self.assertEqual(len(jobs), 1)

    def test_cache_key_uses_devlens_namespace(self):
        filters = build_job_filters(employment_type="full-time", limit=50)

        key = build_jobs_cache_key("ai_ml", filters)

        self.assertRegex(key, r"^devlens:jobs:ai-ml:all:[a-f0-9]{16}$")

    def test_unsupported_role_is_rejected(self):
        with self.assertRaises(ValueError):
            fetch_relevant_jobs("candidate-1", sample_profile("unknown_role"), build_job_filters(), http_client=FakeHttpClient([]), redis_client=FakeRedis())


class RelevantJobsEndpointTests(unittest.TestCase):
    def test_candidate_jobs_endpoint_returns_job_browser_payload(self):
        profile = sample_profile()
        job = RelevantJob.model_validate(sample_job())

        with patch("app.routers.jobs.load_result", return_value=SimpleNamespace(profile=profile)):
            with patch("app.routers.jobs.fetch_relevant_jobs", return_value=([job], "miss", {"source_rows": 1})):
                response = TestClient(app).get("/candidates/candidate-1/jobs?limit=5")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["candidate_id"], "candidate-1")
        self.assertEqual(payload["role_key"], "ai_ml")
        self.assertEqual(payload["role_label"], "AI/ML Engineer")
        self.assertEqual(payload["cache_status"], "miss")
        self.assertEqual(payload["jobs"][0]["title"], "AI Engineer")
        self.assertNotIn("match_score", payload["jobs"][0])
        self.assertNotIn("matched_skills", payload["jobs"][0])
        self.assertNotIn("missing_skills", payload["jobs"][0])

    def test_candidate_jobs_endpoint_rejects_unsupported_candidate_role(self):
        with patch("app.routers.jobs.load_result", return_value=SimpleNamespace(profile=sample_profile("unknown_role"))):
            response = TestClient(app).get("/candidates/candidate-1/jobs")

        self.assertEqual(response.status_code, 400)

    def test_user_facing_jobs_code_does_not_import_scrapers_or_job_boards(self):
        paths = [
            Path("app/services/jobs.py"),
            Path("app/routers/jobs.py"),
        ]
        combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in paths)

        blocked_terms = ["jobscraperspider", "linkedin", "indeed.com", "rozee", "mustakbil"]
        for term in blocked_terms:
            with self.subTest(term=term):
                self.assertNotIn(term, combined)


if __name__ == "__main__":
    unittest.main()
