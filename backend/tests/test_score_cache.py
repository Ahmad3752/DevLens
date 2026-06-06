import json
import unittest

from app.schemas.cv import CandidateProfile, CandidateResult, ScoreSummary
from app.services.score_cache import SCORE_CACHE_TTL_SECONDS, build_score_cache_key, load_cached_score, store_score_cache


class FakeRedis:
    def __init__(self, cached=None, fail=False):
        self.cached = cached
        self.fail = fail
        self.get_calls = []
        self.setex_calls = []

    def get(self, key):
        self.get_calls.append(key)
        if self.fail:
            raise RuntimeError("redis down")
        return self.cached

    def setex(self, key, ttl, value):
        self.setex_calls.append((key, ttl, value))
        if self.fail:
            raise RuntimeError("redis down")
        return True


def sample_result(candidate_id="candidate-old"):
    return CandidateResult(
        candidate_id=candidate_id,
        status="complete",
        profile=CandidateProfile(
            name="Asif Khan",
            email="asif@example.com",
            target_role="ai_ml",
            raw_cv_text="Asif Khan\nPython FastAPI RAG",
            programming_languages=["Python"],
        ),
        summary=ScoreSummary(
            target_role="ai_ml",
            overall_score=74,
            overall_grade="Junior Developer",
            hiring_recommendation="Ready for junior roles",
            aggregate_confidence="high",
            summary_narrative="This CV scores 74/100.",
        ),
        modules=[],
        categories=[],
    )


class ScoreCacheTests(unittest.TestCase):
    def test_score_cache_key_uses_devlens_namespace(self):
        key = build_score_cache_key("abc123", "ai_ml")

        self.assertEqual(key, "devlens:score:abc123:ai_ml")

    def test_load_cached_score_replaces_candidate_id(self):
        cached_payload = sample_result("candidate-old").model_dump_json()
        redis = FakeRedis(cached=cached_payload)

        result = load_cached_score("abc123", "ai_ml", "candidate-new", redis_client=redis)

        self.assertIsNotNone(result)
        self.assertEqual(result.candidate_id, "candidate-new")
        self.assertEqual(result.summary.overall_score, 74)
        self.assertEqual(redis.get_calls, ["devlens:score:abc123:ai_ml"])

    def test_store_score_cache_sets_seven_day_ttl(self):
        redis = FakeRedis()
        result = sample_result()

        stored = store_score_cache("abc123", "ai_ml", result, redis_client=redis)

        self.assertTrue(stored)
        self.assertEqual(redis.setex_calls[0][0], "devlens:score:abc123:ai_ml")
        self.assertEqual(SCORE_CACHE_TTL_SECONDS, 60 * 60 * 24 * 7)
        self.assertEqual(redis.setex_calls[0][1], SCORE_CACHE_TTL_SECONDS)
        self.assertEqual(json.loads(redis.setex_calls[0][2])["candidate_id"], "candidate-old")

    def test_redis_failures_are_non_fatal(self):
        redis = FakeRedis(fail=True)

        self.assertIsNone(load_cached_score("abc123", "ai_ml", "candidate-new", redis_client=redis))
        self.assertFalse(store_score_cache("abc123", "ai_ml", sample_result(), redis_client=redis))


if __name__ == "__main__":
    unittest.main()
