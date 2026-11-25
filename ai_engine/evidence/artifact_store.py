import os
from pathlib import Path
from uuid import uuid4

from ai_engine.api.schemas import InspectionResult


def atomic_write(path, content):
    temporary = path.with_name(f".{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class ArtifactStore:
    def __init__(self, root: Path):
        self.root = root

    def _job_dir(self, inspection_id):
        return self.root / str(inspection_id)

    def read(self, inspection_id):
        return InspectionResult.model_validate_json(
            (self._job_dir(inspection_id) / "manifest.json").read_bytes()
        )

    def write(self, result, capture=None, data=None):
        directory = self._job_dir(result.inspection_id)
        directory.mkdir(parents=True, exist_ok=True)
        if capture:
            atomic_write(directory / str(capture.capture_id), data)
        atomic_write(directory / "manifest.json", result.model_dump_json(indent=2).encode())

    def image_path(self, inspection_id, capture_id):
        return self._job_dir(inspection_id) / str(capture_id)
