import os
import time
import fcntl
import struct
import math

# Cau hinh SPI0 va GPIO (DC: 54, RST: 55)
SPI_DEV_PATH = "/dev/spidev0.0"
SPI_SPEED_HZ = 40000000  # 40MHz
PIN_DC = 54
PIN_RST = 55

WIDTH = 320
HEIGHT = 240

SPI_IOC_WR_MODE = 0x40016B01
SPI_IOC_WR_BITS_PER_WORD = 0x40016B03
SPI_IOC_WR_MAX_SPEED_HZ = 0x40046B04


class LinuxGPIO:
    def __init__(self, pin):
        self.pin = pin
        self.path = f"/sys/class/gpio/gpio{pin}"
        if not os.path.exists(self.path):
            with open("/sys/class/gpio/export", "w") as f:
                f.write(str(pin))
        time.sleep(0.05)
        with open(f"{self.path}/direction", "w") as f:
            f.write("out")
        self.fd = os.open(f"{self.path}/value", os.O_WRONLY)

    def write(self, val):
        os.lseek(self.fd, 0, os.SEEK_SET)
        os.write(self.fd, b"1" if val else b"0")


class PureSPI:
    def __init__(self, dev_path, speed_hz=40000000, mode=0):
        self.fd = os.open(dev_path, os.O_RDWR)
        fcntl.ioctl(self.fd, SPI_IOC_WR_MODE, struct.pack("B", mode))
        fcntl.ioctl(self.fd, SPI_IOC_WR_BITS_PER_WORD, struct.pack("B", 8))
        fcntl.ioctl(self.fd, SPI_IOC_WR_MAX_SPEED_HZ, struct.pack("I", speed_hz))

    def write(self, data):
        view = memoryview(data)
        for i in range(0, len(view), 4096):
            os.write(self.fd, view[i:i + 4096])


class ST7789:
    def __init__(self):
        self.dc = LinuxGPIO(PIN_DC)
        self.rst = LinuxGPIO(PIN_RST)
        self.spi = PureSPI(SPI_DEV_PATH, SPI_SPEED_HZ, mode=0)
        self.init_display()

    def cmd(self, c):
        self.dc.write(0)
        self.spi.write(bytes([c]))

    def data(self, d):
        self.dc.write(1)
        if isinstance(d, int):
            self.spi.write(bytes([d]))
        else:
            self.spi.write(d)

    def reset(self):
        self.rst.write(1)
        time.sleep(0.05)
        self.rst.write(0)
        time.sleep(0.05)
        self.rst.write(1)
        time.sleep(0.12)

    def init_display(self):
        self.reset()
        self.cmd(0x01)
        time.sleep(0.15)
        self.cmd(0x11)
        time.sleep(0.12)
        self.cmd(0x3A)
        self.data(0x55)  # RGB565
        self.cmd(0x36)
        self.data(0x60)  # Ngang 320x240 (doi thanh 0xA0 neu bi nguoc dau)
        self.cmd(0x21)   # Display Inversion On
        self.cmd(0x13)
        self.cmd(0x29)
        time.sleep(0.05)

    def set_window(self, x0, y0, x1, y1):
        self.cmd(0x2A)
        self.data(struct.pack(">HH", x0, x1))
        self.cmd(0x2B)
        self.data(struct.pack(">HH", y0, y1))
        self.cmd(0x2C)

    def fill_rect(self, x, y, w, h, color_bytes):
        if w <= 0 or h <= 0:
            return
        self.set_window(x, y, x + w - 1, y + h - 1)
        self.data(color_bytes * (w * h))

    def fill_screen(self, color_bytes):
        self.fill_rect(0, 0, WIDTH, HEIGHT, color_bytes)

    def blit(self, x, y, w, h, buf):
        self.set_window(x, y, x + w - 1, y + h - 1)
        self.data(buf)


def rgb565_bytes(r, g, b):
    val = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return struct.pack(">H", val)


# Bang mau chuan anime
BLACK       = rgb565_bytes(0, 0, 0)
SCLERA_WARM = rgb565_bytes(245, 238, 210)  # Long trang kem (Sharingan)
SCLERA_COOL = rgb565_bytes(242, 244, 248)  # Long trang sang (Mangekyou)
SCLERA_SHAD = rgb565_bytes(165, 162, 168)  # Bong do mi tren
RED         = rgb565_bytes(225, 10, 10)
DARK_RED    = rgb565_bytes(145, 5, 5)
PURPLE      = rgb565_bytes(198, 162, 232)  # Rinnegan tim sang
PURPLE_MID  = rgb565_bytes(158, 120, 198)  # Rinnegan vien ngoai
PURPLE_DARK = rgb565_bytes(95, 65, 130)    # Bong mi Rinnegan
WHITE       = rgb565_bytes(255, 255, 255)

