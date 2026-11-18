"""Typed local findings and document records.

Private fields live in the encrypted local vault; the gateway exports only
a strict subset of Issue fields.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

Category = Literal[
    "page_count_mismatch",
    "page_overlap",
    "missing_link",
    "missing_review_status",
    "invalid_date_order",
    "reference_mismatch",
    "missing_evidence",
    "unverified_revision",
]
Severity = Literal["info", "review", "high"]


@dataclass(frozen=True)
class Issue:
    category: Category
    severity: Severity
    message: str  # private: NEVER exported to inference
    source_row: int = 0  # private: NEVER exported
    document_id: str = ""  # private: NEVER exported
    metrics: dict[str, int] = field(default_factory=dict)

    def local_json(self) -> dict:
        return asdict(self)


@dataclass
class ImportedDocument:
    id: str
    name: str  # PRIVATE: encrypted locally
    kind: str
    imported_at: str
    text: str  # PRIVATE: encrypted locally
    tables: list[dict]
    warnings: list[str]
    size: int
    sha256: str
    doc_type: str = ""  # selected locally by the engineer; never an export permission
    parse_status: str = "parsed"  # staged / needs_classification / parsed / blocked / needs_attention

    def local_json(self) -> dict:
        return asdict(self)
