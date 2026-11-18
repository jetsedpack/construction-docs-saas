# Construction Docs SaaS — Windows + GPUGO

**Рабочая концепция / инженерный PoC** автоматизации контроля и систематизации исполнительной документации (ИД). Основа: кейс ЧГЭС с реестрами ИД, РД, актами, ПНР, сертификатами и ведомостями изменений. **Не готовый SaaS и не юридически сертифицированная система.**

**Сейчас:** Windows-only PySide6 клиент, зашифрованное локальное хранилище, импорт PDF/DOCX/XLSX/CSV, проверка реестров, политика минимизации данных и два шлюза — клиентский и GPUGO edge. Remote AI включается только по решению пользователя. Мобильной, планшетной и веб-версий нет и в MVP не планируется.

## Функциональная архитектура (основная схема)

**[Девятистраничная блок-схема draw.io: A0 → F01…F07 → кейс ЧГЭС](diagrams/09-functional-architecture.drawio)** — редактируемые блоки с последовательностью работы, ветвлениями, отказами и различием между работающим PoC и будущими функциями. Это **главный документ**, а не mind map.

**[Посмотреть блок-схемы прямо на GitHub](docs/functional/flowcharts.md)** · **[Функциональный справочник](docs/functional/README.md)** · [Входы, операции, выходы и алгоритмы](docs/functional/01-functional-specification.md) · [Таблица функций и файлов кода](docs/functional/02-code-coverage.md).

## Вспомогательные схемы и концепции

| Карта / схема | Что показывает |
| --- | --- |
| [Подробная редактируемая draw.io: Windows → GPUGO + этапы](diagrams/08-windows-gpugo-implementation.drawio) | Общая инженерная карта с 4 GPU, кодом шлюза, хранилищем, разработкой |
| [Старая mind map (не основной документ)](diagrams/03-development-mindmap.md) | Концептуальные заметки; функциональная структура выше имеет приоритет |
| [Архитектура + последовательность запроса](docs/implementation/01-architecture.md) | Границы Windows/GPUGO, данные, AI и человек |
| [ER-модель + статусы документов](diagrams/04-domain-erd.md) | Реальные сущности связанной «коробки» |
| [Размещение 4×6000D / варианты TP/DP](diagrams/05-gpugo-deployment.md) | Edge, inference, GPU, тестирование |
| [Windows UX и пользовательский процесс](diagrams/06-windows-user-flows.md) | ПТО: импорт → проверки → AI → решение |
| [Модель угроз и границы данных](diagrams/07-threat-model.md) | Шифрование, allowlist, trusted/untrusted |
| [Редактируемая draw.io: потоки данных](diagrams/01-construction-data-flow.drawio) | Исходный визуальный чертёж |
| [Редактируемая draw.io: таблицы ИД](diagrams/02-id-record-model.drawio) | Пять связанных контуров учёта |

