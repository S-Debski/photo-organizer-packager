from PIL import Image
import pystray

def run_tray(ctx):
    def on_quit(icon, item):
        ctx.shutdown_event.set()
        icon.stop()

    image = Image.open("assets/icon.png")

    icon = pystray.Icon(
        "PhotoWizard",
        image,
        "Photo Wizard",
        menu=pystray.Menu(
            pystray.MenuItem("Quit", on_quit)
        )
    )

    icon.run_detached()