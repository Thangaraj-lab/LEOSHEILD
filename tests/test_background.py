from io import BytesIO

import numpy as np
from PIL import Image

from ai_engine.preprocessing.vision import analyze, load_leather_rules


def test_smooth_background_gradient_preserves_surface_and_candidate(synthetic_image):
    with Image.open(BytesIO(synthetic_image(mark=True))) as source:
        pixels = np.array(source, dtype=np.int16)
    gradient = np.linspace(-32, 32, pixels.shape[1], dtype=np.int16)
    image = Image.fromarray(np.clip(pixels + gradient[None, :, None], 0, 255).astype(np.uint8))
    quality, surface, candidates = analyze(image, 1, load_leather_rules())
    assert quality.acceptable and surface is not None
    assert 0.14 < surface.x < 0.19
    assert any(0.25 < box.x < 0.45 for box in candidates)


def test_piece_touching_frame_still_fails_capture(synthetic_image):
    with Image.open(BytesIO(synthetic_image())) as source:
        image = source.crop((0, 0, source.width, 530))
    quality, surface, candidates = analyze(image, 1, load_leather_rules())
    assert not quality.acceptable
    assert surface is None and candidates == []
