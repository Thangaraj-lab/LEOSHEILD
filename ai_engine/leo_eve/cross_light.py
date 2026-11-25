"""Register two views of the same face before comparing contrast candidates."""

import cv2
import numpy as np
from PIL import Image

from ai_engine.preprocessing.vision import original_box


def _features(image, detector, surface):
    image = image.copy()
    image.thumbnail((960, 960), Image.Resampling.LANCZOS)
    gray = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2GRAY)
    left, top, right, bottom = _bounds(surface, gray.shape[1], gray.shape[0]).astype(int)
    mask = np.zeros_like(gray)
    inset = max(4, round(0.03 * min(right - left, bottom - top)))
    mask[top + inset:bottom - inset, left + inset:right - inset] = 255
    points, descriptors = detector.detectAndCompute(gray, mask)
    return gray.shape, points, descriptors


def _registered_transform(baseline, baseline_surface, directional, directional_surface):
    detector = cv2.ORB_create(nfeatures=1200)
    shape, target, target_desc = _features(baseline, detector, baseline_surface)
    source_shape, source, source_desc = _features(directional, detector, directional_surface)
    if shape != source_shape or target_desc is None or source_desc is None:
        return None
    matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(source_desc, target_desc, k=2)
    distinctive = [pair[0] for pair in matches if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance]
    # Limit repeated patterns matching the same reference point.
    unique = {}
    for match in sorted(distinctive, key=lambda match: match.distance):
        unique.setdefault(match.trainIdx, match)
    if len(unique) < 12:
        return None
    source_xy = np.float32([source[m.queryIdx].pt for m in unique.values()])
    target_xy = np.float32([target[m.trainIdx].pt for m in unique.values()])
    matrix, inliers = cv2.estimateAffinePartial2D(source_xy, target_xy, method=cv2.RANSAC, ransacReprojThreshold=3)
    if matrix is None or inliers is None:
        return None
    good = inliers.ravel().astype(bool)
    height, width = shape
    scale = np.hypot(matrix[0, 0], matrix[1, 0])
    rotation = abs(np.degrees(np.arctan2(matrix[1, 0], matrix[0, 0])))
    center = np.array([width / 2, height / 2])
    shift = np.linalg.norm(matrix[:, :2] @ center + matrix[:, 2] - center)
    if (good.sum() < 12 or good.mean() < 0.6 or not 0.85 <= scale <= 1.15 or rotation > 12
            or shift > 0.15 * min(shape) or np.any(np.ptp(source_xy[good], axis=0) < 0.15 * np.array([width, height]))):
        return None
    return matrix, width, height


def _display_bounds(box, orientation):
    inverse = {6: 8, 8: 6}.get(orientation, orientation)
    return original_box(box.x, box.y, box.width, box.height, inverse)


def _bounds(box, width, height, matrix=None):
    corners = np.float32([[x * width, y * height] for x in (box.x, box.x + box.width)
                          for y in (box.y, box.y + box.height)])
    if matrix is not None:
        corners = cv2.transform(corners[None, :, :], matrix)[0]
    return np.concatenate((corners.min(axis=0), corners.max(axis=0)))


def _overlap(first, second):
    intersection = np.prod(np.maximum(0, np.minimum(first[2:], second[2:]) - np.maximum(first[:2], second[:2])))
    union = np.prod(first[2:] - first[:2]) + np.prod(second[2:] - second[:2]) - intersection
    return float(intersection / union) if union > 0 else 0.0


def compare(baseline, baseline_orientation, baseline_surface, baseline_boxes,
            directional, directional_orientation, directional_surface, directional_boxes):
    """Return matched baseline indices or None when alignment is unverified."""
    try:
        registered = _registered_transform(baseline, _display_bounds(baseline_surface, baseline_orientation),
                                           directional, _display_bounds(directional_surface, directional_orientation))
    except cv2.error:
        return None
    if registered is None:
        return None
    matrix, width, height = registered
    extra = [_bounds(_display_bounds(box, directional_orientation), width, height, matrix)
             for box in directional_boxes]
    return [index for index, box in enumerate(baseline_boxes)
            if any(_overlap(_bounds(_display_bounds(box, baseline_orientation), width, height), other) >= 0.25
                   for other in extra)]