# Kich thuoc khung mat Anime sac lem (2 ben doi xung tren 320x240)
EYE_W = 136
EYE_H = 76
LEFT_X = 14
RIGHT_X = 170
EYE_Y = (HEIGHT - EYE_H) // 2  # 82

BLACK_ROW = BLACK * EYE_W
WORK_L = bytearray(EYE_W * EYE_H * 2)
WORK_R = bytearray(EYE_W * EYE_H * 2)

# Cac muc do mo mi mat (tu khe hep -> mo to)
OPEN_LEVELS = [0.0, 0.08, 0.18, 0.34, 0.54, 0.74, 0.90, 1.0]


def get_eyelid_bounds(x, is_right, openness):
    """Tinh toa do mi tren (y_top) va mi duoi (y_bot) theo dang mat Anime xech"""
    # u = 0.0 (khoe trong gan mui) -> 1.0 (duoi mat ngoai xech len)
    u = (x / (EYE_W - 1)) if is_right else (1.0 - x / (EYE_W - 1))

    # Duong truc giua mat xech len phia ngoai
    y_mid = EYE_H * (0.64 - 0.24 * u)

    # Do cong mi tren sac (dinh lech ve phia trong) va mi duoi mem hon
    s_top = math.sin(math.pi * (u ** 0.78))
    s_bot = math.sin(math.pi * (u ** 0.92))
    top_h = (EYE_H * 0.43) * (s_top ** 0.72) * openness
    bot_h = (EYE_H * 0.34) * (s_bot ** 0.85) * openness

    y_top = int(y_mid - top_h)
    y_bot = int(y_mid + bot_h)
    return max(0, y_top), min(EYE_H - 1, y_bot)


def build_mask_tables():
    """Tinh san khoang [x0, x1] hien thi cua tung dong cho moi muc nham/mo mat"""
    tables = []
    for op in OPEN_LEVELS:
        side_pair = []
        for is_right in (False, True):
            bounds = [get_eyelid_bounds(x, is_right, op) for x in range(EYE_W)]
            rows = []
            for y in range(EYE_H):
                x0 = -1
                x1 = -1
                for x in range(EYE_W):
                    yt, yb = bounds[x]
                    if op > 0.0 and yt <= y <= yb:
                        if x0 == -1:
                            x0 = x
                        x1 = x
                rows.append((x0, x1))
            side_pair.append(rows)
        tables.append(side_pair)
    return tables


MASK_TABLES = build_mask_tables()


# --- HAM VE CO BAN TREN RAM BUFFER ---
def set_px(buf, x, y, color):
    if 0 <= x < EYE_W and 0 <= y < EYE_H:
        idx = (y * EYE_W + x) * 2
        buf[idx] = color[0]
        buf[idx + 1] = color[1]


def draw_circle(buf, cx, cy, r, color):
    r2 = r * r
    for dy in range(-r, r + 1):
        y = cy + dy
        if 0 <= y < EYE_H:
            dx = int(math.sqrt(r2 - dy * dy))
            x0 = max(0, cx - dx)
            x1 = min(EYE_W - 1, cx + dx)
            length = x1 - x0 + 1
            if length > 0:
                start = (y * EYE_W + x0) * 2
                buf[start:start + length * 2] = color * length


def draw_ring(buf, cx, cy, r, thickness, color):
    r_out2 = (r + thickness) ** 2
    r_in2 = max(0, r - thickness) ** 2
    lim = int(math.ceil(r + thickness))
    for dy in range(-lim, lim + 1):
        y = cy + dy
        if 0 <= y < EYE_H:
            dy2 = dy * dy
            for dx in range(-lim, lim + 1):
                d2 = dx * dx + dy2
                if r_in2 <= d2 <= r_out2:
                    set_px(buf, cx + dx, y, color)


def make_sclera_bg(is_right, sclera_color):
    """Tao nen long trang mat + bong do mi tren cho giong anime"""
    buf = bytearray(sclera_color * (EYE_W * EYE_H))
    for x in range(EYE_W):
        yt, _ = get_eyelid_bounds(x, is_right, 1.0)
        for y in range(yt, min(EYE_H, yt + 7)):
            set_px(buf, x, y, SCLERA_SHAD)
    return buf


def iris_center(is_right):
    cx = int(EYE_W * 0.47) if is_right else int(EYE_W * 0.53)
    cy = int(EYE_H * 0.51)
    return cx, cy


