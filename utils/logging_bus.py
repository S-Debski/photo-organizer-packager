# utils/logging_bus.py
import time

def log_info(ctx, msg: str):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        ctx.log_queue.put_nowait(line)
    except Exception:
        pass