import io
import pytest
from openpyxl import Workbook
from construction_docs.ingest import extract
from construction_docs.models import ImportedDocument
from construction_docs.rules import check_register

def sample_register_bytes():
    wb = Workbook()
    ws = wb.active
    ws.title = "Реестр"
    ws.append(["РЕЕСТР исполнительной документации"])
    ws.append(["№ п/п", "Наименование документа, номер документа", "Количество листов",
               "Страницы по списку", "Путь где лежит документ", "Дата направления на проверку"])
    ws.append([1, "Синтетический паспорт конструкции", 1, "4", None, None])
    ws.append([2, "Синтетический сертификат материала", 3, "4-7", None, None])
    buff = io.BytesIO()
    wb.save(buff)
    return buff.getvalue()

def test_extract_synthetic_xlsx_and_find_conflicts():
    parsed = extract("fake.xlsx", sample_register_bytes())
    doc = ImportedDocument("doc-1", "fake.xlsx", ".xlsx", "", parsed.text,
                           parsed.tables, parsed.warnings, 100, "aabb")
    issues = check_register(doc)
    assert {"page_count_mismatch", "page_overlap", "missing_link",
            "missing_review_status"}.issubset({issue.category for issue in issues})
    assert all(issue.severity != "high" for issue in issues)

def test_unknown_binary_extension_is_rejected():
    with pytest.raises(ValueError, match="не поддержан"):
        extract("cabinet.rar", b"123")

def test_empty_file_is_rejected():
    with pytest.raises(ValueError, match="Пустой"):
        extract("fake.csv", b"")
