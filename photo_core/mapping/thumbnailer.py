# Role: Application module (see Stability Contract)

# photo_core/mapping/thumbnailing.py
# Mapping: image thumbnail generation
# Read-only image transformation

from PIL import Image
import io


def generate_thumbnail(image_path, size=(256, 256), format="JPEG"):
    """
    Generate a thumbnail for an image.

    Returns:
        bytes: encoded thumbnail image
    """
    with Image.open(image_path) as im:
        im = im.convert("RGB")
        im.thumbnail(size, Image.LANCZOS)

        buf = io.BytesIO()
        im.save(buf, format=format, quality=85)
        return buf.getvalue()
