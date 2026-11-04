# Role: Background job and thread coordination (see Stability Contract)

import threading

class ThreadManager:
    def __init__(self, context):
        self.context = context
        self.threads = []

    def start(self, name, target, *args):
        t = threading.Thread(
            target=target,
            name=name,
            args=(self.context, *args),
            daemon=True
        )
        t.start()
        self.threads.append(t)
        print(f"[ThreadManager] Started thread: {name}")
        return t
