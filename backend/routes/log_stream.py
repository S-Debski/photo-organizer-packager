import time

def api_log_stream(ctx):
    def gen():
        # ✅ MUST BE BYTES
        yield b"data: Connected to log stream\n\n"

        while not ctx.shutdown_event.is_set():
            try:
                line = ctx.log_queue.get(timeout=0.5)
                # ✅ ALWAYS ENCODE
                yield f"data: {line}\n\n".encode("utf-8")
            except Exception:
                yield b"data: \n\n"
                time.sleep(0.5)

    return gen()