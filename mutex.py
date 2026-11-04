# Role: Cross-process and critical-section locking (see Stability Contract)

import fasteners


def acquire_mutex(name: str) -> bool:
    lock = fasteners.InterProcessLock(f"{name}.lock")
    return lock.acquire(blocking=False)
