"""Local, provenance-aware graph: the 'box' is a graph of records, not a folder tree.

This is a minimal domain core for the PoC. It has no network capabilities.
All labels and attributes are PRIVATE and should be serialized only into the vault.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any

ENTITY_KINDS = frozenset({
    "project", "section", "work", "drawing_revision", "estimate_line",
    "equipment", "material_batch", "contractor", "id_document", "pnr_protocol",
    "configuration_artifact", "quality_document", "evidence", "normative_edition",
    "change_request", "inspection", "source_document",
})
RELATION_KINDS = frozenset({
    "contains", "specifies", "planned_by", "performed_by", "installed_as", "uses",
    "evidenced_by", "listed_in", "inspected_in", "tested_by", "configured_by",
    "based_on", "has_revision", "applies_to", "has_exception", "derived_from",
    "approved_by", "references",
})


@dataclass(frozen=True)
class Node:
    id: str
    kind: str
    label: str
    attributes: dict[str, Any] = field(default_factory=dict)
    state: str = "unverified"


@dataclass(frozen=True)
class Edge:
    source: str
    relation: str
    target: str
    evidence_ids: tuple[str, ...] = ()


class EntityGraph:
    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []

    def add_node(self, node: Node) -> None:
        if node.kind not in ENTITY_KINDS or not node.id or len(node.id) > 128:
            raise ValueError("Неверная сущность")
        if node.id in self.nodes:
            raise ValueError("Нельзя молча заменить существующую сущность")
        if node.state not in {"unverified", "verified", "rejected", "proposed"}:
            raise ValueError("Неверный статус подтверждения")
        self.nodes[node.id] = node

    def connect(self, edge: Edge) -> None:
        if edge.relation not in RELATION_KINDS:
            raise ValueError("Неизвестный тип связи")
        if edge.source not in self.nodes or edge.target not in self.nodes:
            raise ValueError("Связь требует существующих сущностей")
        if any(evidence not in self.nodes or self.nodes[evidence].kind != "evidence"
               for evidence in edge.evidence_ids):
            raise ValueError("Для связи указан отсутствующий источник доказательства")
        if edge not in self.edges:
            self.edges.append(edge)

    def neighbors(self, source_id: str) -> list[tuple[Edge, Node]]:
        return [
            (edge, self.nodes[edge.target]) for edge in self.edges
            if edge.source == source_id
        ]

    def path(self, start: str, finish: str, max_hops: int = 10) -> list[Edge] | None:
        """Shortest directed evidence path. None is not evidence of absence in reality."""
        if start not in self.nodes or finish not in self.nodes:
            return None
        queue = deque([(start, [])])
        seen = {start}
        while queue:
            node, route = queue.popleft()
            if node == finish:
                return route
            if len(route) >= max_hops:
                continue
            for edge, nxt in self.neighbors(node):
                if nxt.id not in seen:
                    seen.add(nxt.id)
                    queue.append((nxt.id, [*route, edge]))
        return None

    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "nodes": [asdict(node) for node in self.nodes.values()],
            "edges": [asdict(edge) for edge in self.edges],
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "EntityGraph":
        if payload.get("schema_version") != 1:
            raise ValueError("Версия структуры графа не поддерживается")
        graph = cls()
        for entry in payload.get("nodes", []):
            graph.add_node(Node(**entry))
        for entry in payload.get("edges", []):
            graph.connect(Edge(
                source=entry["source"], relation=entry["relation"], target=entry["target"],
                evidence_ids=tuple(entry.get("evidence_ids", ())),
            ))
        return graph