# --- 1. SHARINGAN 3 PHAY (TREN LONG TRANG) ---
def render_sharingan(is_right, rot_deg=0):
    buf = make_sclera_bg(is_right, SCLERA_WARM)
    cx, cy = iris_center(is_right)
    r_iris, r_ring = 29, 17

    draw_circle(buf, cx, cy, r_iris + 1, BLACK)
    draw_circle(buf, cx, cy, r_iris, DARK_RED)
    draw_circle(buf, cx, cy, r_iris - 2, RED)
    draw_ring(buf, cx, cy, r_ring, 0.8, BLACK)
    draw_circle(buf, cx, cy, 6, BLACK)

    for base in (90, 210, 330):
        ang = base + rot_deg
        rad = math.radians(ang)
        tx = int(cx + r_ring * math.cos(rad))
        ty = int(cy + r_ring * math.sin(rad))
        draw_circle(buf, tx, ty, 4, BLACK)
        for step in range(1, 12):
            t_rad = math.radians(ang - step * 2.4)
            cr = r_ring + step * 0.08
            ctx = int(cx + cr * math.cos(t_rad))
            cty = int(cy + cr * math.sin(t_rad))
            cs = max(1, int(3 - step * 0.25))
            draw_circle(buf, ctx, cty, cs, BLACK)
    return buf


# --- 2. MANGEKYOU OBITO / KAKASHI (3 CANH CONG NOI VIEN) ---
def render_mangekyou_obito(is_right, rot_deg=0):
    buf = make_sclera_bg(is_right, SCLERA_COOL)
    cx, cy = iris_center(is_right)
    r_iris = 29

    draw_circle(buf, cx, cy, r_iris + 1, BLACK)
    draw_circle(buf, cx, cy, r_iris, RED)

    # 3 canh cong bam sat vien ngoai
    for base in (0, 120, 240):
        for step in range(0, 26):
            ang = math.radians(base + rot_deg + step * 3.1)
            dist = 9 + step * 0.82
            bx = int(cx + dist * math.cos(ang))
            by = int(cy + dist * math.sin(ang))
            thick = max(2, int(6 - step * 0.16))
            draw_circle(buf, bx, by, thick, BLACK)

    draw_ring(buf, cx, cy, r_iris - 1, 1.5, BLACK)
    draw_circle(buf, cx, cy, 8, BLACK)
    draw_circle(buf, cx, cy, 4, RED)
    return buf


# --- 3. MANGEKYOU SASUKE (6 CANH DO TREN NEN DEN) ---
def render_mangekyou_sasuke(is_right, rot_deg=0):
    buf = make_sclera_bg(is_right, SCLERA_COOL)
    cx, cy = iris_center(is_right)
    r_iris = 29
    r2 = r_iris * r_iris

    draw_circle(buf, cx, cy, r_iris + 1, BLACK)
    angles = [math.radians(rot_deg + a) for a in (0, 60, 120)]
    trig = [(math.cos(a), math.sin(a)) for a in angles]
    inv_a2 = 1.0 / (28.0 * 28.0)
    inv_b2 = 1.0 / (9.0 * 9.0)

    for y in range(max(0, cy - r_iris), min(EYE_H, cy + r_iris + 1)):
        dy = y - cy
        dy2 = dy * dy
        for x in range(max(0, cx - r_iris), min(EYE_W, cx + r_iris + 1)):
            dx = x - cx
            if dx * dx + dy2 <= r2:
                for ca, sa in trig:
                    rx = dx * ca + dy * sa
                    ry = -dx * sa + dy * ca
                    if (rx * rx) * inv_a2 + (ry * ry) * inv_b2 <= 1.0:
                        set_px(buf, x, y, RED)
                        break

    draw_circle(buf, cx, cy, 6, BLACK)
    draw_circle(buf, cx, cy, 2, RED)
    return buf


# --- 4. RINNEGAN (PHU TIM KIN HOC MAT, CO TUY CHON 6 PHAY) ---
def render_rinnegan(is_right, with_tomoe=False, rot_deg=0):
    buf = bytearray(PURPLE_MID * (EYE_W * EYE_H))
    cx, cy = iris_center(is_right)

    # Do chuyen mau tim sang o giua -> tim dam o ria
    draw_circle(buf, cx, cy, 52, PURPLE)
    for r in (10, 19, 28, 37, 46, 55):
        draw_ring(buf, cx, cy, r, 1, BLACK)
    draw_circle(buf, cx, cy, 3, BLACK)

    # Rinnegan 6 phay cua Sasuke
    if with_tomoe:
        for r_ring, offset in ((19, 0), (28, 60)):
            for base in (0, 120, 240):
                ang = math.radians(base + offset + rot_deg)
                tx = int(cx + r_ring * math.cos(ang))
                ty = int(cy + r_ring * math.sin(ang))
                draw_circle(buf, tx, ty, 3, BLACK)

    # Bong do mi tren mau tim dam
    for x in range(EYE_W):
        yt, _ = get_eyelid_bounds(x, is_right, 1.0)
        for y in range(yt, min(EYE_H, yt + 6)):
            set_px(buf, x, y, PURPLE_DARK)
    return buf


