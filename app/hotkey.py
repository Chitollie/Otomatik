import ctypes
import threading


def vk_from_name(name):
    name = str(name).strip().lower()
    if name.startswith("f") and name[1:].isdigit() and 1 <= int(name[1:]) <= 24:
        return 0x70 + int(name[1:]) - 1
    if len(name) == 1 and name.isalnum():
        return ord(name.upper())
    return None


class HotkeyWatcher:
    def __init__(self, get_key, on_press):
        self.get_key = get_key
        self.on_press = on_press
        self.stop_event = threading.Event()

    def start(self):
        user32 = getattr(getattr(ctypes, "windll", None), "user32", None)
        if user32 is None:
            return False
        threading.Thread(target=self.run, args=(user32,), daemon=True).start()
        return True

    def stop(self):
        self.stop_event.set()

    def run(self, user32):
        was_down = False
        while not self.stop_event.wait(0.05):
            vk = vk_from_name(self.get_key())
            down = bool(vk) and bool(user32.GetAsyncKeyState(vk) & 0x8000)
            if down and not was_down:
                self.on_press()
            was_down = down
