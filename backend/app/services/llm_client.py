import json
import logging
import re
from typing import Any, Type, TypeVar

from pydantic import BaseModel

from app.config import get_settings


JSON_SYSTEM = (
    "You are an expert developer CV evaluator. Return only valid JSON. "
    "Do not include markdown, prose, or code fences outside the JSON object."
)

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger("devlens.llm")


def _extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def _safe_error(exc: Exception) -> str:
    message = re.sub(r"\s+", " ", str(exc)).strip()
    if len(message) > 180:
        message = f"{message[:177]}..."
    return f"{type(exc).__name__}: {message}"


def _provider_name(factory) -> str:
    return {
        "_openrouter_llm": "openrouter",
        "_bedrock_llm": "bedrock",
    }.get(getattr(factory, "__name__", ""), getattr(factory, "__name__", "unknown"))


def _openrouter_llm():
    settings = get_settings()
    if not settings.openrouter_key:
        return None
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.openrouter_model,
        api_key=settings.openrouter_key,
        base_url=settings.openrouter_api_base,
        temperature=0.15,
        max_tokens=4096,
        default_headers={
            "HTTP-Referer": "http://127.0.0.1:5173",
            "X-Title": "DevLens",
        },
    )


def _bedrock_llm():
    settings = get_settings()
    from langchain_aws import ChatBedrockConverse

    return ChatBedrockConverse(
        model_id=settings.bedrock_model_id,
        region_name=settings.aws_region,
        temperature=0.15,
        max_tokens=4096,
    )


def invoke_json(prompt: str) -> dict[str, Any]:
    errors: list[str] = []
    for factory in (_openrouter_llm, _bedrock_llm):
        provider = _provider_name(factory)
        try:
            logger.info("LLM provider attempt provider=%s", provider)
            llm = factory()
            if llm is None:
                logger.info("LLM provider skipped provider=%s reason=not_configured", provider)
                continue
            response = llm.invoke([("system", JSON_SYSTEM), ("user", prompt)])
            parsed = _extract_json(str(response.content))
            logger.info("LLM provider success provider=%s", provider)
            return parsed
        except Exception as exc:
            safe = _safe_error(exc)
            logger.warning("LLM provider failed provider=%s error=%s", provider, safe)
            errors.append(f"{factory.__name__}: {safe}")
    raise RuntimeError("; ".join(errors) or "No LLM provider configured")


def invoke_bedrock_json(prompt: str, system: str = JSON_SYSTEM) -> dict[str, Any]:
    try:
        logger.info("LLM provider attempt provider=bedrock")
        llm = _bedrock_llm()
        response = llm.invoke([("system", system), ("user", prompt)])
        parsed = _extract_json(str(response.content))
        logger.info("LLM provider success provider=bedrock")
        return parsed
    except Exception as exc:
        safe = _safe_error(exc)
        logger.warning("LLM provider failed provider=bedrock error=%s", safe)
        raise RuntimeError(f"_bedrock_llm: {safe}") from exc


def invoke_bedrock_model(prompt: str, model: Type[T], system: str = JSON_SYSTEM) -> T:
    try:
        logger.info("LLM provider attempt provider=bedrock mode=structured")
        llm = _bedrock_llm()
        structured = llm.with_structured_output(model)
        response = structured.invoke([("system", system), ("user", prompt)])
        logger.info("LLM provider success provider=bedrock mode=structured")
        if isinstance(response, model):
            return response
        return model.model_validate(response)
    except Exception as exc:
        safe = _safe_error(exc)
        logger.warning("LLM provider failed provider=bedrock mode=structured error=%s", safe)
        raise RuntimeError(f"_bedrock_llm_structured: {safe}") from exc


def invoke_model(prompt: str, model: Type[BaseModel]) -> BaseModel:
    return model.model_validate(invoke_json(prompt))


def provider_status() -> dict[str, Any]:
    settings = get_settings()
    return {
        "openrouter": {
            "configured": bool(settings.openrouter_key),
            "model": settings.openrouter_model,
            "base_url": settings.openrouter_api_base,
        },
        "bedrock": {
            "configured": bool(settings.bedrock_model_id),
            "model": settings.bedrock_model_id,
            "region": settings.aws_region,
        },
    }
