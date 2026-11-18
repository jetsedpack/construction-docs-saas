from __future__ import annotations

from cryptography.fernet import Fernet

from construction_docs.batch import discover_files
from construction_docs.document_types import DOCUMENT_TYPES, require_type
from construction_docs.vault import EncryptedVault


def test_batch_discovery_keeps_tree_and_unsupported(tmp_path):
    root = tmp_path / "project"
    (root / "RD").mkdir(parents=True)
    (root / "PNR").mkdir()
    (root / "RD" / "drawing.dwg").write_bytes(b"dummy-dwg")
    (root / "RD" / "register.csv").write_text("field,value\nunit,3", encoding="utf-8")
    (root / "PNR" / "act.docx").write_bytes(b"not-yet-parsed")
    rows = discover_files(root)
    assert len(rows) == 3
    assert {r.relative_path for r in rows} == {
        "RD/drawing.dwg", "RD/register.csv", "PNR/act.docx"
    }
    assert next(r for r in rows if r.path.suffix == ".dwg").supported_parser is False


def test_types_have_unique_ids_and_require_explicit_selection():
    assert len(DOCUMENT_TYPES) >= 15
    assert len({entry.code for entry in DOCUMENT_TYPES}) == len(DOCUMENT_TYPES)
    assert require_type("working_drawing").label == "Рабочий чертёж"
    import pytest
    with pytest.raises(ValueError):
        require_type("")
    with pytest.raises(ValueError):
        require_type("other")
    with pytest.raises(ValueError):
        require_type("unexpected_type")


def test_staged_document_is_not_parsed_until_type_selected(tmp_path):
    source = tmp_path / "synthetic.csv"
    source.write_text("field,value\nlength,33", encoding="utf-8")
    with EncryptedVault(tmp_path / "vault", test_key=Fernet.generate_key()) as vault:
        staged = vault.stage_file(source)
        assert staged.parse_status == "needs_classification"
        assert staged.doc_type == ""
        assert staged.text == ""
        assert vault.original_bytes(staged.id) == source.read_bytes()
        parsed = vault.classify_document(staged.id, "id_register")
        assert parsed.parse_status == "parsed"
        assert parsed.doc_type == "id_register"
        assert "length" in parsed.text
        assert vault.original_bytes(staged.id) == source.read_bytes()


def test_unsupported_file_is_encrypted_and_blocked(tmp_path):
    source = tmp_path / "circuit.dwg"
    source.write_bytes(b"synthetic-dwg")
    with EncryptedVault(tmp_path / "vault", test_key=Fernet.generate_key()) as vault:
        staged = vault.stage_file(source)
        assert staged.parse_status == "needs_classification"
        blocked = vault.classify_document(staged.id, "working_drawing")
        assert blocked.parse_status == "blocked"
        assert vault.original_bytes(staged.id) == source.read_bytes()
        assert all(event["type"] != "document_exported" for event in vault.events())
