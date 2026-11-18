# GPUGO Edge PoC (server-side gateway)

**Это runnable demo для закрытого тестового контура, не production ingress.**

```bash
pip install -e ".[server,dev]"
export GPUGO_EDGE_API_KEY='<set-via-secret-manager>'
export GPUGO_MODEL='construction-analyzer'
export GPUGO_INTERNAL_MODEL_URL='http://127.0.0.1:8000/v1/chat/completions'
uvicorn server.gpugo_edge.app:app --host 127.0.0.1 --port 8080
```

В этом примере backend vLLM доступен только на loopback. На production HTTPS termination и authorization должны быть реализованы на защищённом ingress; **не размещайте PoC edge публично**.

API принимает OpenAI-compatible форму, но **сам извлекает и повторно проверяет** только `issues[*].{index,category,severity,metrics}`. Клиентский `system` prompt не передаёт; системная инструкция фиксируется на сервере. Любые поля `raw_text`, `filename`, `drawing_code`, `person` или произвольный контекст приводят к 422. Ответ backend заново проверяется и перепаковывается.

### До реальных пилотов нужны
- OAuth/OIDC или подписанные короткоживущие токены по tenant/project; не один static API key.
- API gateway с HTTPS, mTLS/VPN при необходимости, rate limits, quotas, detection of replay, audit metadata.
- Продуманное отсутствие логирования prompt и response на прокси/vLLM и network controls.
- Secrets rotation, health/metrics, model version pin, GPU observability.
- Penetration/security review, customer security approval, лицензии моделей, backup/failover policy.

Связанные документы: [контракт](../../docs/implementation/08-api-contract.md), [безопасность](../../docs/implementation/04-security.md), [4×6000D](../../docs/implementation/05-gpugo-inference.md).
