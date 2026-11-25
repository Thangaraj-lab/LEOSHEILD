from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 24_000_000
MEDIA_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png"}


def decode_image(data, declared_type):
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Image exceeds 10 MiB")
    try:
        with Image.open(BytesIO(data), formats=list(MEDIA_TYPES)) as source:
            media_type = MEDIA_TYPES[source.format]
            if declared_type != media_type:
                raise ValueError("Declared media type does not match the image")
            if source.width * source.height > MAX_PIXELS or getattr(source, "n_frames", 1) != 1:
                raise ValueError("Expected a single image of at most 24 megapixels")
            orientation = source.getexif().get(274, 1)
            clean = ImageOps.exif_transpose(source).convert("RGB")
            return clean, media_type, orientation
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError("Unable to decode JPEG or PNG") from exc
