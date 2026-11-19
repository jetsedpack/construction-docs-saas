"""Offline lint for the edited draw.io atlas and draft AI roundtrip contracts.

No network, dependencies or customer data required. Run:
    python scripts/check_architecture.py
"""
from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
ATLAS = ROOT / "diagrams" / "atlas"
CONTRACTS = ROOT / "docs" / "contracts"


class ContractError(ValueError):
    """The agreed structure does not match its draft contract."""


def check_shape(value: object, schema: dict, root: dict, path: str = "$") -> None:
    """Small offline JSON-Schema subset sufficient for our draft contracts.

    This is NOT a replacement for production JSON Schema validation or data-loss
    prevention. It checks shape, types and allowlists, never semantic privacy.
    """
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            raise ContractError(f"{path}: external refs not supported")
        check_shape(value, root["$defs"][ref.split("/")[-1]], root, path)
        return
    if "const" in schema and value != schema["const"]:
        raise ContractError(f"{path}: unexpected constant")
    if "enum" in schema and value not in schema["enum"]:
        raise ContractError(f"{path}: enum")
    types = schema.get("type")
    if types:
        names = [types] if isinstance(types, str) else types

        def is_type(name: str) -> bool:
            return {
                "object": lambda: isinstance(value, dict),
                "array": lambda: isinstance(value, list),
                "string": lambda: isinstance(value, str),
                "integer": lambda: type(value) is int,
                "number": lambda: type(value) in (int, float),
                "boolean": lambda: type(value) is bool,
                "null": lambda: value is None,
            }[name]()

        if not any(is_type(name) for name in names):
            raise ContractError(f"{path}: wrong type")
    if isinstance(value, dict):
        required = schema.get("required", [])
        missing = set(required) - set(value)
        if missing:
            raise ContractError(f"{path}: required fields missing: {sorted(missing)}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(properties)
            if extra:
                raise ContractError(f"{path}: forbidden fields: {sorted(extra)}")
        for key, item in value.items():
            if key in properties:
                check_shape(item, properties[key], root, path + "." + key)
    elif isinstance(value, list):
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise ContractError(f"{path}: too many items")
        if "minItems" in schema and len(value) < schema["minItems"]:
            raise ContractError(f"{path}: too few items")
        if "prefixItems" in schema:
            for i, item in enumerate(value):
                if i < len(schema["prefixItems"]):
                    check_shape(item, schema["prefixItems"][i], root, f"{path}[{i}]")
        if "items" in schema:
            for i, item in enumerate(value):
                check_shape(item, schema["items"], root, f"{path}[{i}]")
    elif isinstance(value, str):
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise ContractError(f"{path}: too long")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            raise ContractError(f"{path}: invalid pattern")
    elif type(value) in (int, float):
        if "minimum" in schema and value < schema["minimum"]:
            raise ContractError(f"{path}: too small")
        if "maximum" in schema and value > schema["maximum"]:
            raise ContractError(f"{path}: too big")


def check_contracts() -> None:
    pairs = [
        ("structured-packet.schema.json", "structured-packet.synthetic.json"),
        ("prepared-document.schema.json", "prepared-document.synthetic.json"),
    ]
    for schema_name, example_name in pairs:
        schema = json.loads((CONTRACTS / schema_name).read_text(encoding="utf-8"))
        example = json.loads((CONTRACTS / "examples" / example_name).read_text(encoding="utf-8"))
        check_shape(example, schema, schema)
        forbidden_keys = {"filename", "original_path", "author_name", "source_title", "password"}
        outbound_keys = set()

        def find_keys(item: object) -> None:
            if isinstance(item, dict):
                outbound_keys.update(item)
                for v in item.values():
                    find_keys(v)
            elif isinstance(item, list):
                for v in item:
                    find_keys(v)

        find_keys(example)
        if outbound_keys & forbidden_keys:
            raise ContractError(f"{example_name}: prohibited keys")
        if "ИП Иванов" in json.dumps(example, ensure_ascii=False):
            raise ContractError(f"{example_name}: example leaks real alias value")
    registry = json.loads((CONTRACTS / "document-types.draft.json").read_text(encoding="utf-8"))
    types = registry["types"]
    ids = [item["id"] for item in types]
    if len(ids) != len(set(ids)) or len(ids) < 15:
        raise ContractError("Document types: duplicates or incomplete draft catalog")
    if any(item.get("export_policy") != "blocked_until_review" for item in types):
        raise ContractError("Document type must not grant export permission")



def _strict_cross(a: tuple, b: tuple) -> bool:
    """Detect crossing strictly within both orthogonal segments (not shared tips)."""
    p, q = a
    r, s = b
    if p[0] == q[0] and r[1] == s[1]:
        x, y = p[0], r[1]
        return (
            min(r[0], s[0]) < x < max(r[0], s[0])
            and min(p[1], q[1]) < y < max(p[1], q[1])
        )
    if p[1] == q[1] and r[0] == s[0]:
        return _strict_cross(b, a)
    return False


def check_layout_geometry() -> None:
    """Enforce collision-free sources for both SVG previews and editable draw.io.

    The asset compiler shares the same numeric routes across both file types.
    Cards have an 5px safety inset; crossings/overflow fail CI.
    """
    atlas = json.loads((ATLAS / "source.json").read_text(encoding="utf-8"))
    from xml.sax.saxutils import escape as xml_escape

    for page in atlas["pages"]:
        title = page["id"]
        nodes = page["nodes"]
        by_id = {node["id"]: node for node in nodes}
        if len(by_id) != len(nodes):
            raise ContractError(f"{title}: duplicate node ID")
        if len(page["wires"]) < 6:
            raise ContractError(f"{title}: incomplete connections")

        # All cards have enough breathing room and stay within printable canvas.
        for node in nodes:
            x, y, w, h = (node[k] for k in ("x", "y", "w", "h"))
            if x < 65 or y < 180 or x + w > page["w"] - 55 or y + h > page["h"] - 35:
                raise ContractError(f"{title}/{node['id']}: outside page")
            size = 13 if w <= 180 else 18
            body_size = 12 if w <= 180 else 15
            room = w - (28 if w <= 180 else 36)
            for text, font_size in [(node["title"], size)] + [
                (v, body_size) for v in node["body"]
            ]:
                estimated = sum(
                    (0.28 if ch == " " else 0.69 if ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZЖШЩМЫЮОФ"
                     else 0.55) for ch in text
                ) * font_size
                if estimated > room:
                    raise ContractError(f"{title}/{node['id']}: text may overflow: {text}")
        for i, a in enumerate(nodes):
            for b in nodes[i + 1:]:
                if (a["x"] < b["x"] + b["w"] and a["x"] + a["w"] > b["x"]
                    and a["y"] < b["y"] + b["h"] and a["y"] + a["h"] > b["y"]):
                    raise ContractError(f"{title}: blocks overlap {a['id']}/{b['id']}")

        segments: list[tuple[str, tuple, tuple]] = []
        for edge in page["wires"]:
            if edge["from"] not in by_id or edge["to"] not in by_id:
                raise ContractError(f"{title}: endpoint missing")
            points = edge["points"]
            if len(points) < 2:
                raise ContractError(f"{title}: wire without route")
            eid = edge["from"] + "->" + edge["to"]
            for start, end in zip(points, points[1:]):
                x1, y1 = start
                x2, y2 = end
                if x1 != x2 and y1 != y2:
                    raise ContractError(f"{title}/{eid}: diagonal route")
                for block in nodes:
                    if block["id"] in (edge["from"], edge["to"]):
                        continue
                    left = block["x"] + 5
                    right = block["x"] + block["w"] - 5
                    top = block["y"] + 5
                    bottom = block["y"] + block["h"] - 5
                    if x1 == x2:
                        hit = (
                            left < x1 < right
                            and max(min(y1, y2), top) < min(max(y1, y2), bottom)
                        )
                    else:
                        hit = (
                            top < y1 < bottom
                            and max(min(x1, x2), left) < min(max(x1, x2), right)
                        )
                    if hit:
                        raise ContractError(f"{title}: wire {eid} enters {block['id']}")
                for other_eid, other_start, other_end in segments:
                    if other_eid != eid and _strict_cross((start, end), (other_start, other_end)):
                        raise ContractError(f"{title}: crossing arrows {eid} vs {other_eid}")
                segments.append((eid, start, end))

        # Check the generated previews contain all authored card labels.
        svg_names = {
            "a0": "a0-system.svg",
            "f01": "f01-intake.svg",
            "roundtrip": "f04-f06-roundtrip.svg",
            "f07": "f07-norms.svg",
        }
        svg = (ATLAS / svg_names[title]).read_text(encoding="utf-8")
        for node in nodes:
            if xml_escape(node["title"]) not in svg:
                raise ContractError(f"{title}: SVG missing card {node['id']}")
        diagram = next(
            (d for d in ET.parse(ATLAS / "architecture.drawio").getroot().findall("diagram")
             if d.attrib.get("id") == title),
            None,
        )
        if diagram is None:
            raise ContractError(f"{title}: missing editable diagram")
        cells = diagram.findall("mxGraphModel/root/mxCell")
        all_ids = {cell.attrib.get("id") for cell in cells}
        if any(node["id"] not in all_ids for node in nodes):
            raise ContractError(f"{title}: draw.io lost editable card IDs")
        wires = [cell for cell in cells if cell.attrib.get("edge") == "1"]
        if len(wires) != len(page["wires"]):
            raise ContractError(f"{title}: draw.io lost arrows")


def check_diagrams() -> None:
    source = json.loads((ATLAS / "source.json").read_text(encoding="utf-8"))
    design_pages = source["pages"]
    doc = ET.parse(ATLAS / "architecture.drawio").getroot()
    xml_pages = doc.findall("diagram")
    if len(design_pages) != 4 or len(xml_pages) != 4:
        raise ContractError("Atlas needs exactly four canonical pages")
    if [p["id"] for p in design_pages] != [p.attrib["id"] for p in xml_pages]:
        raise ContractError("draw.io page order does not match authored source")
    for model in xml_pages:
        graph = model.find("mxGraphModel/root")
        if graph is None:
            raise ContractError("Missing mxGraphModel")
        vertices = {c.attrib["id"] for c in graph.findall("mxCell") if c.attrib.get("vertex") == "1"}
        edges = [c for c in graph.findall("mxCell") if c.attrib.get("edge") == "1"]
        if not edges:
            raise ContractError("Diagram without functional links")
        for e in edges:
            if e.attrib.get("source") not in vertices or e.attrib.get("target") not in vertices:
                raise ContractError(f"Dangling link {e.attrib.get('id')}")
    for filename in ["a0-system.svg", "f01-intake.svg", "f04-f06-roundtrip.svg", "f07-norms.svg"]:
        svg = ET.parse(ATLAS / filename).getroot()
        if not svg.tag.endswith("svg") or "viewBox" not in svg.attrib:
            raise ContractError(f"{filename}: not compiled SVG")
        if len(list(svg)) < 20:
            raise ContractError(f"{filename}: incomplete vector export")


def check_links() -> None:
    docs = [
        ROOT / "README.md",
        ATLAS / "README.md",
        ROOT / "docs" / "decisions" / "2026-11-18-product-contract.md",
        ROOT / "docs" / "implementation" / "11-vertical-slice-plan.md",
    ]
    for file in docs:
        body = file.read_text(encoding="utf-8")
        for target in re.findall(r"!?(?:\[[^\]]+\])\(([^)]+)\)", body):
            if target.startswith(("https://", "http://", "#", "mailto:")):
                continue
            target = unquote(target).split("#", 1)[0]
            if not (file.parent / target).exists():
                raise ContractError(f"{file.relative_to(ROOT)}: missing link {target}")


def run() -> None:
    check_contracts()
    check_diagrams()
    check_layout_geometry()
    check_links()
    print("OK: structured contracts, 4 draw.io pages, 4 compiled SVGs, document catalog and links")


if __name__ == "__main__":
    try:
        run()
    except (ValueError, OSError, ET.ParseError, KeyError) as exc:
        print(f"Architecture lint failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
