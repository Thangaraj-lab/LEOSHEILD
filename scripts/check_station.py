"""Check camera framing and image quality using a local reference photograph."""

import argparse
import json
from pathlib import Path

from ai_engine.acquisition.image_loader import MAX_IMAGE_BYTES, decode_image
from ai_engine.preprocessing.vision import analyze, load_leather_rules


def assess(path, rules):
    media = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(path.suffix.lower())
    if media is None:
        raise ValueError("Select a JPEG or PNG photograph")
    with path.open("rb") as image_file:
        data = image_file.read(MAX_IMAGE_BYTES + 1)
    image, _, orientation = decode_image(data, media)
    quality, surface, _ = analyze(image, orientation, rules, detect_candidates=False)
    return quality, surface


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("photo", type=Path)
    parser.add_argument("--reference", type=Path, help="Earlier photo of the same reference in the same position")
    args = parser.parse_args()
    rules = load_leather_rules()
    try:
        quality, surface = assess(args.photo, rules)
        drift = None
        if args.reference:
            earlier, reference_box = assess(args.reference, rules)
            if earlier.acceptable and quality.acceptable and reference_box and surface:
                drift = max(abs(getattr(surface, name) - getattr(reference_box, name))
                            for name in ("x", "y", "width", "height"))
        print(json.dumps({"calibration_status": "uncalibrated", "quality": quality.model_dump(),
                          "surface": surface.model_dump() if surface else None,
                          "max_reference_framing_change": drift,
                          "reference_framing_within_tolerance": drift <= 0.035 if drift is not None else None},
                         indent=2))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
