# Привязка функциональных блоков к конкретному коду

**Важно:** это карта покрытия, а не список полностью реализованных возможностей. По запросу «как реализуется функция» открывайте в первую очередь этот файл и [блок-схемы](../../diagrams/09-functional-architecture.drawio).

| ID | Подфункция | Код сейчас | Текущий статус | Что писать следующим |
| --- | --- | --- | --- | --- |
| F00.1 | Контекст проекта и права | `construction_docs/desktop.py`, `vault.py` | Частично: один Windows-пользователь | ProjectContext, project_id, scopes, RBAC для командного этапа |
| F01.1 | Выбор и загрузка файла | `desktop.py::import_document`, `vault.py::import_file` | Есть в PoC | пакетный импорт, каталог проекта, контроль MIME |
| F01.2 | PDF/DOCX/XLSX/CSV | `ingest.py::extract` | Есть в PoC, ограничения | SourceFragment с page/sheet/cell, диагностика OCR |
| F01.3 | Шифрование оригинала | `vault.py::EncryptedVault` | Есть в PoC DPAPI+Fernet | восстановление ключей, TTL/retention, real threat review |
| F02.1 | Структурированные Claim | `models.py::ImportedDocument` | Нет — только текст/таблицы | новые DTO, provenance, parse templates |
| F02.2 | Сущности и связи | `graph.py::EntityGraph`, `vault.py::save_graph` | Есть primitives, ручной граф | automatic matching, collision/ambiguity queue |
| F02.3 | Версии РД и документов | `graph.py::Node.state` | Нет полноценного revision workflow | immutable revisions, hashing, link history |
| F03.1 | Проверка страниц | `rules.py::check_register` | Есть в PoC | динамический header mapping, severity policy |
| F03.2 | Проверка наличия пути и статуса | `rules.py::check_register` | Есть в PoC | авто-связь с vault, учитывать внешние хранилища |
| F03.3 | Сверка РД/смета/факт/сертификат | — | Нет | join по Project/WorkItem/Equipment/MaterialBatch |
| F03.4 | Нормативные правила | `norms.py::NormativeCatalog` | Только ручной учёт редакций | rule evaluator, применимость, экспертные подтверждения |
| F04.1 | Минимизация outbound | `gateway.py::safe_batch` | Есть в PoC, строго enum+integer | угрозы косвенной идентификации, versioned policy |
| F04.2 | Предпросмотр и согласие ПТО | `desktop.py::ask_ai` | Есть в PoC | granular project policy, revoke, idempotency |
| F04.3 | GPUGO серверный шлюз | `server/gpugo_edge/app.py` | Есть demo, не production | OAuth/OIDC, quota, anti-replay, WAF, metrics |
| F04.4 | Сама модель / GPU | — | Не развернуто в репозитории | vLLM validation 4×6000D, benchmark |
| F05.1 | Найти и показать замечания | `desktop.py::display_issues` | Есть в PoC | evidence side-by-side, сортировки, issue grouping |
| F05.2 | Решение человека | `desktop.py::review_selected` | Простая запись audit | workflow, role checks, change/version approval |
| F06.1 | Состав и шаблоны ИД | — | Нет | формализовать перечень конкретного объекта |
| F06.2 | Генерация документов/реестра | — | Нет | DOCX/XLSX templating + preview + hash manifest |
| F06.3 | Электронная подпись | — | Нет | отдельное юридическое/техническое проектирование |
| F07.1 | Реестр редакций норм | `norms.py` | Есть локально, вручную | тесты применимости на реальные даты |
| F07.2 | Подписка на правовые источники | — | Нет | source adapters + лицензии + нормоконтроль |
| X01.1 | Локальная история | `vault.py::audit` | Есть в PoC | tamper evidence, external event collector для enterprise |
| X01.2 | Windows packaging | `packaging/build_windows.ps1` | Скрипт эксперимента | подпись, installer, updater, backup |
| X01.3 | Отказ сети и формата | `gateway.py`, `ingest.py` | Частично | очередь, retry, error taxonomy, negative QA |

## Важное несоответствие «полноценного AI анализа» и текущего safe-payload

Когда GPUgo получает `page_count_mismatch + declared_count=3 + calculated_count=4`, он **ничего не знает** о чертеже, материале, смете или самом документе. Следовательно, нельзя назвать текущий AI функциональным сверяющим движком. Утверждённая первая версия использует **локальные алгоритмы** для проверки, а inference помогает объяснять типы замечаний.

Чтобы AI сравнивал **действительные**, но обезличенные значения из РД и актов:
1. согласовать цели обработки и риск по инженерной информации, которая может идентифицировать объект;
2. определить whitelist технических полей для каждой задачи (например, две длины и единица измерения; не «произвольный текст»);
3. провести red-team на возможность восстановить объект, поставщика, конфигурации РЗА;
4. настроить доверенный gateway policy на клиенте и сервере;
5. сравнить качество с детерминированным правилом; передавать в модель только случаи, где AI действительно добавляет ценность;
6. сохранить source/target соответствие только локально и повторно проверить response человеком.

Разрешить **передачу полных рабочих чертежей на GPUgo** — это совершенно другое решение, в текущую архитектуру не включённое.

## Приоритет следующих работ

1. Создать на основе кейса ЧГЭС обезличенный набор независимых актов и реестров с gold-разметкой.
2. Дописать F02: SourceFragment/Claim и человеко-проверяемый entity resolution.
3. Дописать F03: таблицы соответствия и реальные cross-document rules.
4. Реализовать evidence viewer и F05 decision workflow.
5. Приступить к F06: одна форма и один реестр ИД, без имитации подписи.
6. Отдельно производственно завершить F04 / GPUgo Edge / 4×6000D и F07.
