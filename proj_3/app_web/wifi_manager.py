import os
import time
import socket
import subprocess

WIFI_SSID = "Gosu"
WIFI_PASS = "123456789"
WPA_CONF  = "/tmp/wpa_watch.conf"


def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "0.0.0.0"


def connect_wifi():
    ip = get_ip_address()
    if ip != "0.0.0.0":
        print(f"[WiFi] Da ket noi san. IP: {ip}")
        return ip

    print(f"[WiFi] Dang ket noi toi mang '{WIFI_SSID}'...")
    conf = (
        "ctrl_interface=/var/run/wpa_supplicant\n"
        "update_config=1\n"
        "network={\n"
        f'    ssid="{WIFI_SSID}"\n'
        f'    psk="{WIFI_PASS}"\n'
        "}\n"
    )
    with open(WPA_CONF, "w") as f:
        f.write(conf)

    subprocess.run("killall wpa_supplicant udhcpc 2>/dev/null || true", shell=True)
    subprocess.run("ifconfig wlan0 up 2>/dev/null || true", shell=True)
    subprocess.run(f"wpa_supplicant -B -i wlan0 -c {WPA_CONF}", shell=True)
    subprocess.run("udhcpc -i wlan0 -n -q 2>/dev/null || true", shell=True)

    for _ in range(15):
        ip = get_ip_address()
        if ip != "0.0.0.0":
            print(f"[WiFi] Ket noi thanh cong! IP: {ip}")
            return ip
        time.sleep(1)

    print("[WiFi] Khong lay duoc IP wlan0 (van chay tiep voi mang hien tai).")
    return get_ip_address()