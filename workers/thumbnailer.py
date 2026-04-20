def thumbnail_worker(ctx):
    while not ctx.shutdown_event.is_set():
        # generate thumbnails on demand
        pass