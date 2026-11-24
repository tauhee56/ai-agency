from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.model_config import ModelConfig
from app.security.crypto import decrypt_secret

CEO_SYSTEM = (
    "You are the AI CEO of an autonomous AI company OS. The human is the Founder. "
    "Respond with a short acknowledgment and a structured plan. Prefer JSON with keys: "
    "acknowledgment (string), objectives (array of strings), next_steps (array of strings), "
    "risks (array of strings), open_questions (array of strings). No tool calls."
)


def get_default_model(db: Session, company_id: UUID) -> ModelConfig | None:
    return (
        db.query(ModelConfig)
        .filter(ModelConfig.company_id == company_id, ModelConfig.is_default.is_(True))
        .first()
        or db.query(ModelConfig).filter(ModelConfig.company_id == company_id).first()
    )


def _resolve_api_key(cfg: ModelConfig) -> str | None:
    settings = get_settings()
    if cfg.api_key_encrypted:
        try:
            return decrypt_secret(cfg.api_key_encrypted)
        except ValueError:
            pass
    if cfg.provider == "openai":
        return settings.openai_api_key
    if cfg.provider == "anthropic":
        return settings.anthropic_api_key
    if cfg.provider == "gemini":
        return settings.gemini_api_key
    return settings.openai_api_key


def _offline_stub(message: str) -> dict[str, Any]:
    plan = {
        "acknowledgment": "Acknowledged. Operating in Phase 1 CEO stub mode (no live model call).",
        "objectives": [
            "Clarify Founder intent from the latest message",
            "Propose a minimal execution outline for the autonomous company OS",
            "Identify what requires Founder approval later",
        ],
        "next_steps": [
            "Confirm company goals and constraints",
            "Configure a default LLM in Settings → Models",
            "Expand org chart in Phase 2 once foundation is stable",
        ],
        "risks": [
            "No live model configured — plan is heuristic",
            "Multi-agent execution deferred to Phase 3",
        ],
        "open_questions": [
            "What is the primary product outcome for the next sprint?",
            "Which model provider should be default?",
        ],
        "founder_message_echo": message[:500],
    }
    md = (
        f"### Acknowledgment\n{plan['acknowledgment']}\n\n"
        f"### Objectives\n" + "\n".join(f"- {x}" for x in plan["objectives"]) + "\n\n"
        f"### Next steps\n" + "\n".join(f"1. {x}" for x in plan["next_steps"]) + "\n\n"
        f"### Risks\n" + "\n".join(f"- {x}" for x in plan["risks"])
    )
    return {
        "acknowledgment": plan["acknowledgment"],
        "plan": plan,
        "raw_markdown": md,
        "model_used": None,
        "stub": True,
    }


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


async def _call_openai_compatible(
    *,
    base_url: str,
    api_key: str,
    model: str,
    message: str,
    extra: dict[str, Any],
) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    temperature = float(extra.get("temperature", 0.4))
    max_tokens = int(extra.get("max_tokens", 1200))
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": CEO_SYSTEM},
            {"role": "user", "content": message},
        ],
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=body)
        if resp.status_code >= 400:
            detail = resp.text[:400]
            raise RuntimeError(f"Model provider error ({resp.status_code}): {detail}")
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _call_anthropic(*, api_key: str, model: str, message: str, extra: dict[str, Any]) -> str:
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": int(extra.get("max_tokens", 1200)),
        "system": CEO_SYSTEM,
        "messages": [{"role": "user", "content": message}],
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=body)
        if resp.status_code >= 400:
            raise RuntimeError(f"Anthropic error ({resp.status_code}): {resp.text[:400]}")
        data = resp.json()
        parts = data.get("content") or []
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text")


async def advise(db: Session, *, company_id: UUID, message: str) -> dict[str, Any]:
    cfg = get_default_model(db, company_id)
    if cfg is None:
        return _offline_stub(message)

    api_key = _resolve_api_key(cfg)
    if not api_key:
        return _offline_stub(message)

    extra = cfg.extra or {}
    try:
        if cfg.provider in ("openai", "compatible", "local"):
            settings = get_settings()
            base = cfg.base_url or settings.openai_base_url or "https://api.openai.com/v1"
            content = await _call_openai_compatible(
                base_url=base,
                api_key=api_key,
                model=cfg.model_name,
                message=message,
                extra=extra,
            )
        elif cfg.provider == "anthropic":
            content = await _call_anthropic(
                api_key=api_key, model=cfg.model_name, message=message, extra=extra
            )
        elif cfg.provider == "gemini":
            # OpenAI-compatible Gemini proxy path via base_url preferred in P1.
            base = cfg.base_url or "https://generativelanguage.googleapis.com/v1beta/openai"
            content = await _call_openai_compatible(
                base_url=base,
                api_key=api_key,
                model=cfg.model_name,
                message=message,
                extra=extra,
            )
        else:
            return _offline_stub(message)
    except Exception as exc:
        # Clear client-facing error without stack traces.
        raise ValueError(str(exc)) from exc

    parsed = _extract_json(content)
    if parsed:
        acknowledgment = str(parsed.get("acknowledgment") or "Acknowledged.")
        return {
            "acknowledgment": acknowledgment,
            "plan": parsed,
            "raw_markdown": content,
            "model_used": f"{cfg.provider}:{cfg.model_name}",
            "stub": False,
        }

    return {
        "acknowledgment": "Acknowledged.",
        "plan": {"raw": content},
        "raw_markdown": content,
        "model_used": f"{cfg.provider}:{cfg.model_name}",
        "stub": False,
    }
