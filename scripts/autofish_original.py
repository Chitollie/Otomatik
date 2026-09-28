import os
import time
import ctypes
import threading
import random
import cv2
import numpy as np
import pyautogui
import pydirectinput

# AutoFish - by Chitollie
#
# How it works:
#   1. Hold E to cast the line
#   2. Wait for the fish minigame bar to appear
#   3. Press SPACE each time green shows up in the bar
#   4. When the bar disappears, go back to step 1

CAST_KEY = "e"
CATCH_KEY = "space"

HOLD_DURATION = 4.0
BITE_TIMEOUT = 120.0
MINIGAME_TIMEOUT = 60.0
MINIGAME_END_DELAY = 0.6            # bar missing this long = minigame over
SCAN_INTERVAL = 0.01
RECAST_DELAY = (0.5, 2.0)

PAUSE_VK = 2
paused = threading.Event()

# Reference resolution and fish bar region (x, y, width, height)
# Inside of the blue bar only, without the rounded edges
REF_W, REF_H = 1920, 1080
ROI_REF = (1082, 245, 40, 592)

# Green range (OpenCV HSV) and minimum share of green pixels needed to press
GREEN_LOW = np.array([40, 80, 100], dtype=np.uint8)
GREEN_HIGH = np.array([90, 255, 255], dtype=np.uint8)
GREEN_MIN = 0.005


def capture():
    sx = pyautogui.size()[0] / REF_W
    sy = pyautogui.size()[1] / REF_H
    x, y, w, h = ROI_REF
    region = (int(x * sx), int(y * sy), int(w * sx), int(h * sy))
    return cv2.cvtColor(np.array(pyautogui.screenshot(region=region)), cv2.COLOR_RGB2BGR)


def analyze(img):
    """Returns (bar_visible, green_present)."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    b, g, r = (img[:, :, i].astype(int) for i in range(3))

    blue = (b > 170) & (r < 140) & (g > 110)
    green = cv2.inRange(hsv, GREEN_LOW, GREEN_HIGH) > 0

    visible = blue.mean() + green.mean() >= 0.5
    return visible, green.mean() >= GREEN_MIN


def watch_pause_key():
    was_down = False
    while True:
        down = bool(ctypes.windll.user32.GetAsyncKeyState(PAUSE_VK) & 0x8000)
        if down and not was_down:
            if paused.is_set():
                paused.clear()
                print("Resumed.")
            else:
                paused.set()
                print("Paused (F8 to resume).")
        was_down = down
        time.sleep(0.05)


def wait_if_paused():
    while paused.is_set():
        time.sleep(0.1)


def cast_line():
    pydirectinput.keyDown(CAST_KEY)
    try:
        time.sleep(HOLD_DURATION)
    finally:
        pydirectinput.keyUp(CAST_KEY)


def wait_for_minigame():
    start = time.time()
    while time.time() - start < BITE_TIMEOUT:
        wait_if_paused()
        if analyze(capture())[0]:
            return True
        time.sleep(0.05)
    return False


def play_minigame():
    start = time.time()
    absent_since = None
    locked = False
    presses = 0

    while time.time() - start < MINIGAME_TIMEOUT:
        wait_if_paused()
        visible, green = analyze(capture())
        now = time.time()

        if not visible:
            absent_since = absent_since or now
            if now - absent_since >= MINIGAME_END_DELAY:
                break
        else:
            absent_since = None

            if green and not locked:
                pydirectinput.press(CATCH_KEY)
                locked = True
                presses += 1
            elif not green:
                locked = False

        time.sleep(SCAN_INTERVAL)

    print(f"Minigame over ({presses} presses)")


def run():
    print("Switch to the game... (5 seconds)  |  F8 = pause/resume  |  Ctrl+C = stop")
    time.sleep(5)

    while True:
        wait_if_paused()
        cast_line()

        if wait_for_minigame():
            play_minigame()

        time.sleep(random.uniform(*RECAST_DELAY))


def ask(label, current, cast):
    value = input(f"{label} [{current}]: ").strip()
    if not value:
        return current
    try:
        return cast(value)
    except ValueError:
        print("Invalid value.")
        return current


def menu():
    global PAUSE_VK, HOLD_DURATION, GREEN_MIN, CAST_KEY, CATCH_KEY

    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print("========== AUTOFISH ==========")
        print("         by Chitollie\n")
        print("[1] Start")
        print(f"[2] Pause/resume key      : {PAUSE_VK}")
        print(f"[3] Hold time for E (s)   : {HOLD_DURATION}")
        print(f"[4] Green sensitivity     : {GREEN_MIN}  (lower = more sensitive)")
        print(f"[5] Cast key              : {CAST_KEY}")
        print(f"[6] Catch key             : {CATCH_KEY}")
        print("[7] Quit")

        choice = input("> ").strip()

        if choice == "1":
            try:
                run()
            except KeyboardInterrupt:
                print("\nStopped.")
                time.sleep(1)
        elif choice == "2":
            PAUSE_VK = ask("Pause/resume key", PAUSE_VK, int)
        elif choice == "3":
            HOLD_DURATION = ask("Hold time", HOLD_DURATION, float)
        elif choice == "4":
            GREEN_MIN = ask("Sensitivity", GREEN_MIN, float)
        elif choice == "5":
            CAST_KEY = ask("Cast key", CAST_KEY, str)
        elif choice == "6":
            CATCH_KEY = ask("Catch key", CATCH_KEY, str)
        elif choice == "7":
            break


if __name__ == "__main__":
    threading.Thread(target=watch_pause_key, daemon=True).start()
    menu()