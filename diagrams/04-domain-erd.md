# Предметная ER-модель: объекты, акты, ПНР, доказательства

```mermaid
erDiagram
   PROJECT ||--o{ WORK_SECTION : contains
   WORK_SECTION ||--o{ WORK_ITEM : plans
   DRAWING ||--o{ DRAWING_REVISION : versions
   DRAWING_REVISION }o--o{ WORK_ITEM : specifies
   ESTIMATE_LINE }o--o{ WORK_ITEM : prices
   WORK_ITEM ||--o{ WORK_EVENT : has
   WORK_ITEM }o--o{ EQUIPMENT : installs
   EQUIPMENT ||--o{ EQUIPMENT_DOCUMENT : linked_to
   EQUIPMENT_DOCUMENT }o--|| DOCUMENT : references
   WORK_ITEM }o--o{ MATERIAL_BATCH : uses
   MATERIAL_BATCH ||--o{ QUALITY_DOCUMENT : verified_by
   WORK_ITEM ||--o{ ID_DOCUMENT : evidenced_by
   ID_DOCUMENT ||--o{ ID_REGISTER_ENTRY : catalogued_by
   DOCUMENT ||--o{ SOURCE_FRAGMENT : split_into
   SOURCE_FRAGMENT ||--o{ CLAIM : asserted_by
   CLAIM ||--o{ FINDING : checked_by
   RULE ||--o{ FINDING : detects
   NORM_EDITION ||--o{ RULE : supports
   FINDING ||--o{ REVIEW : decided_by
   EQUIPMENT ||--o{ PNR_PROTOCOL : tested_by
   PNR_PROTOCOL }o--o{ CONFIG_ARTIFACT : refers_to
   ID_DOCUMENT ||--o{ DOCUMENT : represented_as
```

## Статусы объекта учёта
```mermaid
stateDiagram-v2
 [*] --> Imported
 Imported --> Parsed
 Imported --> ManualExtraction: scan/legacy file
 Parsed --> NeedsReview: inconsistent/missing
 Parsed --> Verified: no blocking findings
 NeedsReview --> Verified: expert accepted
 NeedsReview --> Rejected: invalid source
 Verified --> Packaged: register + evidence
 Packaged --> Archived
 Verified --> NeedsReview: revised RD/norm
 Rejected --> ManualExtraction
```

**Примечание:** статус `Verified` подтверждает только пройденную процедуру проверки внутри продукта. Юридическая подпись и приёмка выполненных работ — отдельные действия уполномоченных лиц.
