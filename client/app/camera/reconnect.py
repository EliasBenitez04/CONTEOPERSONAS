import time


class ReconnectManager:

    def __init__(self, delay_seconds=3):

        self.delay_seconds = delay_seconds

        self.attempts = 0

    def wait(self):

        self.attempts += 1

        print(
            f"[RECONNECT] Intento #{self.attempts}. "
            f"Esperando {self.delay_seconds}s..."
        )

        time.sleep(
            self.delay_seconds
        )

    def reset(self):

        self.attempts = 0