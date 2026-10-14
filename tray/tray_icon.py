# Role: Application module (see Stability Contract)

# tray/tray_icon.py
# -----------------------------------------------------------------------------
# System tray (Windows) / menu bar (macOS) icon for desktop builds.
#
# The app's UI is a browser page, so without this a windowed build has no
# visible presence and no way to quit. Must run on the main thread
# (required by macOS).
# -----------------------------------------------------------------------------

from PIL import Image
import pystray


def run_tray(ctx, icon_path, on_open, title="Photo Organizer"):
    """Show the tray icon and block until the user chooses Quit."""

    def open_item(icon, item):
        on_open()

    def quit_item(icon, item):
        ctx.shutdown_event.set()
        icon.stop()

    icon = pystray.Icon(
        "PhotoOrganizer",
        Image.open(icon_path),
        title,
        menu=pystray.Menu(
            pystray.MenuItem("Open Photo Organizer", open_item, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", quit_item),
        ),
    )

    icon.run()
