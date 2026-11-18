"""Minimal GPUGO inference edge, rejecting any free-text construction input.

PoC controls: static bearer auth, strict JSON input/output, loopback-only vLLM,
no payload logs, size limits, no forwarding to arbitrary URLs.
Production still needs real tenant auth, replay protection, quotas, logging policy,
rate limits, WAF, threat review and mTLS/VPN where needed.
"""
from __future__ import annotations

import json
import os
import secrets
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from construction_docs.gateway import (
    ACTIONS, CATEGORIES, METRICS, SEVERITIES, SYSTEM_PROMPT, validate_recommendations,
)

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str
    content: str = Field(max_length=4_000)


class CompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(max_length=80)
    messages: list[ChatMessage] = Field(min_length=2, max_length=2)
    temperature: float = 0
    max_tokens: int = Field(ge=1, le=400)
    stream: bool = False


def _require_key(auth: str | None) -> None:
    configured = os.environ.get("GPUGO_EDGE_API_KEY", "")
    provided = auth[7:] if auth and auth.startswith("Bearer ") else ""
    if not configured or not secrets.compare_digest(provided, configured):
        raise HTTPException(status_code=401, detail="Unauthorized")


def validate_safe_request(req: CompletionRequest) -> dict:
    if [m.role for m in req.messages] != ["system", "user"]:
        raise HTTPException(status_code=422, detail="Invalid message roles")
    if req.stream or req.temperature != 0 or req.max_tokens > 400:
        raise HTTPException(status_code=422, detail="Unsupported inference settings")
    allowed_model = os.environ.get("GPUGO_MODEL", "construction-analyzer")
    if req.model != allowed_model:
        raise HTTPException(status_code=422, detail="Model not allowed")
    try:
        payload = json.loads(req.messages[1].content)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Expected JSON issue batch")
    if not isinstance(payload, dict) or set(payload) != {"issues"}:
        raise HTTPException(status_code=422, detail="Unexpected data fields")
    issues = payload["issues"]
    if not isinstance(issues, list) or not (1 <= len(issues) <= 10):
        raise HTTPException(status_code=422, detail="Invalid issue count")
    clean = []
    for i, issue in enumerate(issues, 1):
        if not isinstance(issue, dict) or set(issue) != {"index", "category", "severity", "metrics"}:
            raise HTTPException(status_code=422, detail="Unexpected issue fields")
        metrics = issue["metrics"]
        if (
            type(issue["index"]) is not int or issue["index"] != i or
            issue["category"] not in CATEGORIES or issue["severity"] not in SEVERITIES or
            not isinstance(metrics, dict) or any(
                key not in METRICS or type(value) is not int or not (0 <= value <= 100_000)
                for key, value in metrics.items()
            )
        ):
            raise HTTPException(status_code=422, detail="Unsafe issue payload")
        clean.append(issue)
    return {"issues": clean}


def backend_url() -> str:
    # Restrict prototype worker to local-only to prevent SSRF or public raw vLLM access.
    url = os.environ.get(
        "GPUGO_INTERNAL_MODEL_URL", "http://127.0.0.1:8000/v1/chat/completions"
    )
    p = urlparse(url)
    if p.scheme != "http" or p.hostname not in {"127.0.0.1", "localhost"}:
        raise HTTPException(status_code=503, detail="Backend not configured for safe loopback")
    if p.path != "/v1/chat/completions" or p.username or p.password or p.query or p.fragment:
        raise HTTPException(status_code=503, detail="Unsafe backend URL")
    return url


@app.get("/healthz")
def healthz():
    # No secret or internal host information in unauthenticated health response.
    return {"status": "ok", "component": "gpugo-edge-poc"}


@app.post("/v1/chat/completions")
async def completion(req: CompletionRequest, authorization: str | None = Header(default=None)):
    _require_key(authorization)
    safe = validate_safe_request(req)
    body = {
        "model": req.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(safe, ensure_ascii=True, separators=(",", ":"))},
        ],
        "stream": False,
        "temperature": 0,
        "max_tokens": min(req.max_tokens, 400),
    }
    try:
        async with httpx.AsyncClient(timeout=30.0, trust_env=False, follow_redirects=False) as client:
            response = await client.post(backend_url(), json=body)
            response.raise_for_status()
            if len(response.content) > 16_384:
                raise ValueError("Oversized backend response")
            remote = response.json()
            generated = json.loads(remote["choices"][0]["message"]["content"])
            checked = validate_recommendations(generated, len(safe["issues"]))
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, RuntimeError):
        raise HTTPException(status_code=502, detail="Inference backend failed validation")

    # Rebuild the response ourselves. Never relay arbitrary model headers or payload metadata.
    return {
        "id": "edge-recommendation",
        "object": "chat.completion",
        "model": req.model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": json.dumps({"recommendations": checked}, ensure_ascii=False),
            },
            "finish_reason": "stop",
        }],
    }
