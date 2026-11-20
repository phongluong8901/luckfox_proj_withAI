import glob
import os
import shutil
import socket
import subprocess
import time

RTSP_PORT = 554


def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "192.168.1.9"


def check_port(host, port):
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except Exception:
        return False


def is_rkipc_running():
    res = subprocess.run(["pidof", "rkipc"], capture_output=True, text=True)
    return res.returncode == 0 and res.stdout.strip() != ""


def find_rkipc_starter():
    candidates = [
        "/oem/usr/bin/RkLunch.sh",
        "/usr/bin/RkLunch.sh",
        "/oem/usr/bin/rkipc",
        "/usr/bin/rkipc",
    ]
    for path in candidates:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path
    return shutil.which("rkipc")


def print_sensor_info():
    # Kiem tra cam bien trong i2c sysfs va dmesg
    found = []
    for name_file in sorted(glob.glob("/sys/bus/i2c/devices/*/name")):
        try:
            with open(name_file, "r") as f:
                name = f.read().strip()
            if any(k in name.lower() for k in ("sc33", "imx", "gc20", "ov", "sensor")):
                dev = os.path.basename(os.path.dirname(name_file))
                found.append(f"{dev}: {name}")
        except Exception:
            pass
    if found:
        print(f"[OK] Sensor I2C phat hien: {', '.join(found)}")
    else:
        print("[!] Khong thay ten sensor (sc33xx/imx...) trong /sys/bus/i2c/devices.")

    dmesg = subprocess.run(
        "dmesg | grep -iE 'sc33|sensor|csi|vicap|rkisp' | tail -n 15",
        shell=True,
        capture_output=True,
        text=True,
    )
    if dmesg.stdout.strip():
        print("--- dmesg camera ---")
        print(dmesg.stdout.strip())
        print("--------------------")

    if shutil.which("i2cdetect"):
        i2c = subprocess.run("i2cdetect -y 4", shell=True, capture_output=True, text=True)
        if i2c.stdout.strip():
            print("--- i2cdetect -y 4 ---")
            print(i2c.stdout.strip())
            print("----------------------")

    iq_files = sorted(
        glob.glob("/oem/usr/share/iqfiles/*.json")
        + glob.glob("/etc/iqfiles/*.json")
    )
    if iq_files:
        names = [os.path.basename(p) for p in iq_files]
        print(f"[i] IQ files tren mach: {', '.join(names[:8])}")


print("=== Kiem tra & Bat Stream Camera tren Luckfox Pico Zero ===")

# 1. Kiem tra cac node /dev/video*
video_nodes = sorted(glob.glob("/dev/video*"))
if not video_nodes:
    print("[X] Khong tim thay /dev/video*! Hay kiem tra lai cap CSI.")
    raise SystemExit(1)

print(f"[OK] Phat hien {len(video_nodes)} video nodes (co /dev/video11 rkisp_mainpath).")
print_sensor_info()

# 2. Dam bao rkipc dang chay de stream RTSP
if is_rkipc_running():
    print("[OK] rkipc dang chay san.")
else:
    starter = find_rkipc_starter()
    if not starter:
        print("[X] Khong tim thay rkipc hoac RkLunch.sh tren mach.")
        raise SystemExit(1)

    print(f"[...] Dang khoi dong camera stream bang: {starter}")
    log_file = open("/tmp/rkipc.log", "w")
    subprocess.Popen(
        [starter],
        stdin=subprocess.DEVNULL,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    for _ in range(16):
        time.sleep(0.5)
        if is_rkipc_running() and check_port("127.0.0.1", RTSP_PORT):
            break

    if not is_rkipc_running() and starter.endswith("RkLunch.sh"):
        rkipc_bin = shutil.which("rkipc") or (
            "/oem/usr/bin/rkipc" if os.path.exists("/oem/usr/bin/rkipc") else None
        )
        if rkipc_bin:
            print(f"[...] RkLunch.sh chua bat rkipc, thu chay truc tiep: {rkipc_bin}")
            subprocess.Popen(
                [rkipc_bin],
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            for _ in range(10):
                time.sleep(0.5)
                if is_rkipc_running() and check_port("127.0.0.1", RTSP_PORT):
                    break

    if is_rkipc_running():
        print("[OK] rkipc da khoi dong thanh cong!")
    else:
        print("[X] Khoi dong rkipc that bai. Noi dung /tmp/rkipc.log:")
        try:
            with open("/tmp/rkipc.log", "r") as f:
                print(f.read().strip() or "(log rong)")
        except Exception as e:
            print(f"Khong doc duoc log: {e}")
        raise SystemExit(1)

# 3. Kiem tra cong RTSP 554
ip = get_ip_address()
if check_port("127.0.0.1", RTSP_PORT):
    print(f"[OK] Cong RTSP ({RTSP_PORT}) dang mo!")
else:
    print(f"[!] rkipc dang chay nhung cong RTSP ({RTSP_PORT}) chua san sang.")

print("")
print("==========================================================")
print("  CACH XEM CAMERA TREN MAY TINH:")
print(f"  - Mo VLC -> Media -> Open Network Stream (Ctrl+N):")
print(f"    rtsp://{ip}/live/0")
print(f"  - Hoac dung ffplay:")
print(f"    ffplay -fflags nobuffer rtsp://{ip}/live/0")
print("==========================================================")
