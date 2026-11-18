# Контракты внешнего шлюза GPUGO — версия 0

> **Только действующий demo API (enum+числа); не целевой AI-контракт.** Полная структура с безопасными метаданными, локальными aliases, результатом ИИ и обратной подстановкой определена в [структурном контракте](../functional/04-structured-roundtrip-contract.md) и [JSON Schema](../contracts/structured-packet.schema.json). Для этого нужен отдельный API и security review, он в коде не включён.

## Локальный вызов
`ApprovedIssue`: `category` из ENUM [page_count_mismatch, page_overlap, missing_link, missing_review_status, invalid_date_order, reference_mismatch, missing_evidence, unverified_revision]; `severity` [info, review, high]; `metrics` map keys from [declared_count, calculated_count, conflict_count], integer 0..100000; запрещены поля `raw_text`, `source_name`, `filename`, `people`, `drawing_code`, `original_document`. До 10 находок.

Гейтвей генерирует короткий task prompt с ограниченным набором кодов и чисел. Оригинальные локальные ID не уходят, только индекс в рамках запроса. JSON-запрос по OpenAI-compatible `POST /v1/chat/completions` отправляется с bearer token, `stream=false`, `temperature=0`, `max_tokens` ограничен.

Пример **полностью синтетический**:
```json
{
  "model": "construction-analyzer",
  "messages": [
    {"role": "system", "content": "You help review abstract construction documentation consistency issues. Do not invent evidence or certify construction facts. Return JSON."},
    {"role": "user", "content": "{\"issues\":[{\"index\":1,\"category\":\"page_count_mismatch\",\"severity\":\"review\",\"metrics\":{\"declared_count\":3,\"calculated_count\":4}}]}"}
  ],
  "max_tokens": 400,
  "temperature": 0,
  "stream": false
}
```

## Ответ
```json
{"recommendations": [
  {"index": 1, "action": "check_source", "rationale": "Check the page range and declared number of sheets against the original document."}
]}
```
`index` должен ссылаться на конкретную переданную находку, `action` — ENUM [check_source, request_clarification, manual_review, no_action]. Ограничение длины текста; отсутствие заявлений «согласовано/измерено/подписано» от имени модели. Результат только для показа, не команда.

## Ошибки
- Connection error / 408 / 429 / 5xx → без изменений в локальной БД, показать retry с безопасным payload.
- 401/403 → disable AI, проверить credentials; секреты не печатать.
- Не-JSON, превышение лимитов, неожиданные поля, невалидный index → reject.
- Нет `GPUGO_INFERENCE_URL` или `GPUGO_INFERENCE_TOKEN` → offline-only.

## Нельзя называть этот API готовым серверным шлюзом
Реализация текущего репозитория — **Windows client-side policy gate и OpenAI-compatible adapter**. Production GPUGO edge с tenant auth, quota, prompt logging control, mTLS/VPN и обслуживанием токенов — отдельно в backlog.
