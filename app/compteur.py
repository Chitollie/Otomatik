import os
import re
import threading
import time
import unicodedata
from difflib import SequenceMatcher

import cv2
import numpy as np
import pyautogui

try:
    import pytesseract
except ImportError:
    pytesseract = None

REF_W, REF_H = 1920, 1080
NOTIFICATION_ROI = (1300, 0, 620, 180)
OCR_INTERVAL = 0.20
CONFIRM_FRAMES = 2
ABSENCE_FRAMES = 3

FISH_PRICES = {
    "Filet de poissons": 1000,
    "Maquereau": 1300,
    "Dorade": 2200,
    "Bar": 1700,
    "Thon": 3000,
    "Espadon": 4000,
}

EXACT_PATTERNS = [
    (r"\bfilet de poissons?\b", "Filet de poissons"),
    (r"\bmaquereau\b", "Maquereau"),
    (r"\bdorade\b", "Dorade"),
    (r"\bbar\b", "Bar"),
    (r"\bthon\b", "Thon"),
    (r"\bespadon\b", "Espadon"),
]

FUZZY_TARGETS = [
    ("maquereau", "Maquereau"),
    ("dorade", "Dorade"),
    ("espadon", "Espadon"),
]

TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


def normalize_text(text):
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def find_fish(text):
    t = normalize_text(text)

    for pattern, fish in EXACT_PATTERNS:
        if re.search(pattern, t):
            return fish

    for word in re.findall(r"[a-z]+", t):
        for target, fish in FUZZY_TARGETS:
            if len(word) >= 5 and SequenceMatcher(None, word, target).ratio() >= 0.8:
                return fish

    if "filet" in t and "poisson" in t:
        return "Filet de poissons"

    return None


def format_money(value):
    return f"{int(value):,}".replace(",", " ") + " $"


def setup_tesseract():
    if pytesseract is None:
        return False

    for path in TESSERACT_PATHS:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            return True

    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


class Compteur:
    def __init__(self, log=lambda x: None):
        self.log = log
        self.stop_event = threading.Event()
        self.thread = None
        self.lock = threading.Lock()
        self.lang = "eng"
        self.counts = {name: 0 for name in FISH_PRICES}
        self.elapsed = 0.0
        self.started_at = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        if not setup_tesseract():
            self.log("Compteur : Tesseract OCR introuvable (pip install pytesseract + installer Tesseract).")
            return
        try:
            self.lang = "fra" if "fra" in pytesseract.get_languages(config="") else "eng"
        except Exception:
            self.lang = "eng"
        self.stop_event.clear()
        with self.lock:
            self.started_at = time.time()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        with self.lock:
            if self.started_at is not None:
                self.elapsed += time.time() - self.started_at
                self.started_at = None

    def reset(self):
        with self.lock:
            self.counts = {name: 0 for name in FISH_PRICES}
            self.elapsed = 0.0
            if self.started_at is not None:
                self.started_at = time.time()
        self.log("Compteur : remis à zéro.")

    def snapshot(self):
        with self.lock:
            counts = dict(self.counts)
            elapsed = self.elapsed
            if self.started_at is not None:
                elapsed += time.time() - self.started_at
        total = sum(FISH_PRICES[name] * n for name, n in counts.items())
        per_hour = total / elapsed * 3600 if elapsed > 5 else 0
        return {
            "counts": counts,
            "total": total,
            "per_hour": per_hour,
            "elapsed": elapsed,
            "running": self.started_at is not None,
        }

    def capture(self):
        width, height = pyautogui.size()
        sx, sy = width / REF_W, height / REF_H
        x, y, w, h = NOTIFICATION_ROI
        region = (int(x * sx), int(y * sy), int(w * sx), int(h * sy))
        return cv2.cvtColor(np.array(pyautogui.screenshot(region=region)), cv2.COLOR_RGB2BGR)

    def read_notification(self):
        try:
            gray = cv2.cvtColor(self.capture(), cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
            _, threshold = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)
            texts = []
            for img in (gray, threshold):
                try:
                    texts.append(pytesseract.image_to_string(img, lang=self.lang, config="--psm 6"))
                except Exception:
                    pass
            return "\n".join(texts)
        except Exception:
            return ""

    def run(self):
        self.log("Compteur : démarré.")
        candidate = None
        candidate_frames = 0
        counted_fish = None
        absence_frames = 0

        while not self.stop_event.is_set():
            fish = find_fish(self.read_notification())

            if fish is None:
                absence_frames += 1
                candidate = None
                candidate_frames = 0
                if absence_frames >= ABSENCE_FRAMES:
                    counted_fish = None
            else:
                absence_frames = 0
                if fish == candidate:
                    candidate_frames += 1
                else:
                    candidate = fish
                    candidate_frames = 1

                if candidate_frames >= CONFIRM_FRAMES and fish != counted_fish:
                    with self.lock:
                        self.counts[fish] += 1
                    counted_fish = fish
                    self.log(f"Compteur : {fish} +{format_money(FISH_PRICES[fish])}")

            time.sleep(OCR_INTERVAL)

        self.log("Compteur : arrêté.")
