import threading, time
import pydirectinput

class AntiAFK:
    def __init__(self, cfg, log=lambda x: None):
        self.cfg, self.log = cfg, log
        self.stop_event = threading.Event()
        self.thread = None
    def start(self):
        if self.thread and self.thread.is_alive(): return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
    def stop(self): self.stop_event.set()
    def run(self):
        self.log('AntiAFK : démarré.')
        while not self.stop_event.is_set():
            pydirectinput.press('s'); time.sleep(.25)
            if self.stop_event.is_set(): break
            pydirectinput.press('z')
            self.log('AntiAFK : S puis Z.')
            if self.stop_event.wait(20*60): break
        self.log('AntiAFK : arrêté.')
