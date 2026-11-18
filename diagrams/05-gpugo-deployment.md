# Развёртывание и расклад GPU

```mermaid
flowchart LR
  subgraph C["Периметр заказчика — Windows"]
    D["Desktop UI"] --> V["DPAPI vault"]
    V --> R["Rule Engine / human review"]
    R --> L["Outbound allowlist + local approval"]
  end
  subgraph NET["Сеть / HTTPS"]
    P["DDoS/WAF/Ingress (будущее)"]
  end
  subgraph G["GPUGO · выделенный AI inference pool"]
    EDGE["Authn/authz + tenant limits / no prompt log"]
    Q["Request queue / validation"]
    LB["Scheduler + health"]
    subgraph GPU["4× RTX PRO 6000D · 4×84GB VRAM"]
      GPU1["GPU0"]
      GPU2["GPU1"]
      GPU3["GPU2"]
      GPU4["GPU3"]
    end
    VLLM["vLLM: 4xDP / 2xTP2 / 1xTP4; after benchmark"]
    EDGE --> Q --> LB --> VLLM
    VLLM --- GPU1
    VLLM --- GPU2
    VLLM --- GPU3
    VLLM --- GPU4
  end
  L --> P --> EDGE
  EDGE --> |"validated response"| L
```

## Четыре варианта планирования
```mermaid
flowchart TD
   MODEL["Подтверждённые веса, контекст, квантование"] --> F{"1 карта 84GB вместе с KV?"}
   F -- "Да" --> DP4["4x DP1: четыре независимых экземпляра"]
   F -- "Нет" --> F2{"2×84GB + KV, TP=2 работает?"}
   F2 -- "Да" --> TP2["2 сервера модели, по 2 GPU"]
   F2 -- "Нет" --> TP4["1 сервер модели, TP=4"]
   DP4 --> TEST["Сравнить throughput, TTFT, p95, VRAM, quality"]
   TP2 --> TEST
   TP4 --> TEST
   TEST --> DEC{"SLO+качество+стоимость?"}
   DEC -- "Нет" --> MODEL
   DEC -- "Да" --> PROD["Закрепить version + rollout + alerting"]
```

Ограничения: не поднимать порт vLLM в публичную сеть, не хранить запросы и клиентские документы на inference-ноде, проверять лицензии и устройство PCIe. В публичный GPT API нельзя передавать оригинальные документы. Точные числа TPS не заявлены до тестов.
