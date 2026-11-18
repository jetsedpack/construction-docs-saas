"""Local encrypted vault. PoC: per-user DPAPI wrapping a Fernet data key.

No network connections, no plaintext document copies, no server DB.
DO NOT mistake this for an audited multi-user enterprise secure store.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet

from .ingest import MAX_FILE_BYTES, extract
from .models import ImportedDocument, Issue


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_root() -> Path:
    if sys.platform != "win32":
        raise RuntimeError("Релиз ориентирован на Windows; тесты используют изолированный test_key")
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("Не найден LOCALAPPDATA")
    return Path(local) / "ConstructionDocsPoC"


def _dpapi_fernet_key(root: Path) -> bytes:
    if sys.platform != "win32":
        raise RuntimeError("DPAPI доступен только в Windows. На POSIX — только тестовый ключ")
    import win32crypt

    f = root / "master.dpapi"
    if f.exists():
        key = win32crypt.CryptUnprotectData(f.read_bytes(), None, None, None, 0)[1]
        Fernet(key)  # validate key before use
        return key
    key = Fernet.generate_key()
    sealed = win32crypt.CryptProtectData(key, "ConstructionDocsPoC", None, None, None, 0)
    # O_EXCL prevents a second process from silently replacing a key.
    with f.open("xb") as handle:
        handle.write(sealed)
    return key


class EncryptedVault:
    def __init__(self, root: str | Path | None = None, *, test_key: bytes | None = None):
        self.root = Path(root) if root is not None else _default_root()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "blobs").mkdir(exist_ok=True)
        self.crypto = Fernet(test_key if test_key is not None else _dpapi_fernet_key(self.root))
        self.db = sqlite3.connect(self.root / "vault.sqlite3")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, payload BLOB NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS findings (document_id TEXT PRIMARY KEY, payload BLOB NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS audit (event_id TEXT PRIMARY KEY, payload BLOB NOT NULL)")
        self.db.commit()

    def _seal(self, data: dict | list) -> bytes:
        return self.crypto.encrypt(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _open(self, payload: bytes):
        return json.loads(self.crypto.decrypt(payload).decode("utf-8"))

    def audit(self, event_type: str, data: dict) -> None:
        event = {"time": _now(), "type": event_type, "data": data}
        self.db.execute(
            "INSERT INTO audit (event_id, payload) VALUES (?, ?)",
            (uuid.uuid4().hex, self._seal(event)),
        )
        self.db.commit()

    def import_file(self, path: str | Path) -> ImportedDocument:
        source = Path(path)
        if not source.is_file():
            raise ValueError("Файл не найден")
        if source.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("Файл слишком большой для PoC")
        content = source.read_bytes()
        result = extract(source.name, content)  # local-only, never network
        ident = uuid.uuid4().hex
        doc = ImportedDocument(
            id=ident,
            name=source.name,
            kind=source.suffix.lower(),
            imported_at=_now(),
            text=result.text,
            tables=result.tables,
            warnings=result.warnings,
            size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )
        target = self.root / "blobs" / f"{ident}.enc"
        with target.open("xb") as handle:
            handle.write(self.crypto.encrypt(content))
        try:
            with self.db:
                self.db.execute(
                    "INSERT INTO documents (id, payload) VALUES (?, ?)",
                    (ident, self._seal(doc.local_json())),
                )
        except Exception:
            target.unlink(missing_ok=True)
            raise
        self.audit("document_imported", {"document_id": ident, "status": "ok"})
        return doc

    def get_document(self, ident: str) -> ImportedDocument:
        row = self.db.execute("SELECT payload FROM documents WHERE id=?", (ident,)).fetchone()
        if row is None:
            raise KeyError("Неизвестный документ")
        return ImportedDocument(**self._open(row[0]))

    def list_documents(self) -> list[ImportedDocument]:
        rows = self.db.execute("SELECT payload FROM documents").fetchall()
        return sorted(
            (ImportedDocument(**self._open(row[0])) for row in rows),
            key=lambda doc: doc.imported_at,
            reverse=True,
        )

    def original_bytes(self, ident: str) -> bytes:
        self.get_document(ident)  # validate identifier exists in DB
        # Only immutable, internally generated UUIDs can be used as blob names.
        if len(ident) != 32 or any(c not in "0123456789abcdef" for c in ident):
            raise ValueError("Недопустимый идентификатор")
        return self.crypto.decrypt((self.root / "blobs" / f"{ident}.enc").read_bytes())

    def save_findings(self, document_id: str, issues: list[Issue]) -> None:
        self.get_document(document_id)
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO findings (document_id, payload) VALUES (?, ?)",
                (document_id, self._seal([issue.local_json() for issue in issues])),
            )
        self.audit("local_check", {"document_id": document_id, "count": len(issues)})

    def get_findings(self, document_id: str) -> list[Issue]:
        row = self.db.execute("SELECT payload FROM findings WHERE document_id=?", (document_id,)).fetchone()
        if not row:
            return []
        return [Issue(**item) for item in self._open(row[0])]

    def events(self) -> list[dict]:
        rows = self.db.execute("SELECT payload FROM audit ORDER BY rowid").fetchall()
        return [self._open(row[0]) for row in rows]

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "EncryptedVault":
        return self

    def __exit__(self, *_exc):
        self.close()
