import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ai_engine import ROOT
from ai_engine.acquisition.image_loader import MAX_IMAGE_BYTES, decode_image
from ai_engine.api.app import create_app
from ai_engine.api.schemas import InspectionResult
from ai_engine.preprocessing.vision import LeatherRules, load_leather_rules, original_box

IDS = {"product_id": "synthetic", "lot_id": "software-test", "profile": "leather"}
CAPTURE = {"view": "front", "lighting": "manual_diffuse"}


def post(client, data, raw, url="/inspect", media="image/png"):
    return client.post(url, data=data, files={"image": ("fixture", raw, media)})


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path, benchmark_path=tmp_path / "benchmark.json")) as client:
        yield client


def test_two_views_cover_required_surface_and_preserve_original(client, synthetic_image, tmp_path):
    first = synthetic_image()
    second = synthetic_image(mark=True, shade=10, format="JPEG")
    response = post(client, IDS | CAPTURE, first)
    assert response.status_code == 202, response.text
    initial = InspectionResult.model_validate(response.json())
    assert initial.status == "awaiting_capture"
    assert initial.recommendation == "hold"
    assert initial.coverage.inspected_regions == 1
    assert initial.uncertain_regions == []
    assert initial.actions[0].view == "back"
    base = f"/inspections/{initial.inspection_id}"
    fields = CAPTURE | {"view": "back"}
    assert post(client, fields, first, base + "/captures").status_code == 409
    response = post(client, fields, second, base + "/captures", media="image/jpeg")
    assert response.status_code == 202, response.text
    result = InspectionResult.model_validate(response.json())
    assert result.status == "completed"
    assert result.recommendation == "review"
    assert result.coverage.complete and result.human_approval_required
    assert result.defects == []
    mark = result.uncertain_regions[0]
    assert mark.region_id == "back" and 0.25 < mark.box.x < 0.45
    assert mark.evidence_id == result.evidence[1].capture_id
    assert result.evidence[1].sha256 == sha256(second).hexdigest()
    assert client.get(result.evidence[1].image_url).content == second
    assert len(client.get(base + "/evidence").json()) == 2
    assert TestClient(create_app(tmp_path)).get(base).json() == response.json()


def test_clean_pair_requires_human_approval(client, synthetic_image):
    initial = post(client, IDS | CAPTURE, synthetic_image()).json()
    url = f"/inspections/{initial['inspection_id']}/captures"
    result = post(client, CAPTURE | {"view": "back"}, synthetic_image(shade=8), url).json()
    assert result["recommendation"] == "no_defect_flagged"
    assert result["human_approval_required"] is True


def test_resolution_and_lighting_block_coverage(client, synthetic_image):
    result = post(client, IDS | CAPTURE, synthetic_image(size=300)).json()
    assert "resolution_below_profile_minimum" in result["image_quality"]["warnings"]
    assert result["actions"][0]["kind"] == "recapture"
    base = f"/inspections/{result['inspection_id']}"
    result = post(client, CAPTURE | {"lighting": "manual_left"}, synthetic_image(), base + "/captures").json()
    assert result["coverage"]["inspected_regions"] == 0
    assert result["actions"][0]["reason"] == "baseline_lighting_required"
    closed = client.post(base + "/finish").json()
    assert closed["status"] == "completed" and closed["recommendation"] == "hold"
    assert post(client, CAPTURE, synthetic_image(shade=3), base + "/captures").status_code == 409


def test_attempt_budget_cannot_override_coverage(client, synthetic_image):
    result = post(client, IDS | CAPTURE, synthetic_image(size=300)).json()
    url = f"/inspections/{result['inspection_id']}/captures"
    for size in (301, 302, 303):
        result = post(client, CAPTURE, synthetic_image(size=size), url).json()
    assert result["status"] == "completed" and result["recommendation"] == "hold"
    assert "capture_budget_exhausted" in result["warnings"]


