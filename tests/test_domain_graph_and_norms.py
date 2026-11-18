from datetime import date
import pytest
from construction_docs.graph import Edge, EntityGraph, Node
from construction_docs.norms import NormativeCatalog, NormativeEdition

def test_work_to_pnr_has_evidence_path():
    graph = EntityGraph()
    for ident, kind in [
        ("work-1", "work"), ("cabinet-1", "equipment"),
        ("pnr-1", "pnr_protocol"), ("ev-1", "evidence"),
    ]:
        graph.add_node(Node(ident, kind, "СИНТЕТИЧЕСКИЙ"))
    graph.connect(Edge("work-1", "installed_as", "cabinet-1", ("ev-1",)))
    graph.connect(Edge("cabinet-1", "tested_by", "pnr-1", ("ev-1",)))
    route = graph.path("work-1", "pnr-1")
    assert [e.relation for e in route] == ["installed_as", "tested_by"]
    assert EntityGraph.from_dict(graph.to_dict()).path("work-1", "pnr-1") == route

def test_disallow_unproven_new_nodes_or_relations():
    graph = EntityGraph()
    graph.add_node(Node("work-1", "work", "test"))
    with pytest.raises(ValueError):
        graph.connect(Edge("work-1", "approved_by", "missing-approver"))

def test_norms_by_effective_date_and_region():
    cat = NormativeCatalog()
    first = NormativeEdition(
        code="FAKE-NORM", revision="v1", kind="NPA",
        published_at=date(2024, 1, 10), effective_from=date(2024, 2, 1),
        effective_until=date(2025, 1, 31), jurisdiction="RU",
        scope=frozenset({"construction"}), source_url="https://example.org/fake",
        reviewed_by="domain_expert", reviewed_at=date(2024, 1, 25),
    )
    cat.register(first)
    assert cat.applicable("FAKE-NORM", date(2024, 8, 1), "RU-05", "construction") == [first]
    assert cat.applicable("FAKE-NORM", date(2025, 2, 1), "RU-05", "construction") == []
    with pytest.raises(ValueError):
        cat.register(first)
