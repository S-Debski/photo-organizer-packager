import fasteners

def acquire_mutex(name: str) -> bool:
    lock = fasteners.InterProcessLock(f"{name}.lock")
    return lock.acquire(blocking=False)