# --- HIEN THI NHANH BANG BANG TRA MASK (ZERO-FLICKER) ---
def apply_mask_and_blit(lcd, buf_l, buf_r, open_idx):
    row_bytes = EYE_W * 2
    spans_l = MASK_TABLES[open_idx][0]
    spans_r = MASK_TABLES[open_idx][1]

    for y in range(EYE_H):
        dst = y * row_bytes

        # Mat trai
        WORK_L[dst:dst + row_bytes] = BLACK_ROW
        x0, x1 = spans_l[y]
        if x0 != -1:
            s0 = dst + x0 * 2
            s1 = dst + (x1 + 1) * 2
            WORK_L[s0:s1] = buf_l[s0:s1]

        # Mat phai
        WORK_R[dst:dst + row_bytes] = BLACK_ROW
        x0, x1 = spans_r[y]
        if x0 != -1:
            s0 = dst + x0 * 2
            s1 = dst + (x1 + 1) * 2
            WORK_R[s0:s1] = buf_r[s0:s1]

    lcd.blit(LEFT_X, EYE_Y, EYE_W, EYE_H, WORK_L)
    lcd.blit(RIGHT_X, EYE_Y, EYE_W, EYE_H, WORK_R)


def animate_close(lcd, buf_l, buf_r):
    for idx in (6, 4, 2, 1, 0):
        apply_mask_and_blit(lcd, buf_l, buf_r, idx)
        time.sleep(0.018)


def animate_open(lcd, buf_l, buf_r):
    for idx in (1, 2, 3, 4, 5, 6, 7):
        apply_mask_and_blit(lcd, buf_l, buf_r, idx)
        time.sleep(0.022)


def animate_blink(lcd, buf_l, buf_r):
    for idx in (5, 2, 0):
        apply_mask_and_blit(lcd, buf_l, buf_r, idx)
        time.sleep(0.014)
    time.sleep(0.03)
    for idx in (2, 5, 7):
        apply_mask_and_blit(lcd, buf_l, buf_r, idx)
        time.sleep(0.018)


if __name__ == "__main__":
    print("[*] Khoi tao man hinh TFT ST7789 (Anime Sharingan + Rinnegan)...")
    lcd = ST7789()
    lcd.fill_screen(BLACK)

    print("[*] Dang pre-render 4 canh chuan video vao RAM...")
    t0 = time.time()

    # Canh 1: Song Sharingan 3 phay
    s1_l = [render_sharingan(False, d) for d in range(0, 120, 20)]
    s1_r = [render_sharingan(True, -d) for d in range(0, 120, 20)]

    # Canh 2: Trai Mangekyou Obito/Kakashi + Phai Rinnegan
    s2_l = [render_mangekyou_obito(False, d) for d in range(0, 120, 20)]
    s2_r = [render_rinnegan(True, with_tomoe=False)]

    # Canh 3: Trai Mangekyou Sasuke + Phai Rinnegan 6 phay
    s3_l = [render_mangekyou_sasuke(False, d) for d in range(0, 60, 10)]
    s3_r = [render_rinnegan(True, with_tomoe=True, rot_deg=-d) for d in range(0, 120, 20)]

    # Canh 4: Song Rinnegan
    s4_l = [render_rinnegan(False, with_tomoe=False)]
    s4_r = [render_rinnegan(True, with_tomoe=False)]

    print(f"[*] Pre-render xong trong {time.time() - t0:.2f}s! Bat dau trinh dien...")

    scenes = [
        ("Sharingan 3 Phay (Song Mat)",     s1_l, s1_r, 0.06, 26),
        ("Mangekyou Obito + Rinnegan",      s2_l, s2_r, 0.045, 30),
        ("Mangekyou Sasuke + Rinnegan 6P",  s3_l, s3_r, 0.045, 30),
        ("Song Mat Rinnegan",               s4_l, s4_r, 0.12, 18),
    ]

    try:
        while True:
            for name, frames_l, frames_r, delay, loops in scenes:
                print(f"[*] Canh: {name}")
                # Mo mat tu khe hep
                animate_open(lcd, frames_l[0], frames_r[0])

                for i in range(loops):
                    fl = frames_l[i % len(frames_l)]
                    fr = frames_r[i % len(frames_r)]
                    apply_mask_and_blit(lcd, fl, fr, 7)
                    time.sleep(delay)

                    # Chop mat tu nhien giua canh
                    if i == loops // 2:
                        animate_blink(lcd, fl, fr)

                # Khep mat thanh khe hep roi toi han de chuyen sang canh sau
                animate_close(lcd, frames_l[-1], frames_r[-1])
                time.sleep(0.25)

    except KeyboardInterrupt:
        print("\n[*] Da dung chuong trinh.")