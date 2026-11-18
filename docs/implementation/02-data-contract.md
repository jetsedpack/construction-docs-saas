# Каноническая предметная модель

## Реализованный локальный граф PoC

Реализация: [construction_docs/graph.py](../../construction_docs/graph.py), [construction_docs/vault.py](../../construction_docs/vault.py) (зашифрованная сериализация графа). Это минимальный источник сущностей и доказательных ссылок. Постоянная PostgreSQL-схема и автоматическое связывание пока отсутствуют.

## Слой исходных доказательств
`SourceDocument` (id, type, cipher_sha256, supplied_filename_encrypted, import_time, format, extraction_status)
→ `SourceFragment` (document_id, page/sheet/cell, offset, text_hash, encrypted_text)
→ `Claim` (subject_id, predicate, value_encrypted, source_fragment_id, origin_type, version, status).

`Claim.origin_type`: project_assertion / contractor_report / measured_result / regulator_text / AI_suggestion. Утверждение может быть `proposed`, `requires_check`, `verified`, `rejected`. Наличие файла не превращает его в факт.

## Учётные сущности
`Project, WorkSection, Drawing, DrawingRevision, WorkItem, Equipment, EquipmentTag, Material, MaterialBatch, QualityDocument, Contractor, Authority, EstimatePosition, WorkEvent, Inspection, IDDocument, IDRegisterEntry, Acceptance, PNRProtocol, ConfigurationArtifact, Rule, NormativeEdition, Finding, Review, AuditEvent`.

Связи many-to-many через `WorkDocument, EquipmentDocument, MaterialUsage, DrawingWork, RuleApplicability`. Все экземпляры в одном проекте; исторические шифры РД и версии/изм. отдельно.

## Пример ЧГЭС без подлинных закрытых данных
- Рабочий раздел `<RD-CODE>-УА` → конструкция `<STRUCTURE-ID>` → операция бурения → АОСР → исполнительная схема.
- Электрошкаф `EQ-F10` → паспорт → монтаж → протокол ПНР → акт испытания → конфигурационный архив.
- Паспорт качества кабеля `Q-DOC-X` → партия → материал → позиция спецификации → кабельный журнал → работа.
- Изменение кабельной трассы `CHANGE-1` → `planned_length`, `measured_length`, `reason`, `approval_evidence` (может отсутствовать) → finding.

`DocumentFile` и `DocumentRecord` — не одно и то же. Один и тот же сертификат встречается в нескольких комплектах; нельзя создавать новый фактический сертификат при каждой копии файла.

## Не смешивать
- `EstimatePosition.planned_cost` с `ActKS2.accepted_cost` (КС-2 не равна АОСР).
- `DrawingRevision.projected_length` с `Measurement.actual_length`.
- `Certificate.valid_until` с `Certificate.issued_at`.
- `ModelSuggestion` с `ApprovedChange`.
- `Equipment.type` с `Equipment.serial` и `Equipment.tag`.
- `normative_edition.effective_from` с `downloaded_at` и `published_at`.

## Модель правил
`Rule = id, scope, version, normative_citation, source_url, effective_period, check_type, required_fields, error_class, tests`. Данные из разных лет проверяются по редакции с учётом объекта, договора, даты и правового статуса. Нельзя автоматически заменять нормы на «последние».

## Индексы и поиск в будущей БД
`(tenant_id, project_id, equipment_tag)`, `(tenant_id, project_id, drawing_cipher, revision)`, `(tenant_id, project_id, document_type, status)`, `(tenant_id, norm_id, effective_from)`; полнотекстовый индекс только в защищённом контуре; в PoC локальная SQLite хранит ciphertext, а поиск ограничен расшифрованными в процессе выборками.

## Путь от логического к физическому
Сначала реальная схема по данным ЧГЭС и ещё 2 объектам разных типов. Затем нормализованная PostgreSQL схема и миграции Alembic внутри периметра заказчика, не раньше проверки таксономии с инженером ПТО.
