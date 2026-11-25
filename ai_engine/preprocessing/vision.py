import cv2
import numpy as np
import yaml
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai_engine import ROOT
from ai_engine.api.schemas import Box, Quality, View
from ai_engine.preprocessing.detectors import CandidateDetector, local_contrast


class LeatherRules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    material: str
    required_views: list[View] = Field(min_length=1, max_length=2)
    minimum_side: int = Field(ge=64, le=4096)
    minimum_sharpness: float = Field(ge=0)
    maximum_dark_fraction: float = Field(gt=0, le=1)
    maximum_glare_fraction: float = Field(gt=0, le=1)
    minimum_surface_fraction: float = Field(gt=0, lt=1)
    maximum_capture_attempts: int = Field(ge=2, le=16)
    maximum_directional_candidates: int = Field(default=6, ge=0, le=40)

    @field_validator("required_views")
    @classmethod
    def unique_views(cls, views):
        if len(views) != len(set(views)):
            raise ValueError("Required views must be unique")
        return views


def load_leather_rules():
    return LeatherRules.model_validate(yaml.safe_load(
        (ROOT / "config/profiles/leather.yaml").read_text(encoding="utf-8")
    ))


def original_box(x, y, width, height, orientation):
    """Map the EXIF-oriented rectangle to the original encoded pixel grid."""
    transforms = {
        2: lambda u, v: (1 - u, v),
        3: lambda u, v: (1 - u, 1 - v),
        4: lambda u, v: (u, 1 - v),
        5: lambda u, v: (v, u),
        6: lambda u, v: (v, 1 - u),
        7: lambda u, v: (1 - v, 1 - u),
        8: lambda u, v: (1 - v, u),
    }
    transform = transforms.get(orientation, lambda u, v: (u, v))
    first = transform(x, y)
    second = transform(x + width, y + height)
    return Box(x=min(first[0], second[0]), y=min(first[1], second[1]),
               width=abs(first[0] - second[0]), height=abs(first[1] - second[1]))


def background_distance(lab):
    """Estimate a smooth background gradient from all four image edges."""
    height, width = lab.shape[:2]
    xs = np.linspace(-1, 1, width, dtype=np.float32)
    ys = np.linspace(-1, 1, height, dtype=np.float32)
    x = np.concatenate((xs, xs, np.full(height, -1), np.ones(height)))
    y = np.concatenate((np.full(width, -1), np.ones(width), ys, ys))
    samples = np.concatenate((lab[0], lab[-1], lab[:, 0], lab[:, -1]))
    uniform = np.median(samples, axis=0)
    uniform_spread = float(np.percentile(np.linalg.norm(samples - uniform, axis=1), 95))
    if uniform_spread <= 22:
        return np.linalg.norm(lab - uniform, axis=2), uniform_spread

    design = np.column_stack((np.ones_like(x), x, y)).astype(np.float32)
    keep = np.ones(len(samples), dtype=bool)
    for _ in range(3):
        coefficients = np.linalg.lstsq(design[keep], samples[keep], rcond=None)[0]
        residual = np.linalg.norm(samples - design @ coefficients, axis=1)
        keep = residual <= max(6, float(np.percentile(residual, 85)))
    sides = np.split(residual, (width, width * 2, width * 2 + height))
    if any(np.percentile(side, 95) > 22 for side in sides):
        return None, 0
    predicted = (coefficients[0] + xs[None, :, None] * coefficients[1]
                 + ys[:, None, None] * coefficients[2])
    return np.linalg.norm(lab - predicted, axis=2), float(np.percentile(residual, 95))


def analyze(image, orientation, rules, *, detect_candidates=True, save_mask=None,
            detector: CandidateDetector = local_contrast):
    """Evaluate a single piece on a uniform, contrasting matte background."""
    original_width, original_height = image.size
    image.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
    rgb = np.asarray(image)
    height, width = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    quality = Quality(width=original_width, height=original_height)
    if min(original_width, original_height) < rules.minimum_side:
        quality.warnings.append("resolution_below_profile_minimum")
        return quality, None, []

    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    distance, background_spread = background_distance(lab)
    if distance is None:
        quality.warnings.append("background_nonuniform_or_product_clipped")
        return quality, None, []
    foreground = (distance > max(20, 3 * background_spread)).astype(np.uint8)
    element = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    foreground = cv2.morphologyEx(foreground, cv2.MORPH_CLOSE, element)
    contours, _ = cv2.findContours(foreground, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        quality.warnings.append("surface_not_isolated")
        return quality, None, []

    contour = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(contour)
    if (cv2.contourArea(contour) < width * height * rules.minimum_surface_fraction
            or x < 3 or y < 3 or x + w > width - 3 or y + h > height - 3
            or any(other is not contour and cv2.contourArea(other) > 0.12 * cv2.contourArea(contour)
                   for other in contours)):
        quality.warnings.append("surface_not_isolated_or_clipped")
        return quality, None, []

    surface = np.zeros_like(gray)
    cv2.drawContours(surface, [contour], -1, 255, cv2.FILLED)
    inner = cv2.erode(surface, element) != 0
    if not np.any(inner):
        quality.warnings.append("surface_too_narrow")
        return quality, None, []
    if save_mask is not None:
        mask = Image.fromarray(inner)
        undo_orientation = {
            2: Image.Transpose.FLIP_LEFT_RIGHT, 3: Image.Transpose.ROTATE_180, 4: Image.Transpose.FLIP_TOP_BOTTOM,
            5: Image.Transpose.TRANSPOSE, 6: Image.Transpose.ROTATE_90, 7: Image.Transpose.TRANSVERSE,
            8: Image.Transpose.ROTATE_270,
        }
        if orientation in undo_orientation:
            mask = mask.transpose(undo_orientation[orientation])
        save_mask(mask)
    quality.sharpness = round(float(cv2.Laplacian(gray, cv2.CV_32F)[inner].var()), 3)
    quality.dark_fraction = round(float(np.mean(gray[inner] <= 24)), 4)
    quality.glare_fraction = round(float(np.mean(np.min(rgb[inner], axis=1) >= 245)), 4)
    if quality.sharpness < rules.minimum_sharpness:
        quality.warnings.append("low_sharpness_or_low_texture")
    if quality.dark_fraction > rules.maximum_dark_fraction:
        quality.warnings.append("excessive_dark_surface_pixels")
    if quality.glare_fraction > rules.maximum_glare_fraction:
        quality.warnings.append("possible_glare_or_overexposure")
    quality.acceptable = not quality.warnings
    box = original_box(x / width, y / height, w / width, h / height, orientation)
    if not quality.acceptable or not detect_candidates:
        return quality, box, []

    candidates, truncated = detector(lab, surface, inner)
    if truncated:
        quality.warnings.append("candidate_limit_reached")
    boxes = [original_box(cx / width, cy / height, cw / width, ch / height, orientation)
             for cx, cy, cw, ch in candidates]
    return quality, box, boxes
