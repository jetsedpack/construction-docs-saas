"""Local-only batch discovery; no parsing, exports, uploads or network access.

The discovered paths and original filenames remain private inside Windows.
All files are enumerated, including currently unsupported formats.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .ingest import SUPPORTED

MAX_BATCH_FILES = 500
MAX_BATCH_BYTES = 512 * 1024 * 1024
IGNORED_DIRS = {".git", ".venv", "__pycache__", "node_modules"}


@dataclass(frozen=True)
class BatchCandidate:
    path: Path
    relative_path: str
    size: int
    supported_parser: bool


def discover_files(root: str | Path) -> list[BatchCandidate]:
    base = Path(root)
    if not base.is_dir() or base.is_symlink():
        raise ValueError("Выберите существующую папку без символической ссылки")
    items: list[BatchCandidate] = []
    total = 0
    for current, dirs, files in os.walk(base, topdown=True, followlinks=False):
        dirs[:] = sorted(
            d for d in dirs if d not in IGNORED_DIRS and not (Path(current) / d).is_symlink()
        )
        for filename in sorted(files):
            path = Path(current) / filename
            if path.is_symlink() or not path.is_file():
                continue
            size = path.stat().st_size
            total += size
            if len(items) >= MAX_BATCH_FILES or total > MAX_BATCH_BYTES:
                raise ValueError("Пакет превышает лимиты PoC: 500 файлов / 512 MiB")
            items.append(
                BatchCandidate(
                    path=path,
                    relative_path=path.relative_to(base).as_posix(),
                    size=size,
                    supported_parser=path.suffix.lower() in SUPPORTED,
                )
            )
    return items
