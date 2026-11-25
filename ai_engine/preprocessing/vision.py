import cv2
import numpy as np
import yaml
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai_engine import ROOT
from ai_engine.api.schemas import Box, Quality, View


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


def analyze(image, orientation, rules):
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
    border = np.concatenate((lab[0], lab[-1], lab[:, 0], lab[:, -1]))
    background = np.median(border, axis=0)
    border_distance = np.linalg.norm(border - background, axis=1)
    background_spread = float(np.percentile(border_distance, 95))
    if background_spread > 22:
        quality.warnings.append("background_nonuniform_or_product_clipped")
        return quality, None, []
    distance = np.linalg.norm(lab - background, axis=2)
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
    if not quality.acceptable:
        return quality, box, []

    weights = (surface != 0).astype(np.float32)
    local_weight = cv2.GaussianBlur(weights, (0, 0), 7)
    local_sum = cv2.GaussianBlur(lab * weights[:, :, None], (0, 0), 7)
    local_reference = local_sum / np.maximum(local_weight[:, :, None], 1e-6)
    contrast = np.max(np.abs(lab - local_reference), axis=2)
    marked = ((contrast >= 24) & inner).astype(np.uint8)
    marked = cv2.morphologyEx(marked, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(marked)
    candidates = [row for row in stats[1:count] if row[4] >= 14 and max(row[2:4]) >= 8]
    candidates.sort(key=lambda row: -int(row[4]))
    if len(candidates) > 40:
        quality.warnings.append("candidate_limit_reached")
    boxes = [original_box(cx / width, cy / height, cw / width, ch / height, orientation)
             for cx, cy, cw, ch, _ in candidates[:40]]
    return quality, box, boxes
