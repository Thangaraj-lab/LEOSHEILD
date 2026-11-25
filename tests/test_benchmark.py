from fastapi.testclient import TestClient

from ai_engine.api.app import create_app
from ai_engine.preprocessing.vision import load_leather_rules
from scripts.benchmark import Dataset, run


def test_measure_screening_without_publishing_synthetic_data(tmp_path, synthetic_image):
    (tmp_path / "front.png").write_bytes(synthetic_image())
    (tmp_path / "normal.png").write_bytes(synthetic_image(shade=5))
    (tmp_path / "mark.png").write_bytes(synthetic_image(mark=True))
    dataset = Dataset.model_validate({
        "dataset_id": "generated-test", "source": "synthetic",
        "pieces": [
            {"piece_id": "A", "label": "normal", "front": "front.png", "back": "normal.png"},
            {"piece_id": "B", "label": "critical", "front": "front.png", "back": "mark.png"},
        ],
    })
    report = run(dataset, tmp_path, tmp_path / "records", load_leather_rules())
    assert report.source == "synthetic"
    assert report.pieces == 2 and report.holds == 0 and report.required_view_coverage == 1
    assert report.piece_recall == 1 and report.piece_precision == 1 and report.piece_false_positive_rate == 0
    assert report.median_decode_and_analysis_ms > 0
    benchmark = tmp_path / "latest.json"
    benchmark.write_text(report.model_dump_json(), encoding="utf-8")
    client = TestClient(create_app(tmp_path / "records", benchmark_path=benchmark))
    assert client.get("/benchmarks/latest").status_code == 404
