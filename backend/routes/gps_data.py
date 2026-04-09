# backend/routes/gps_data.py

def api_gps_data(ctx):
    """
    Return GPS points for the currently active folder
    using cached EXIF data only.
    NEVER touches the filesystem.
    """

    folder = ctx.state.get("current_active_folder")
    if not folder:
        return []

    # Cache GPS per folder so this is O(1) after first build
    cache_key = f"gps::{folder}"

    if cache_key in ctx.state:
        return ctx.state[cache_key]

    gps_points = []

    # exif_scanner_worker should already have populated this
    exif_key = f"exif_stats::{folder}"
    exif_data = ctx.exif_cache.get(exif_key)

    if not exif_data:
        # EXIF not ready yet — do NOT block
        return []

    # ✅ Example structure — adapt if your cache names differ
    for item in exif_data.get("items", []):
        lat = item.get("lat")
        lon = item.get("lon")

        if lat is not None and lon is not None:
            gps_points.append({
                "lat": lat,
                "lon": lon,
                "filename": item.get("filename", "")
            })

    # Store GPS cache
    ctx.state[cache_key] = gps_points
    return gps_points