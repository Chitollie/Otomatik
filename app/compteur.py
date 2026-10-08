import os
import re
import shutil
import sys
import threading
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import cv2
import numpy as np
import pyautogui

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    import winreg
except ImportError:
    winreg = None

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


def find_tesseract():
    for path in TESSERACT_PATHS:
        if os.path.exists(path):
            return path

    if winreg is not None:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Tesseract-OCR") as key:
                path = os.path.join(winreg.QueryValueEx(key, "InstallDir")[0], "tesseract.exe")
                if os.path.exists(path):
                    return path
        except OSError:
            pass

    return shutil.which("tesseract")


def setup_tesseract():
    if pytesseract is None:
        return None
    path = find_tesseract()
    if path:
        pytesseract.pytesseract.tesseract_cmd = path
    return path


def bundled_tessdata():
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
    folder = base / "tessdata"
    return folder if (folder / "fra.traineddata").exists() else None


def resolve_language(tesseract_path):
    folder = bundled_tessdata()
    if folder is None:
        candidate = Path(tesseract_path).parent / "tessdata"
        if (candidate / "fra.traineddata").exists():
            folder = candidate
    if folder:
        return "fra", str(folder)
    return "eng", None


class Compteur:
    def __init__(self, log=lambda x: None):
        self.log = log
        self.stop_event = threading.Event()
        self.thread = None
        self.lock = threading.Lock()
        self.lang = "eng"
        self.reported_errors = set()
        self.counts = {name: 0 for name in FISH_PRICES}
        self.elapsed = 0.0
        self.started_at = None

    @property
    def running(self):
        return self.started_at is not None

    def start(self):
        if self.thread and self.thread.is_alive():
            if not self.stop_event.is_set():
                return
            self.thread.join(timeout=1)
        if pytesseract is None:
            self.log("Compteur : le module pytesseract est absent de l'application (problème de build de l'EXE).")
            return
        path = setup_tesseract()
        if not path:
            self.log("Tesseract OCR introuvable : installe-le puis relance le compteur.")
            return
        self.lang, tessdata_dir = resolve_language(path)
        if tessdata_dir:
            os.environ["TESSDATA_PREFIX"] = tessdata_dir
        self.log(f"Compteur : Tesseract = {path} | langue = {self.lang} | tessdata = {tessdata_dir or 'défaut'}")
        self.reported_errors.clear()
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
            running = self.started_at is not None
            if running:
                elapsed += time.time() - self.started_at
        total = sum(FISH_PRICES[name] * n for name, n in counts.items())
        per_hour = total / elapsed * 3600 if elapsed > 5 else 0
        return {
            "counts": counts,
            "total": total,
            "per_hour": per_hour,
            "elapsed": elapsed,
            "running": running,
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
                    texts.append(
                        pytesseract.image_to_string(img, lang=self.lang, config="--psm 6")
                    )
                except Exception as error:
                    self.report_error(f"OCR : {error}")
            return "\n".join(texts)
        except Exception as error:
            self.report_error(f"Capture d'écran : {error}")
            return ""

    def report_error(self, message):
        message = " ".join(str(message).split())[:300]
        if message in self.reported_errors or len(self.reported_errors) >= 5:
            return
        self.reported_errors.add(message)
        self.log(f"Compteur : erreur — {message}")

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