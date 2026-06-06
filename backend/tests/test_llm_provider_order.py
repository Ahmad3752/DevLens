import unittest
from unittest.mock import patch

from pydantic import BaseModel

from app.schemas.cv import CandidateProfile
from app.services import extractor
from app.services import llm_client


class TinyResponse(BaseModel):
    ok: bool


class FakeStructuredLLM:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    def invoke(self, _messages):
        if self.error:
            raise self.error
        return self.response


class FakeLLM:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    def with_structured_output(self, _model):
        return FakeStructuredLLM(self.response, self.error)


class LLMProviderOrderTests(unittest.TestCase):
    def test_extraction_uses_openrouter_first_structured_model(self):
        baseline = CandidateProfile(
            target_role="ai_ml",
            raw_cv_text="Asif Khan\nPython RAG",
            name="Asif Khan",
            programming_languages=["Python"],
        )
        refined = baseline.model_copy(update={"extraction_confidence": "high"})

        with patch("app.services.extractor.invoke_model_openrouter_first", return_value=refined) as invoke:
            result = extractor.llm_extract("Asif Khan\nPython RAG", "ai_ml", baseline)

        self.assertEqual(result.extraction_confidence, "high")
        invoke.assert_called_once()

    def test_openrouter_first_structured_model_falls_back_to_bedrock(self):
        attempts = []

        def openrouter():
            attempts.append("openrouter")
            return FakeLLM(error=RuntimeError("openrouter unavailable"))

        def bedrock():
            attempts.append("bedrock")
            return FakeLLM(response={"ok": True})

        with patch("app.services.llm_client._openrouter_llm", new=openrouter):
            with patch("app.services.llm_client._bedrock_llm", new=bedrock):
                result = llm_client.invoke_model_openrouter_first("return ok", TinyResponse)

        self.assertEqual(result.ok, True)
        self.assertEqual(attempts, ["openrouter", "bedrock"])

    def test_bedrock_first_structured_model_falls_back_to_openrouter(self):
        attempts = []

        def bedrock():
            attempts.append("bedrock")
            return FakeLLM(error=RuntimeError("bedrock unavailable"))

        def openrouter():
            attempts.append("openrouter")
            return FakeLLM(response={"ok": True})

        with patch("app.services.llm_client._bedrock_llm", new=bedrock):
            with patch("app.services.llm_client._openrouter_llm", new=openrouter):
                result = llm_client.invoke_model_bedrock_first("return ok", TinyResponse)

        self.assertEqual(result.ok, True)
        self.assertEqual(attempts, ["bedrock", "openrouter"])


if __name__ == "__main__":
    unittest.main()
