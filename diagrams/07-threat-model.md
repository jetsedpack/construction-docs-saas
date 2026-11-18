# Data safety, доверие и угрозы

```mermaid
flowchart LR
  subgraph SEC["Защищённая зона Windows"]
    P["Подлинные документы"]
    E["Извлечённые утверждения"]
    J["Инженер ПТО"]
    VAULT[("Ciphertext vault + DPAPI")]
    SAFE["Allowlist, null-drop, schema check"]
    P --> E --> VAULT
    VAULT --> J
    J --> SAFE
  end
  subgraph OUT["Внешняя граница"]
    HTTPS["TLS + token"]
    EDGE["GPUGO Edge: auth, limits, audit metadata"]
    INF["Inference: no storage, no file access"]
  end
  SAFE --> |"enum issue + numeric metrics"| HTTPS --> EDGE --> INF
  INF --> |"untrusted recommendation"| EDGE --> SAFE
  SAFE -. "результат на ручную проверку" .-> J
```

**Threats**: prompt injection, metadata leakage, re-identification, insecure model logging, compromised Windows profile, outdated norm edition, malicious malformed ZIP/DOCX, tool-output spoofing, model hallucinations, unauthorized registry writes. Сведения по каждому риску — [security](../docs/implementation/04-security.md).
