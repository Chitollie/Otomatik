import threading
import time

import pydirectinput


class AntiAFK:
    def __init__(self, cfg, log=lambda text: None):
        self.cfg = cfg
        self.log = log
        self.stop_event = threading.Event()
        self.thread = None
        self.cycles = 0
        self.next_at = None

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self):
        if self.running:
            return
        self.stop_event.clear()
        self.cycles = 0
        self.next_at = time.time() + 5
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def snapshot(self):
        left = max(0.0, self.next_at - time.time()) if self.running and self.next_at else None
        return {
            "running": self.running,
            "cycles": self.cycles,
            "seconds_left": left,
            "interval_minutes": self.cfg["afk_minutes"],
        }

    def run(self):
        self.log("Démarré : première action dans 5 secondes.")
        try:
            if self.stop_event.wait(5):
                return
            while True:
                pydirectinput.press("s")
                if self.stop_event.wait(0.25):
                    break
                pydirectinput.press("z")
                self.cycles += 1
                self.log("S puis Z envoyés.")
                self.next_at = time.time() + self.cfg["afk_minutes"] * 60
                if self.stop_event.wait(self.cfg["afk_minutes"] * 60):
                    break
        except Exception as error:
            self.log(f"Erreur : {error}")
        finally:
            self.next_at = None
            self.log("Arrêté.")
