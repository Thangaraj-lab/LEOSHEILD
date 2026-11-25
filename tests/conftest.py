from io import BytesIO

import numpy as np
import pytest
from PIL import Image


@pytest.fixture
def synthetic_image():
    """Generate software fixtures with controlled texture and optional marks."""
    def make(mark=False, shade=0, size=640, format="PNG", orientation=None, compress_level=6):
        pixels = np.full((size, size, 3), (205, 207, 209), dtype=np.uint8)
        y, x = np.indices((size, size))
        texture = np.where((x + y) % 2, 4, 0).astype(np.uint8)
        surface = (x > size // 6) & (y > size // 6) & (x < size * 5 // 6) & (y < size * 5 // 6)
        pixels[surface] = np.array([120 + shade, 80 + shade, 58 + shade]) + texture[surface, None]
        if mark:
            pixels[size // 2 - 2:size // 2 + 3, size // 3:size * 2 // 3] = (18, 15, 10)
        buffer = BytesIO()
        image = Image.fromarray(pixels)
        options = {"quality": 100} if format == "JPEG" else {"compress_level": compress_level}
        if orientation is not None:
            exif = image.getexif()
            exif[274] = orientation
            options["exif"] = exif
        image.save(buffer, format=format, **options)
        return buffer.getvalue()

    return make
