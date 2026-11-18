"""Fail-closed, minimal-context, client-side gateway adapter for GPUGO inference.

Never send raw documents, names, drawing codes, issue.message or source row IDs.
Production server-side policy/auth is an independent implementation requirement.
"""
from __future__ import annotations

import json
import os
from urllib.parse import urlparse

import httpx

from .models import Issue

CATEGORIES = frozenset({
    "page_count_mismatch", "page_overlap", "missing_link", "missing_review_status",
    "invalid_date_order", "reference_mismatch", "missing_evidence", "unverified_revision",
})
SEVERITIES = frozenset({"info", "review", "high"})
METRICS = frozenset({"declared_count", "calculated_count", "conflict_count"})
ACTIONS = frozenset({"check_source", "request_clarification", "manual_review", "no_action"})
MAX_ISSUES = 10

SYSTEM_PROMPT = (
    "You advise an engineer about ABSTRACT construction-document consistency issues. "
    "All inputs are pseudonymized categories and counts, not construction facts. "
    "Do not guess identity, fabricate evidence, claim any field work or legal acceptance. "
    "Reply with compact JSON only: "
    '{"recommendations":[{"index":1,"action":"check_source","rationale":"..."}]}. '
    "Action must be check_source, request_clarification, manual_review, or no_action."
)


class GatewayError(RuntimeError):
    pass


def safe_batch(issues: list[Issue]) -> dict:
    if not 1 <= len(issues) <= MAX_ISSUES:
        raise GatewayError(f"Ожидается 1–{MAX_ISSUES} замечаний")
    exported: list[dict] = []
    for index, issue in enumerate(issues, start=1):
        if issue.category not in CATEGORIES or issue.severity not in SEVERITIES:
            raise GatewayError("Недопустимая категория или важность")
        if not isinstance(issue.metrics, dict):
            raise GatewayError("Метрики должны быть словарём")
        if any(k not in METRICS or type(v) is not int or not 0 <= v <= 100_000 for k, v in issue.metrics.items()):
            raise GatewayError("Недопустимые поля или значения метрик")
        exported.append({
            "index": index,
            "category": issue.category,
            "severity": issue.severity,
            "metrics": dict(issue.metrics),
        })
    return {"issues": exported}


def validate_endpoint(url: str, allowed_hosts: set[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise GatewayError("Для GPUGO разрешён только HTTPS")
    if parsed.hostname.lower() not in {host.strip().lower() for host in allowed_hosts if host.strip()}:
        raise GatewayError("Домен не находится в списке разрешённых GPUGO endpoints")
    if parsed.path != "/v1/chat/completions" or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise GatewayError("Неверный путь или небезопасные параметры URL")


def validate_recommendations(value: object, issue_count: int) -> list[dict]:
    if not isinstance(value, dict) or set(value) != {"recommendations"}:
        raise GatewayError("Ответ AI не соответствует схеме")
    rows = value["recommendations"]
    if not isinstance(rows, list) or len(rows) > issue_count:
        raise GatewayError("Неверное количество рекомендаций")
    seen: set[int] = set()
    for item in rows:
        if not isinstance(item, dict) or set(item) != {"index", "action", "rationale"}:
            raise GatewayError("Неизвестные поля в ответе AI")
        idx, action, rationale = item["index"], item["action"], item["rationale"]
        if type(idx) is not int or idx not in range(1, issue_count + 1) or idx in seen:
            raise GatewayError("Повторён или придуман индекс замечания")
        if action not in ACTIONS or not isinstance(rationale, str) or not 1 <= len(rationale) <= 400:
            raise GatewayError("Недопустимая рекомендация")
        seen.add(idx)
    return rows


class GPUGOGateway:
    def __init__(self, url: str | None = None, token: str | None = None, model: str | None = None):
        self.url = url if url is not None else os.environ.get("GPUGO_INFERENCE_URL", "")
        self.token = token if token is not None else os.environ.get("GPUGO_INFERENCE_TOKEN", "")
        self.model = model if model is not None else os.environ.get("GPUGO_MODEL", "construction-analyzer")
        self.allowed = set(os.environ.get("GPUGO_ALLOWED_HOSTS", "").split(","))
        if not self.url or not self.token:
            raise GatewayError("GPUGO не настроен: работа только офлайн")
        validate_endpoint(self.url, self.allowed)
        if not self.model or len(self.model) > 80:
            raise GatewayError("Неправильный идентификатор модели")

    def explain(self, issues: list[Issue]) -> list[dict]:
        # Explicit invocation ONLY: GUI must show safe_batch() to the operator first.
        safe = safe_batch(issues)
        request = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(safe, ensure_ascii=True, separators=(",", ":"))},
            ],
            "temperature": 0,
            "max_tokens": 400,
            "stream": False,
        }
        try:
            with httpx.Client(timeout=30.0, follow_redirects=False, trust_env=False) as client:
                response = client.post(
                    self.url,
                    headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
                    json=request,
                )
                response.raise_for_status()
                if len(response.content) > 16_384:
                    raise GatewayError("Ответ модели слишком большой")
                envelope = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Avoid logging request body, model response or auth headers.
            raise GatewayError("Сеть/шлюз GPUGO вернул ошибку; локальные данные не изменены") from None
        try:
            content = envelope["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("Expected plain JSON string")
            return validate_recommendations(json.loads(content), len(issues))
        except (ValueError, KeyError, IndexError, TypeError, GatewayError):
            raise GatewayError("Ответ модели не прошёл контроль формата; изменения не внесены") from None
