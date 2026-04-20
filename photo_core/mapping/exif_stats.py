# Mapping: EXIF statistics analysis
# Read-only analysis
# Informational outputs only
# No Flask, no ctx, no caching

from photo_core.mapping.exif_dates import (
    extract_exif_datetime,
    extract_camera_model,
    extract_lens_model,
)
from photo_core.mapping.quality_classification import extract_exif_gps


def compute_exif_stats(image_paths):
    """
    Compute camera and lens usage statistics for a set of image paths.

    Returns:
        {
            "cameras": [{"model": str, "count": int}, ...],
            "lenses": [{"lens": str, "count": int}, ...],
        }
    """
    camera_counter = {}
    lens_counter = {}

    for img in image_paths:
        # Mapping signals (date/GPS extracted but not interpreted here)
        extract_exif_datetime(img)
        extract_exif_gps(img)

        cam = extract_camera_model(img) or "Unknown"
        lens = extract_lens_model(img) or "Unknown Lens"

        camera_counter[cam] = camera_counter.get(cam, 0) + 1
        lens_counter[lens] = lens_counter.get(lens, 0) + 1

    return {
        "cameras": [{"model": k, "count": v} for k, v in camera_counter.items()],
        "lenses": [{"lens": k, "count": v} for k, v in lens_counter.items()],
    }
