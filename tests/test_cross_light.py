from io import BytesIO

import cv2
import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from ai_engine.api.app import create_app
from ai_engine.api.schemas import Box
from ai_engine.leo_eve.cross_light import compare


def test_registration_compares_translated_candidate_and_rejects_unrelated_surface():
    rng = np.random.default_rng(52)
    pixels = np.full((640, 640, 3), 205, dtype=np.uint8)
    for _ in range(160):
        x, y = map(int, rng.integers(95, 545, size=2))
        color = int(rng.integers(35, 175))
        cv2.circle(pixels, (x, y), int(rng.integers(3, 11)), (color, color, color), -1)
    shifted = cv2.warpAffine(pixels, np.float32([[1, 0, 18], [0, 1, -13]]), (640, 640),
                             borderValue=(205, 205, 205))
    surfaces = Box(x=0.1, y=0.1, width=0.8, height=0.8)
    original = Box(x=0.35, y=0.4, width=0.15, height=0.08)
    same = Box(x=original.x + 18 / 640, y=original.y - 13 / 640, width=original.width, height=original.height)
    different = Box(x=0.68, y=0.7, width=0.1, height=0.1)
    baseline = Image.fromarray(pixels)
    other = Image.fromarray(shifted)
    assert compare(baseline, 1, surfaces, [original], other, 1, surfaces, [same]) == [0]
    assert compare(baseline, 1, surfaces, [original], other, 1, surfaces, [different]) == []
    assert compare(baseline, 1, surfaces, [original], Image.new("RGB", (640, 640)), 1, surfaces, [same]) is None


def test_directional_capture_fuses_in_same_inspection(tmp_path, synthetic_image):
    rng = np.random.default_rng(3)
    baseline = np.full((640, 640, 3), 205, dtype=np.uint8)
    baseline[105:535, 105:535] = (128, 92, 67)
    for _ in range(190):
        x, y = map(int, rng.integers(125, 515, 2))
        delta = int(rng.choice([-21, 21]))
        cv2.circle(baseline, (x, y), int(rng.integers(3, 10)), (128 + delta, 92 + delta, 67 + delta), -1)
    baseline[310:315, 260:385] = (39, 22, 17)
    directional = np.clip(baseline.astype(np.int16) + 4, 0, 255).astype(np.uint8)
    directional = cv2.warpAffine(directional, np.float32([[1, 0, 8], [0, 1, -6]]), (640, 640),
                                 borderValue=(209, 209, 209))
    files = []
    for pixels in (baseline, directional):
        raw = BytesIO()
        Image.fromarray(pixels).save(raw, "PNG")
        files.append({"image": ("fixture.png", raw.getvalue(), "image/png")})
    with TestClient(create_app(tmp_path)) as client:
        first = client.post("/inspect", data={"product_id": "fixture", "lot_id": "simulation", "profile": "leather",
                                             "view": "front", "lighting": "NORMAL", "camera_source": "phone_file"},
                            files=files[0]).raise_for_status().json()
        assert first["evidence"][0]["camera_source"] == "phone_file"
        base = f"/inspections/{first['inspection_id']}"
        baseline_pair = client.post(base + "/captures", data={"view": "back", "lighting": "NORMAL"},
                                    files={"image": ("back.png", synthetic_image(), "image/png")}).raise_for_status().json()
        assert baseline_pair["coverage"]["complete"] and baseline_pair["recommendation"] == "hold"
        assert baseline_pair["actions"][0]["target_box"] and baseline_pair["actions"][0]["view"] == "front"
        result = client.post(base + "/captures", data={"view": "front", "lighting": "RIGHT"},
                             files=files[1]).raise_for_status().json()
        assert result["status"] == "completed" and result["recommendation"] == "review"
        assert "cross_light_persistent_candidates" in result["warnings"]
        assert len(result["evidence"]) == 3 and result["human_approval_required"]
        findings = client.get(base + "/findings").raise_for_status().json()
        assert findings and all(item["method"] == "masked_local_contrast" for item in findings)
        assert len({item["candidate_id"] for item in findings}) == len(findings)
