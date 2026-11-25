"""Replay labeled front/back captures and measure piece-level candidate screening."""

import argparse
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_engine import ROOT
from ai_engine.acquisition.image_loader import MAX_IMAGE_BYTES
from ai_engine.api.schemas import BenchmarkResult, CaptureInput, InspectionInput
from ai_engine.evidence.artifact_store import ArtifactStore, atomic_write
from ai_engine.leo_eve.engine import Engine
from ai_engine.preprocessing.vision import load_leather_rules


class Piece(BaseModel):
    model_config = ConfigDict(extra="forbid")
    piece_id: str = Field(min_length=1, max_length=128)
    label: Literal["normal", "defective", "critical"]
    front: Path
    back: Path


class Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str = Field(min_length=1, max_length=128)
    source: Literal["physical", "synthetic"]
    pieces: list[Piece] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_pieces(self):
        if len({piece.piece_id for piece in self.pieces}) != len(self.pieces):
            raise ValueError("Piece IDs must be unique")
        return self


def fraction(numerator, denominator):
    return numerator / denominator if denominator else None


def run(dataset, image_root, evidence_root, rules):
    engine = Engine(ArtifactStore(evidence_root), rules)
    normal = defective = false_positives = true_positives = missed_critical = holds = captures = 0
    inspected_views = required_views = 0
    timing = []
    for piece in dataset.pieces:
        inputs = InspectionInput(profile="leather", product_id=piece.piece_id, lot_id=dataset.dataset_id)
        result = None
        for view, relative in (("front", piece.front), ("back", piece.back)):
            path = (image_root / relative).resolve(strict=True)
            if not path.is_relative_to(image_root):
                raise ValueError("Images must be inside the dataset directory")
            media = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(path.suffix.lower())
            if media is None:
                raise ValueError(f"Unsupported image extension for piece {piece.piece_id}")
            with path.open("rb") as handle:
                data = handle.read(MAX_IMAGE_BYTES + 1)
            capture = CaptureInput(view=view, lighting="manual_diffuse")
            if result is None:
                result = engine.start(inputs, capture, data, media)
            else:
                result = engine.add_capture(result.inspection_id, capture, data, media)
        result = engine.finish(result.inspection_id)
        flagged = result.recommendation == "review"
        if piece.label == "normal":
            normal += 1
            false_positives += flagged
        else:
            defective += 1
            true_positives += flagged
            missed_critical += piece.label == "critical" and not flagged
        holds += result.recommendation == "hold"
        captures += len(result.evidence)
        timing.append(result.processing_time_ms)
        inspected_views += result.coverage.inspected_regions
        required_views += result.coverage.required_regions
    return BenchmarkResult(
        measured_at=datetime.now(UTC), dataset_id=dataset.dataset_id, source=dataset.source,
        pieces=len(dataset.pieces), captures=captures, holds=holds, missed_critical_pieces=missed_critical,
        piece_recall=fraction(true_positives, defective),
        piece_precision=fraction(true_positives, true_positives + false_positives),
        piece_false_positive_rate=fraction(false_positives, normal),
        required_view_coverage=inspected_views / required_views,
        median_decode_and_analysis_ms=median(timing),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--publish", action="store_true", help="Expose physical results through the local API")
    args = parser.parse_args()
    dataset = Dataset.model_validate_json(args.dataset.read_bytes())
    if args.publish and dataset.source != "physical":
        parser.error("Publishing requires a physical dataset")
    rules = load_leather_rules()
    storage = ROOT / "storage/benchmarks"
    storage.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=storage) as working:
        report = run(dataset, args.dataset.resolve().parent, Path(working), rules)
    content = report.model_dump_json(indent=2)
    if args.publish:
        atomic_write(storage / "latest.json", (content + "\n").encode())
    print(content)


if __name__ == "__main__":
    main()
