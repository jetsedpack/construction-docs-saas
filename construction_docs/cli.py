"""Local-only CLI diagnostics for engineers; Windows vault required."""
from __future__ import annotations

import argparse
import json

from .rules import check_register
from .vault import EncryptedVault


def main() -> int:
    parser = argparse.ArgumentParser(description="Construction Docs Windows local PoC")
    sub = parser.add_subparsers(dest="command", required=True)
    p_import = sub.add_parser("import", help="Import supported file into encrypted vault")
    p_import.add_argument("file")
    sub.add_parser("list", help="List imported documents")
    p_check = sub.add_parser("check", help="Check previously imported Excel/CSV register")
    p_check.add_argument("document_id")
    args = parser.parse_args()

    with EncryptedVault() as vault:
        if args.command == "import":
            doc = vault.import_file(args.file)
            print(json.dumps({"id": doc.id, "name": doc.name, "warnings": doc.warnings}, ensure_ascii=False))
        elif args.command == "list":
            print(json.dumps([
                {"id": d.id, "name": d.name, "kind": d.kind} for d in vault.list_documents()
            ], ensure_ascii=False, indent=2))
        elif args.command == "check":
            doc = vault.get_document(args.document_id)
            findings = check_register(doc)
            vault.save_findings(doc.id, findings)
            print(json.dumps([f.local_json() for f in findings], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
