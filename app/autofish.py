import time, random, threading, cv2, numpy as np, pyautogui, pydirectinput
class AutoFish:
    def __init__(self,cfg,log=lambda x:None): self.cfg,self.log=cfg,log; self.stop_event=threading.Event(); self.pause_event=threading.Event(); self.thread=None
    def start(self):
        if self.thread and self.thread.is_alive(): return
        self.stop_event.clear(); self.pause_event.clear(); self.thread=threading.Thread(target=self.run,daemon=True); self.thread.start()
    def stop(self): self.stop_event.set(); self.pause_event.clear()
    def pause(self): self.pause_event.set()
    def resume(self): self.pause_event.clear()
    def wait(self):
        while self.pause_event.is_set() and not self.stop_event.is_set(): time.sleep(.1)
    def capture(self):
        sx=pyautogui.size()[0]/self.cfg['ref_w']; sy=pyautogui.size()[1]/self.cfg['ref_h']; x,y,w,h=[self.cfg[k] for k in ('roi_x','roi_y','roi_w','roi_h')]; r=(int(x*sx),int(y*sy),int(w*sx),int(h*sy)); return cv2.cvtColor(np.array(pyautogui.screenshot(region=r)),cv2.COLOR_RGB2BGR)
    def analyze(self,img):
        hsv=cv2.cvtColor(img,cv2.COLOR_BGR2HSV); b,g,r=(img[:,:,i].astype(int) for i in range(3)); blue=(b>170)&(r<140)&(g>110); green=cv2.inRange(hsv,np.array([40,80,100],np.uint8),np.array([90,255,255],np.uint8))>0; return blue.mean()+green.mean()>=.5,green.mean()>=self.cfg['green_min']
    def run(self):
        self.log('AutoFish : démarrage dans 5 secondes.'); time.sleep(5)
        while not self.stop_event.is_set():
            self.wait(); pydirectinput.keyDown(self.cfg['cast_key']); time.sleep(self.cfg['hold_duration']); pydirectinput.keyUp(self.cfg['cast_key'])
            start=time.time()
            while not self.stop_event.is_set() and time.time()-start<self.cfg['bite_timeout']:
                self.wait()
                if self.analyze(self.capture())[0]: break
                time.sleep(.05)
            start=time.time(); absent=None; locked=False
            while not self.stop_event.is_set() and time.time()-start<self.cfg['minigame_timeout']:
                self.wait(); visible,green=self.analyze(self.capture()); now=time.time()
                if not visible:
                    absent=absent or now
                    if now-absent>=self.cfg['minigame_end_delay']: break
                else:
                    absent=None
                    if green and not locked: pydirectinput.press(self.cfg['catch_key']); locked=True
                    elif not green: locked=False
                time.sleep(self.cfg['scan_interval'])
            time.sleep(random.uniform(self.cfg['recast_min'],self.cfg['recast_max']))
        self.log('AutoFish : arrêté.')
