"""Versioned normative catalog, manually curated in the protected customer perimeter.

The updater for official publications and license-aware legal sources is NOT
implemented. This registry only models applicability and preserves history.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class NormativeEdition:
    code: str
    revision: str
    kind: str  # NPA, NTDoc, approved_working_document
    published_at: date
    effective_from: date
    effective_until: date | None
    jurisdiction: str  # e.g. RU or RU-REGION-CODE
    scope: frozenset[str]
    source_url: str
    reviewed_by: str  # local protected identity or role
    reviewed_at: date

    def applicable(self, on: date, jurisdiction: str, scope: str) -> bool:
        return (
            (self.jurisdiction == "RU" or self.jurisdiction == jurisdiction)
            and scope in self.scope
            and self.effective_from <= on
            and (self.effective_until is None or on <= self.effective_until)
        )


class NormativeCatalog:
    def __init__(self):
        self.editions: dict[tuple[str, str], NormativeEdition] = {}

    def register(self, edition: NormativeEdition) -> None:
        key = (edition.code, edition.revision)
        if key in self.editions:
            raise ValueError("Редакция уже зарегистрирована — нельзя менять историю")
        if edition.effective_until is not None and edition.effective_until < edition.effective_from:
            raise ValueError("Неверный период действия")
        if not edition.source_url.startswith("https://") or not edition.reviewed_by:
            raise ValueError("Нет проверенного источника или экспертного подтверждения")
        self.editions[key] = edition

    def applicable(self, code: str, on: date, region: str, scope: str) -> list[NormativeEdition]:
        return sorted(
            (e for e in self.editions.values()
             if e.code == code and e.applicable(on, region, scope)),
            key=lambda x: (x.effective_from, x.revision),
            reverse=True,
        )
