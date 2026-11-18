import json
import pytest
from construction_docs.gateway import GPUGOGateway, GatewayError, safe_batch, validate_endpoint, validate_recommendations
from construction_docs.models import Issue

def sample():
    return Issue(
        category="page_count_mismatch", severity="review",
        message="PRIVATE: real construction name 123",
        source_row=55, document_id="secret-file-id",
        metrics={"declared_count": 3, "calculated_count": 4},
    )

def test_allowlist_excludes_private_fields():
    raw = json.dumps(safe_batch([sample()]), ensure_ascii=False)
    assert "secret-file-id" not in raw
    assert "PRIVATE" not in raw
    assert "source_row" not in raw
    assert "document_id" not in raw
    assert '"declared_count": 3' in raw

@pytest.mark.parametrize("key,val", [
    ("filename", 1), ("raw_text", 42),
    ("declared_count", "14"), ("conflict_count", -1),
])
def test_unsafe_metrics_rejected(key, val):
    finding = Issue("page_count_mismatch", "review", "private", metrics={key: val})
    with pytest.raises(GatewayError):
        safe_batch([finding])

def test_endpoint_requires_https_and_exact_host():
    with pytest.raises(GatewayError):
        validate_endpoint("http://gpu.example.com/v1/chat/completions", {"gpu.example.com"})
    with pytest.raises(GatewayError):
        validate_endpoint("https://gpu.example.com.evil/v1/chat/completions", {"gpu.example.com"})
    validate_endpoint("https://gpu.example.com/v1/chat/completions", {"gpu.example.com"})

def test_response_must_have_known_index_and_action():
    good = {"recommendations": [{"index": 1, "action": "manual_review", "rationale": "Check original."}]}
    assert validate_recommendations(good, 1)[0]["index"] == 1
    with pytest.raises(GatewayError):
        validate_recommendations({"recommendations": [{"index": 2, "action": "delete", "rationale": "x"}]}, 1)

def test_no_url_no_api_key_is_offline(monkeypatch):
    monkeypatch.delenv("GPUGO_INFERENCE_URL", raising=False)
    monkeypatch.delenv("GPUGO_INFERENCE_TOKEN", raising=False)
    with pytest.raises(GatewayError):
        GPUGOGateway()
