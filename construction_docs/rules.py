"""Deterministic register checks based on the *shape* of construction ID Excel registers.

They detect candidates for human review, NOT legally established violations.
"""
from __future__ import annotations

import re

from .models import ImportedDocument, Issue

_SPAN = re.compile(r"^\s*(\d+)\s*[-–—]\s*(\d+)\s*$")


def _match_col(row: list[str], needle: str) -> int | None:
    return next((idx for idx, v in enumerate(row) if needle in str(v).lower()), None)


def _cell(row: list, idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    return str(row[idx]).strip()


def _page_interval(raw: str) -> tuple[int, int] | None:
    raw = raw.strip()
    if raw.isdigit():
        n = int(raw)
        return (n, n) if n > 0 else None
    m = _SPAN.fullmatch(raw)
    if m and int(m[1]) > 0 and int(m[2]) >= int(m[1]):
        return int(m[1]), int(m[2])
    return None


def check_register(doc: ImportedDocument) -> list[Issue]:
    issues: list[Issue] = []
    for sheet in doc.tables:
        rows = sheet.get("rows", [])
        header_index = None
        for i, row in enumerate(rows[:80]):
            if _match_col(row, "количество листов") is not None and _match_col(row, "наименование документа") is not None:
                header_index = i
                break
        if header_index is None:
            continue  # not a construction ID register; cannot assume meaning
        header = rows[header_index]
        c_number = _match_col(header, "№ п/п")
        c_name = _match_col(header, "наименование документа")
        c_sheets = _match_col(header, "количество листов")
        c_pages = _match_col(header, "страницы по списку")
        c_path = _match_col(header, "путь где лежит")
        c_review = _match_col(header, "дата направления на проверку")
        if c_number is None or c_name is None:
            continue

        used_pages: set[int] = set()
        for excel_row_idx in range(header_index + 1, len(rows)):
            row = rows[excel_row_idx]
            number = _cell(row, c_number)
            name = _cell(row, c_name)
            if not number.isdigit() or len(name) < 5 or name.isdigit():
                continue
            at = excel_row_idx + 1
            span = _page_interval(_cell(row, c_pages))
            declared_raw = _cell(row, c_sheets)
            declared = int(declared_raw) if declared_raw.isdigit() else None

            if span is not None:
                start, end = span
                calculated = end - start + 1
                if declared is not None and declared != calculated:
                    issues.append(Issue(
                        "page_count_mismatch", "review",
                        f"Лист {sheet.get('sheet')}, строка {at}: записано {declared} листов, диапазон {start}–{end} содержит {calculated}.",
                        at, doc.id,
                        {"declared_count": declared, "calculated_count": calculated},
                    ))
                # Bound a potential malformed range.
                if end - start < 10_000:
                    overlapping = sum(page in used_pages for page in range(start, end + 1))
                    if overlapping:
                        issues.append(Issue(
                            "page_overlap", "review",
                            f"Лист {sheet.get('sheet')}, строка {at}: диапазон страниц пересекается с предыдущими ({overlapping} стр.).",
                            at, doc.id, {"conflict_count": overlapping},
                        ))
                    used_pages.update(range(start, end + 1))

            if c_path is not None and not _cell(row, c_path):
                issues.append(Issue(
                    "missing_link", "info",
                    f"Лист {sheet.get('sheet')}, строка {at}: в реестре не заполнен путь к файлу (возможно, есть внешняя система).",
                    at, doc.id,
                ))
            if c_review is not None and not _cell(row, c_review):
                issues.append(Issue(
                    "missing_review_status", "info",
                    f"Лист {sheet.get('sheet')}, строка {at}: не заполнена графа направления на проверку.",
                    at, doc.id,
                ))
    return issues
