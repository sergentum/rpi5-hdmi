import subprocess
import time
import sys
import logging
import select
import os
import re
import threading

from evdev import InputDevice, list_devices, ecodes, categorize

# ---------------- CONFIG ----------------

INPUT_POLL_INTERVAL = 0.1

INPUT_TIMEOUT = 900

COOLDOWN = 2
DEVICE_REFRESH_INTERVAL = 5

COMBOS = {
    frozenset(["BTN_START", "BTN_SOUTH"]): "start",
    frozenset(["BTN_START", "BTN_EAST"]): "stop",
}

# ----------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

log = logging.getLogger()

# ---------------- SHARED STATE (NO LOCKS) ----------------

last_input_time = time.time()
last_trigger_time = 0
moonlight_active = False

pressed = set()
devices = []

# ---------------- CEC ----------------

def start():
    run_moonlight()
    tv_on()
    log.info("STARTED")

def stop():
    kill_moonlight()
    tv_off()
    log.info("STOPPED")

def auto_stop():
    kill_moonlight()
    log.info("AUTO STOPPED")


def tv_on():
    subprocess.run('echo "on 0" | cec-client -s -d 1', shell=True)
    time.sleep(1)
    subprocess.run('echo "as" | cec-client -s -d 1', shell=True)

def tv_off():
    subprocess.run('echo "standby 0" | cec-client -s -d 1', shell=True)


def is_moonlight_running():
    global moonlight_active
    result = subprocess.run(
        "pgrep -x moonlight-qt",
        shell=True,
        stdout=subprocess.DEVNULL
    )
    moonlight_active = result.returncode == 0
    return moonlight_active

def run_moonlight():
    global moonlight_active
    if is_moonlight_running():
        log.info("Moonlight already running")
        return

    cmd = [
        "/usr/bin/moonlight-qt",
        "stream",
        "pc",
        "desktop"
    ]

    env = dict(os.environ)
    env["DISPLAY"] = ":0"
    env["XAUTHORITY"] = "/home/a/.Xauthority"

    log.info(f"Launching Moonlight: {cmd}")

    try:
        subprocess.Popen(cmd, env=env)
        moonlight_active = True
    except Exception as e:
        log.error(f"Failed to launch Moonlight: {e}")

def kill_moonlight():
    import subprocess
    import logging
    global moonlight_active

    log = logging.getLogger()

    try:
        # try graceful kill
        subprocess.run(["pkill", "-x", "moonlight-qt"], check=False)

        # check if still running
        result = subprocess.run(
            ["pgrep", "-x", "moonlight-qt"],
            stdout=subprocess.DEVNULL
        )

        if result.returncode == 0:
            log.warning("Moonlight still running → force kill")
            subprocess.run(["pkill", "-9", "-x", "moonlight-qt"], check=False)

        log.info("Moonlight terminated")
        moonlight_active = False
    except Exception as e:
        log.error(f"Kill failed: {e}")


ACTIONS = {
    "start": start,
    "stop": stop,
}

# ---------------- INPUT DEVICES ----------------

def refresh_devices():
    devs = []
    for path in list_devices():
        try:
            devs.append(InputDevice(path))
        except:
            pass
    return devs

devices = refresh_devices()


# ---------------- INPUT THREAD ----------------

def input_thread():
    global last_input_time, last_trigger_time, devices

    last_refresh = 0

    while True:
        try:
            now = time.time()

            # refresh devices
            if now - last_refresh > DEVICE_REFRESH_INTERVAL:
                devices = refresh_devices()
                pressed.clear()
                last_refresh = now

            if not devices:
                time.sleep(1)
                continue

            r, _, _ = select.select(devices, [], [], INPUT_POLL_INTERVAL)

            for dev in r:
                for event in dev.read():

                    if event.type != ecodes.EV_KEY:
                        continue

                    key_event = categorize(event)
                    keys = key_event.keycode

                    if isinstance(keys, str):
                        keys = [keys]

                    for key in keys:
                        if not key.startswith("BTN_"):
                            continue

                        if key_event.keystate == key_event.key_down:
                            # log.info(f"DOWN: {key}")
                            pressed.add(key)
                            last_input_time = now

                            if now - last_trigger_time < COOLDOWN:
                                continue

                            for combo, action in COMBOS.items():
                                if combo.issubset(pressed):
                                    log.info(f"COMBO -> {action}")
                                    ACTIONS[action]()
                                    last_trigger_time = now
                                    break

                        elif key_event.keystate == key_event.key_up:
                            pressed.discard(key)

        except Exception as e:
            log.error(f"INPUT thread error: {e}")
            time.sleep(1)


# ---------------- AUTO STOP THREAD ----------------

def auto_stop_thread():
    global last_input_time
    global moonlight_active
    input_idle = 0

    while True:
        try:
            now = time.time()
            input_idle = (now - last_input_time)
            log.info(f"Input is idle for: {input_idle}")
            if moonlight_active and input_idle > INPUT_TIMEOUT:
                log.info("AUTO STOP")
                auto_stop()

        except Exception as e:
            log.error(f"LOGIC thread error: {e}")

        time.sleep(10)


# ---------------- MAIN ----------------

if __name__ == "__main__":

    threading.Thread(target=input_thread, daemon=True).start()
    threading.Thread(target=auto_stop_thread, daemon=True).start()
    is_moonlight_running()

    while True:
        time.sleep(10)
