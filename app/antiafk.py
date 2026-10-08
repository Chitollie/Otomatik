import ctypes
import threading
import time
from ctypes import wintypes

import pydirectinput

KEY_LEFT = "q"
KEY_RIGHT = "d"
HOLD_SECONDS = 0.35
GAP_SECONDS = 0.15

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
MAPVK_VK_TO_VSC = 0


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class INPUT(ctypes.Structure):
    class _Union(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _Union)]


def user32():
    return getattr(getattr(ctypes, "windll", None), "user32", None)


def scan_code(char):
    """Code physique de la touche qui porte cette lettre sur TON clavier (AZERTY ou QWERTY)."""
    api = user32()
    if api is None:
        return None
    vk = api.VkKeyScanW(ord(char)) & 0xFF
    if vk == 0xFF:
        return None
    return api.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC) or None


def send_scan(scan, up=False):
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0)
    event = INPUT(type=INPUT_KEYBOARD)
    event.ki = KEYBDINPUT(0, scan, flags, 0, 0)
    if user32().SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) != 1:
        raise OSError("SendInput a été refusé par Windows (le jeu tourne-t-il en administrateur ?)")


def hold_key(key, seconds, stop_event):
    """Maintient la touche `seconds` secondes. Renvoie True si on a demandé l'arrêt."""
    scan = scan_code(key)
    if scan:
        press = lambda: send_scan(scan)
        release = lambda: send_scan(scan, up=True)
    else:
        press = lambda: pydirectinput.keyDown(key)
        release = lambda: pydirectinput.keyUp(key)

    press()
    try:
        return stop_event.wait(seconds)
    finally:
        release()


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
        left, right = KEY_LEFT.upper(), KEY_RIGHT.upper()
        self.log("Démarré : première action dans 5 secondes (le jeu doit être au premier plan).")
        try:
            if self.stop_event.wait(5):
                return
            while True:
                if hold_key(KEY_LEFT, HOLD_SECONDS, self.stop_event):
                    break
                if self.stop_event.wait(GAP_SECONDS):
                    break
                if hold_key(KEY_RIGHT, HOLD_SECONDS, self.stop_event):
                    break
                self.cycles += 1
                self.log(f"{left} puis {right} envoyés.")
                self.next_at = time.time() + self.cfg["afk_minutes"] * 60
                if self.stop_event.wait(self.cfg["afk_minutes"] * 60):
                    break
        except Exception as error:
            self.log(f"Erreur : {error}")
        finally:
            self.next_at = None
            self.log("Arrêté.")