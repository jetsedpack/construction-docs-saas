from cryptography.fernet import Fernet
from construction_docs.vault import EncryptedVault

def test_encrypted_blob_and_metadata_roundtrip(tmp_path):
    payload = "№ п/п,Наименование документа, номер документа\n1,СИНТЕТИЧЕСКИЙ АКТ".encode("utf-8")
    source = tmp_path / "synthetic.csv"
    source.write_bytes(payload)
    with EncryptedVault(tmp_path / "vault", test_key=Fernet.generate_key()) as vault:
        doc = vault.import_file(source)
        assert vault.get_document(doc.id).text.startswith("№")
        assert vault.original_bytes(doc.id) == payload
        assert len(vault.list_documents()) == 1
        assert vault.events()[0]["type"] == "document_imported"
    stored = (tmp_path / "vault" / "vault.sqlite3").read_bytes()
    cipher = (tmp_path / "vault" / "blobs" / f"{doc.id}.enc").read_bytes()
    assert b"synthetic.csv" not in stored
    assert payload not in stored
    assert payload not in cipher

def test_corrupt_ciphertext_fails_closed(tmp_path):
    import pytest
    from cryptography.fernet import InvalidToken
    key = Fernet.generate_key()
    path = tmp_path / "vault"
    source = tmp_path / "fake.csv"
    source.write_text("col1,col2\na,b", encoding="utf-8")
    with EncryptedVault(path, test_key=key) as vault:
        ident = vault.import_file(source).id
        (path / "blobs" / f"{ident}.enc").write_bytes(b"broken")
        with pytest.raises(InvalidToken):
            vault.original_bytes(ident)
