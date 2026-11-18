"""Extract text/tables inside the trusted Windows process; no outbound calls."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path

MAX_FILE_BYTES = 12 * 1024 * 1024
MAX_TEXT_CHARS = 250_000
MAX_PDF_PAGES = 150
MAX_ROWS = 4_000
MAX_COLS = 80
MAX_SHEETS = 20

SUPPORTED = {".pdf", ".docx", ".xlsx", ".csv"}


@dataclass
class Extraction:
    text: str
    tables: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _crop(s: str, warnings: list[str]) -> str:
    if len(s) > MAX_TEXT_CHARS:
        warnings.append("Текст обрезан по лимиту безопасности; нужен пакетный импорт.")
        return s[:MAX_TEXT_CHARS]
    return s


def extract(filename: str, content: bytes) -> Extraction:
    ext = Path(filename).suffix.lower()
    if len(content) > MAX_FILE_BYTES:
        raise ValueError("Файл превышает лимит PoC (12 MiB)")
    if not content:
        raise ValueError("Пустой файл")
    if ext not in SUPPORTED:
        raise ValueError(f"Формат {ext or 'без расширения'} пока не поддержан; DOC/XLS/DWG/RAR/OCR — в backlog")
    warnings: list[str] = []

    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content), strict=False)
        if reader.is_encrypted:
            raise ValueError("Зашифрованный PDF: нужен штатный доступ и отдельная процедура")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ValueError("Слишком много страниц для одного импорта PoC")
        parts = []
        for i, page in enumerate(reader.pages, start=1):
            parts.append(f"[page:{i}]\n" + (page.extract_text() or ""))
        text = "\n".join(parts)
        if not text.strip() or len(text.strip()) < 30:
            warnings.append("В PDF почти нет извлекаемого текста: вероятно, скан; нужен локальный OCR")
        return Extraction(_crop(text, warnings), warnings=warnings)

    if ext == ".docx":
        from docx import Document
        doc = Document(io.BytesIO(content))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.append("\t".join(cell.text for cell in row.cells))
        return Extraction(_crop("\n".join(parts), warnings), warnings=warnings)

    if ext == ".xlsx":
        from openpyxl import load_workbook
        book = load_workbook(io.BytesIO(content), read_only=True, data_only=True, keep_links=False)
        try:
            if len(book.worksheets) > MAX_SHEETS:
                raise ValueError("Слишком много листов Excel для PoC")
            tables, lines = [], []
            for ws in book.worksheets:
                if ws.max_row and ws.max_row > MAX_ROWS:
                    raise ValueError(f"Лист {ws.title}: слишком много строк для PoC")
                if ws.max_column and ws.max_column > MAX_COLS:
                    raise ValueError(f"Лист {ws.title}: слишком много столбцов для PoC")
                rows = []
                for row in ws.iter_rows(values_only=True):
                    rows.append([str(x).strip() if x is not None else "" for x in row])
                tables.append({"sheet": ws.title, "rows": rows})
                lines.append(f"[sheet:{ws.title}]\n" + "\n".join("\t".join(r) for r in rows))
            return Extraction(_crop("\n".join(lines), warnings), tables=tables, warnings=warnings)
        finally:
            book.close()

    # CSV; retain rows for the same rule engine as Excel.
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("cp1251")
        warnings.append("CSV декодирован как cp1251; проверьте символы")
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) > MAX_ROWS or any(len(r) > MAX_COLS for r in rows):
        raise ValueError("CSV превышает лимиты PoC")
    return Extraction(_crop(text, warnings), tables=[{"sheet": "CSV", "rows": rows}], warnings=warnings)
