from tft_driver import ST7789
from robot_engine import load_config
from face_uchiha import UchihaWatchFace
from face_senju import SenjuWatchFace
from face_extra import KuramaWatchFace, ByakuganWatchFace
from wifi_manager import connect_wifi
from web_server import start_web_server


def main():
    ip = connect_wifi()
    print(f"[*] Mo trinh duyet truy cap: http://{ip}:8080")

    state = load_config()
    state.update({
        "blink": False,
        "powerup": False,
        "gaze_manual": False,
        "gaze_x": 0,
        "gaze_y": 0,
    })
    start_web_server(state, port=8080)

    print("[*] Dang khoi tao man hinh TFT ST7789 & dung khung hinh Robot Naruto...")
    lcd = ST7789()

    faces = {
        "uchiha": UchihaWatchFace(),
        "senju": SenjuWatchFace(),
        "kurama": KuramaWatchFace(),
        "byakugan": ByakuganWatchFace(),
    }

    active_mode = None
    try:
        while True:
            target_mode = state["mode"]
            if target_mode not in faces:
                target_mode = "uchiha"
            if target_mode != active_mode:
                active_mode = target_mode
                faces[active_mode].on_enter(lcd, state)
            faces[active_mode].update(lcd, state)
    except KeyboardInterrupt:
        print("\n[*] Da dung chuong trinh.")


if __name__ == "__main__":
    main()
