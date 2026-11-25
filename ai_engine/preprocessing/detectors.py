"""Candidate-screening boundary for classical and future validated detectors."""

from collections.abc import Sequence
from typing import Protocol

import cv2
import numpy as np


class CandidateDetector(Protocol):
    def __call__(self, lab: np.ndarray, surface: np.ndarray, inner: np.ndarray
                 ) -> tuple[Sequence[tuple[int, int, int, int]], bool]:
        """Return candidate boxes in working-image pixels and a truncation flag."""


def local_contrast(lab, surface, inner):
    weights = (surface != 0).astype(np.float32)
    local_weight = cv2.GaussianBlur(weights, (0, 0), 7)
    local_sum = cv2.GaussianBlur(lab * weights[:, :, None], (0, 0), 7)
    local_reference = local_sum / np.maximum(local_weight[:, :, None], 1e-6)
    contrast = np.max(np.abs(lab - local_reference), axis=2)
    surface_contrast = contrast[inner]
    typical = float(np.median(surface_contrast))
    deviation = float(np.median(np.abs(surface_contrast - typical)))
    threshold = float(np.clip(typical + 6 * deviation, 24, 36))
    marked = ((contrast >= threshold) & inner).astype(np.uint8)
    marked = cv2.morphologyEx(marked, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(marked)
    candidates = [row for row in stats[1:count] if row[4] >= 14 and max(row[2:4]) >= 8]
    candidates.sort(key=lambda row: -int(row[4]))
    return [tuple(map(int, row[:4])) for row in candidates[:40]], len(candidates) > 40