Mermaid-диаграммы отображаются прямо на GitHub; их текст легко меняет Codex. Для draw.io есть [diagrams.net](https://app.diagrams.net/).

## Документация разработки

- [Область MVP и ограничения](docs/implementation/00-scope.md)
- [Подробная архитектура](docs/implementation/01-architecture.md)
- [Каноническая предметная модель и контракты](docs/implementation/02-data-contract.md)
- [Windows-интерфейс и установка](docs/implementation/03-windows.md)
- [Безопасность, псевдонимизация и data flow](docs/implementation/04-security.md)
- [GPUgo inference: 4 RTX PRO 6000D](docs/implementation/05-gpugo-inference.md)
- [Кейс ЧГЭС и тестовые сценарии](docs/implementation/06-chges-test-plan.md)
- [Этапы, владельцы, риски, критический путь](docs/implementation/07-roadmap.md)
- [API-контракт шлюза](docs/implementation/08-api-contract.md)
- [Критерии приёмки и readiness](docs/implementation/09-acceptance-and-validation.md)
- [Прототип server-side GPUGO Edge](server/gpugo_edge/README.md)
- [Security policy](SECURITY.md)

Ранее подготовленные [общее описание предметной области](docs/architecture.md), [модель данных](docs/data-model.md) и [нормативные источники](docs/regulatory-sources.md) остаются в репозитории как материалы discovery.

## Быстрый запуск на Windows

**Требования:** Windows 11 x64, Python 3.12 и Git. Убедитесь, что в систему не помещаются реальные секреты и файлы заказчика до security review.

```powershell
git clone https://github.com/jetsedpack/construction-docs-saas.git
cd construction-docs-saas
git checkout feat/windows-saas-architecture-mvp
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[desktop,dev]"
python -m construction_docs.desktop
```

**CLI** (локально, без сети): `construction-docs import .\example.xlsx`, `construction-docs list`, `construction-docs check <document-id>`.

**Tests** (включая серверные): `python -m pip install -e ".[server,dev]"` → `python -m pytest -q`. CI проверяет Windows и Linux Python, GUI smoke — на Windows.

**GPUGO**: для включения AI-подсказок задать `GPUGO_INFERENCE_URL` (только HTTPS, путь `/v1/chat/completions`), `GPUGO_ALLOWED_HOSTS`, `GPUGO_INFERENCE_TOKEN` и `GPUGO_MODEL`. **Не указывать реальные токены в Git.** Пока endpoint не предоставлен и не прошёл проверку на стороне GPUGO, приложение работает полностью офлайн по поддержанным локальным функциям.

**Server demo:** `server/gpugo_edge/app.py` предназначен для закрытого loopback стенда с локальным vLLM. **Не публиковать публично без промышленной аутентификации и hardening.**

## Реализация связей и нормативов

- [construction_docs/graph.py](construction_docs/graph.py) — первый рабочий граф сущностей и доказательных связей; локальное шифрованное сохранение графа.
- [construction_docs/norms.py](construction_docs/norms.py) — ручной версионируемый каталог НПА/НТД с проверкой даты действия (автообновление ещё не реализовано).
- [packaging/build_windows.ps1](packaging/build_windows.ps1) — попытка сборки unsigned developer .exe на Windows, **не production installer**.
- [GitHub Issues](https://github.com/jetsedpack/construction-docs-saas/issues) — девять детальных задач от discovery до защищённого командного режима, пригодных для работы с Codex по отдельности.

## Безопасность
Сырые документы, все извлечённые сведения, файлы РД, планы, паспорта и конфигурации оборудования остаются в Windows-контуре. DPAPI защищает Fernet-ключ; файл оригинала и запись БД шифруются, но это **не SQLCipher для всего SQLite**, не защита от скомпрометированного Windows-аккаунта и не готовая enterprise-security. По сети отправляются только категории замечаний, важность и числовые счётчики после ручного подтверждения. Ни модель, ни её ответ не могут изменять исходный документ или удостоверять выполнение работ.

**Исходники ЧГЭС в репозиторий не копировались.** В коде и тестах только синтетические документы и обозначения. Перед использованием с реальным заказчиком нужен договор обработки данных, полноценная модель угроз, проверка инфраструктуры и экспертное подтверждение нормативных правил.

## Что уже работает в коде, а что пока только план
| Подсистема | Статус |
| --- | --- |
| Импорт supported PDF/DOCX/XLSX/CSV | Код PoC, требуется проверка на Windows |
| Оригиналы и метаданные в локальном DPAPI+Fernet vault | Код PoC, не аудирован |
| Проверка страниц/полей реестра | Код PoC + unit-тесты |
| Desktop UI PySide6 / ручное решение ПТО | Код PoC, UX не завершён |
| Client allowlist gateway / server GPUGO Edge | Код PoC, без production auth |
| Модель на 4×6000D / real token throughput | План benchmark, не развёрнуто |
| Автоматизированный нормоконтроль, полная связанная база, ЭП, OCR/DWG | Спроектировано/в backlog |
| Подписанный .exe/MSI, enterprise team workflow | Не реализовано |

## Принцип
**Правило + доказательство + человек, а не «ИИ заменяет инспектора».** Реестр отделяет проектные утверждения, подтверждённые факты и AI-гипотезы, хранит версии нормативов и происхождение данных. На первой стадии ограничиваемся проверяемыми узкими сценариями, а не «всеми ГОСТ и всей стройкой».