def test_expiry_preserves_hold(client, synthetic_image, tmp_path):
    result = post(client, IDS | CAPTURE, synthetic_image()).json()
    path = tmp_path / result["inspection_id"] / "manifest.json"
    result["evidence"][0]["received_at"] = (datetime.now(UTC) - timedelta(minutes=11)).isoformat()
    path.write_text(json.dumps(result), encoding="utf-8")
    expired = client.get(f"/inspections/{result['inspection_id']}").json()
    assert expired["status"] == "completed" and expired["recommendation"] == "hold"
    assert "capture_window_expired" in expired["warnings"]


def test_invalid_and_unsupported_inputs(client, synthetic_image):
    assert post(client, IDS | CAPTURE, b"broken").status_code == 422
    assert post(client, IDS | CAPTURE, synthetic_image(), media="image/jpeg").status_code == 422
    assert post(client, IDS | CAPTURE, synthetic_image(), media="image/webp").status_code == 415
    assert post(client, IDS | CAPTURE, b"x" * (MAX_IMAGE_BYTES + 1)).status_code == 413
    assert post(client, IDS | CAPTURE | {"profile": "footwear"}, synthetic_image()).status_code == 422
    assert post(client, IDS | CAPTURE | {"product_id": " "}, synthetic_image()).status_code == 422
    assert client.get("/inspections/not-a-uuid").status_code == 422
    assert client.get("/inspections/11111111-1111-4111-8111-111111111111").status_code == 404
    assert client.post("/inspect", headers={"Content-Type": "multipart/form-data"}, content=b"broken").status_code == 400


def test_upload_above_default_multipart_spool_threshold(client, synthetic_image):
    data = synthetic_image(compress_level=0)
    assert len(data) > 1024 * 1024
    assert post(client, IDS | CAPTURE, data).status_code == 202


def test_hardware_failures_are_explicit(client):
    assert client.get("/hardware/status").json()["esp32_verified"] is False
    assert client.post("/lighting/set", json={"mode": "LEFT", "brightness": 10}).status_code == 503
    assert client.post("/lighting/set", json={"mode": "UNKNOWN"}).status_code == 422
    assert client.post("/capture", json=CAPTURE).status_code == 503
    assert client.post("/capture", json={"view": "x" * 4096}).status_code == 413
    assert client.post("/capture", data=CAPTURE).status_code == 415
    assert client.post("/inspect", json=IDS | {"source": "station"}).status_code == 503
    assert client.get("/benchmarks/latest").status_code == 404


def test_profile_rules_load_and_reject_duplicate_views():
    rules = load_leather_rules()
    assert rules.required_views == ["front", "back"]
    with pytest.raises(ValidationError, match="Required views must be unique"):
        LeatherRules.model_validate(rules.model_dump() | {"required_views": ["front", "front"]})


def test_authentication(tmp_path):
    token = "synthetic-contract-token-32-characters"
    client = TestClient(create_app(tmp_path, token))
    assert client.get("/health").status_code == 401
    assert client.get("/health", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_exif_and_mapping(synthetic_image):
    image, _, orientation = decode_image(synthetic_image(format="JPEG", orientation=6), "image/jpeg")
    assert orientation == 6 and 274 not in image.getexif()
    box = original_box(0.2, 0.1, 0.3, 0.2, orientation)
    assert list(box.model_dump().values()) == pytest.approx([0.1, 0.5, 0.2, 0.3])


def test_exported_contract_matches_runtime(client):
    shared = ROOT / "shared"
    spec = json.loads((shared / "openapi.json").read_text())
    assert spec == client.get("/openapi.json").json()
    assert spec["info"]["version"] == (shared / "contract-version.txt").read_text().strip()
    assert json.loads((shared / "inspection-schema.json").read_text()) == InspectionResult.model_json_schema()
    meta = json.loads((shared / "api-contract.json").read_text())
    assert all(path in spec["paths"] for path in meta["endpoints"])
