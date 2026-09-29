import random
import threading
import time

import cv2
import numpy as np
import pyautogui
import pydirectinput

GREEN_LOW = np.array([40, 80, 100], dtype=np.uint8)
GREEN_HIGH = np.array([90, 255, 255], dtype=np.uint8)


class AutoFish:
    def __init__(self, cfg, log=lambda text: None):
        self.cfg = cfg
        self.log = log
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.lock = threading.Lock()
        self.thread = None
        self.started_at = None
        self.finished_at = None
        self.phase = "Arrêté"
        self.stats = {"casts": 0, "minigames": 0, "presses": 0}

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self):
        if self.running:
            return
        self.stop_event.clear()
        self.pause_event.clear()
        with self.lock:
            self.stats = {"casts": 0, "minigames": 0, "presses": 0}
            self.started_at = time.time()
            self.finished_at = None
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop(self, wait=False):
        self.stop_event.set()
        self.pause_event.clear()
        if wait and self.thread:
            self.thread.join(timeout=2)

    def pause(self):
        if self.running:
            self.pause_event.set()
            self.log("En pause.")

    def resume(self):
        if self.running and self.pause_event.is_set():
            self.pause_event.clear()
            self.log("Reprise.")

    def toggle_pause(self):
        if self.pause_event.is_set():
            self.resume()
        else:
            self.pause()

    def snapshot(self):
        with self.lock:
            stats = dict(self.stats)
            end = self.finished_at or time.time()
            elapsed = end - self.started_at if self.started_at else 0.0
        return {
            **stats,
            "running": self.running,
            "paused": self.pause_event.is_set() and self.running,
            "phase": self.phase,
            "elapsed": elapsed,
        }

    def count(self, key, amount=1):
        with self.lock:
            self.stats[key] += amount

    def set_phase(self, text):
        self.phase = text

    def wait_if_paused(self):
        if not self.pause_event.is_set():
            return
        self.set_phase("En pause")
        while self.pause_event.is_set() and not self.stop_event.is_set():
            time.sleep(0.1)

    def capture(self):
        width, height = pyautogui.size()
        sx = width / self.cfg["ref_w"]
        sy = height / self.cfg["ref_h"]
        x, y, w, h = (self.cfg[k] for k in ("roi_x", "roi_y", "roi_w", "roi_h"))
        region = (int(x * sx), int(y * sy), int(w * sx), int(h * sy))
        return cv2.cvtColor(np.array(pyautogui.screenshot(region=region)), cv2.COLOR_RGB2BGR)

    def analyze(self, img):
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        b, g, r = (img[:, :, i].astype(int) for i in range(3))
        blue = (b > 170) & (r < 140) & (g > 110)
        green = cv2.inRange(hsv, GREEN_LOW, GREEN_HIGH) > 0
        visible = blue.mean() + green.mean() >= 0.5
        return visible, green.mean() >= self.cfg["green_min"]

    def cast_line(self):
        key = self.cfg["cast_key"]
        self.set_phase("Lancer de la ligne")
        pydirectinput.keyDown(key)
        try:
            self.stop_event.wait(self.cfg["hold_duration"])
        finally:
            pydirectinput.keyUp(key)
        self.count("casts")

    def wait_for_minigame(self):
        self.set_phase("Attente d'une touche")
        start = time.time()
        while not self.stop_event.is_set() and time.time() - start < self.cfg["bite_timeout"]:
            self.wait_if_paused()
            self.set_phase("Attente d'une touche")
            if self.analyze(self.capture())[0]:
                return True
            time.sleep(0.05)
        return False

    def play_minigame(self):
        self.set_phase("Minijeu en cours")
        self.count("minigames")
        start = time.time()
        absent_since = None
        locked = False
        presses = 0

        while not self.stop_event.is_set() and time.time() - start < self.cfg["minigame_timeout"]:
            self.wait_if_paused()
            self.set_phase("Minijeu en cours")
            visible, green = self.analyze(self.capture())
            now = time.time()

            if not visible:
                absent_since = absent_since or now
                if now - absent_since >= self.cfg["minigame_end_delay"]:
                    break
            else:
                absent_since = None
                if green and not locked:
                    pydirectinput.press(self.cfg["catch_key"])
                    locked = True
                    presses += 1
                    self.count("presses")
                elif not green:
                    locked = False

            time.sleep(self.cfg["scan_interval"])

        self.log(f"Minijeu terminé ({presses} appuis).")

    def run(self):
        self.log("Passe sur le jeu : démarrage dans 5 secondes.")
        self.set_phase("Démarrage dans 5 s")
        try:
            if not self.stop_event.wait(5):
                while not self.stop_event.is_set():
                    self.wait_if_paused()
                    if self.stop_event.is_set():
                        break
                    self.cast_line()
                    if self.wait_for_minigame():
                        self.log("Touche détectée.")
                        self.play_minigame()
                    else:
                        self.log("Aucune touche détectée.")
                    self.set_phase("Pause avant relance")
                    self.stop_event.wait(random.uniform(self.cfg["recast_min"], self.cfg["recast_max"]))
        except Exception as error:
            self.log(f"Erreur : {error}")
        finally:
            with self.lock:
                self.finished_at = time.time()
            self.set_phase("Arrêté")
            self.log("Arrêté.")
