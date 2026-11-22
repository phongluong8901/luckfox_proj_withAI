import os
import time
import fcntl
import struct
import math

SPI_DEV_PATH = "/dev/spidev0.0"
SPI_SPEED_HZ = 40000000
PIN_DC = 54
PIN_RST = 55

WIDTH = 320
HEIGHT = 240

SPI_IOC_WR_MODE = 0x40016B01
SPI_IOC_WR_BITS_PER_WORD = 0x40016B03
SPI_IOC_WR_MAX_SPEED_HZ = 0x40046B04

# Font bitmap 5x7 day du so, chu in hoa va ky tu co ban
FONT_5X7 = {
    '0': [0x3E, 0x51, 0x49, 0x45, 0x3E],
    '1': [0x00, 0x42, 0x7F, 0x40, 0x00],
    '2': [0x42, 0x61, 0x51, 0x49, 0x46],
    '3': [0x21, 0x41, 0x45, 0x4B, 0x31],
    '4': [0x18, 0x14, 0x12, 0x7F, 0x10],
    '5': [0x27, 0x45, 0x45, 0x45, 0x39],
    '6': [0x3C, 0x4A, 0x49, 0x49, 0x30],
    '7': [0x01, 0x71, 0x09, 0x05, 0x03],
    '8': [0x36, 0x49, 0x49, 0x49, 0x36],
    '9': [0x06, 0x49, 0x49, 0x29, 0x1E],
    ':': [0x00, 0x36, 0x36, 0x00, 0x00],
    '-': [0x08, 0x08, 0x08, 0x08, 0x08],
    '/': [0x20, 0x10, 0x08, 0x04, 0x02],
    '.': [0x00, 0x60, 0x60, 0x00, 0x00],
    ' ': [0x00, 0x00, 0x00, 0x00, 0x00],
    'A': [0x7E, 0x11, 0x11, 0x11, 0x7E],
    'B': [0x7F, 0x49, 0x49, 0x49, 0x36],
    'C': [0x3E, 0x41, 0x41, 0x41, 0x22],
    'D': [0x7F, 0x41, 0x41, 0x22, 0x1C],
    'E': [0x7F, 0x49, 0x49, 0x49, 0x41],
    'F': [0x7F, 0x09, 0x09, 0x09, 0x01],
    'G': [0x3E, 0x41, 0x49, 0x49, 0x7A],
    'H': [0x7F, 0x08, 0x08, 0x08, 0x7F],
    'I': [0x00, 0x41, 0x7F, 0x41, 0x00],
    'J': [0x20, 0x40, 0x41, 0x3F, 0x01],
    'K': [0x7F, 0x08, 0x14, 0x22, 0x41],
    'L': [0x7F, 0x40, 0x40, 0x40, 0x40],
    'M': [0x7F, 0x02, 0x0C, 0x02, 0x7F],
    'N': [0x7F, 0x04, 0x08, 0x10, 0x7F],
    'O': [0x3E, 0x41, 0x41, 0x41, 0x3E],
    'P': [0x7F, 0x09, 0x09, 0x09, 0x06],
    'Q': [0x3E, 0x41, 0x51, 0x21, 0x5E],
    'R': [0x7F, 0x09, 0x19, 0x29, 0x46],
    'S': [0x46, 0x49, 0x49, 0x49, 0x31],
    'T': [0x01, 0x01, 0x7F, 0x01, 0x01],
    'U': [0x3F, 0x40, 0x40, 0x40, 0x3F],
    'V': [0x1F, 0x20, 0x40, 0x20, 0x1F],
    'W': [0x3F, 0x40, 0x38, 0x40, 0x3F],
    'X': [0x63, 0x14, 0x08, 0x14, 0x63],
    'Y': [0x07, 0x08, 0x70, 0x08, 0x07],
    'Z': [0x61, 0x51, 0x49, 0x45, 0x43],
}


def rgb565_bytes(r, g, b):
    val = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return struct.pack(">H", val)


BLACK = rgb565_bytes(0, 0, 0)
WHITE = rgb565_bytes(255, 255, 255)


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
        self.data(0x55)
        self.cmd(0x36)
        self.data(0x60)  # Ngang 320x240 (doi 0xA0 neu nguoc)
        self.cmd(0x21)
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

    def draw_text(self, x, y, text, color_bytes, bg_bytes=BLACK, scale=2):
        char_w = 6 * scale
        char_h = 7 * scale
        total_w = len(text) * char_w
        buf = bytearray(bg_bytes * (total_w * char_h))
        for idx, ch in enumerate(text.upper()):
            cols = FONT_5X7.get(ch, FONT_5X7[' '])
            ox = idx * char_w
            for cx_i, col_bits in enumerate(cols):
                for cy_i in range(7):
                    if (col_bits >> cy_i) & 1:
                        for sy in range(scale):
                            py = cy_i * scale + sy
                            row_off = py * total_w
                            for sx in range(scale):
                                px = ox + cx_i * scale + sx
                                pos = (row_off + px) * 2
                                buf[pos] = color_bytes[0]
                                buf[pos + 1] = color_bytes[1]
        self.blit(x, y, total_w, char_h, buf)


def set_px(buf, bw, bh, x, y, color):
    if 0 <= x < bw and 0 <= y < bh:
        idx = (y * bw + x) * 2
        buf[idx] = color[0]
        buf[idx + 1] = color[1]


def draw_circle(buf, bw, bh, cx, cy, r, color):
    r2 = r * r
    for dy in range(-r, r + 1):
        y = cy + dy
        if 0 <= y < bh:
            dx = int(math.sqrt(r2 - dy * dy))
            x0 = max(0, cx - dx)
            x1 = min(bw - 1, cx + dx)
            length = x1 - x0 + 1
            if length > 0:
                start = (y * bw + x0) * 2
                buf[start:start + length * 2] = color * length


def draw_ring(buf, bw, bh, cx, cy, r, thickness, color):
    r_out = r + thickness * 0.5
    r_in = max(0.0, r - thickness * 0.5)
    r_out2 = r_out * r_out
    r_in2 = r_in * r_in
    lim = int(math.ceil(r_out))
    for dy in range(-lim, lim + 1):
        y = cy + dy
        if 0 <= y < bh:
            dy2 = dy * dy
            if dy2 > r_out2:
                continue
            dx_out = int(math.sqrt(r_out2 - dy2))
            if dy2 < r_in2:
                dx_in = int(math.sqrt(r_in2 - dy2))
                # Left span
                x0 = max(0, cx - dx_out)
                x1 = min(bw - 1, cx - dx_in)
                if x1 >= x0:
                    s = (y * bw + x0) * 2
                    buf[s:s + (x1 - x0 + 1) * 2] = color * (x1 - x0 + 1)
                # Right span
                x0 = max(0, cx + dx_in)
                x1 = min(bw - 1, cx + dx_out)
                if x1 >= x0:
                    s = (y * bw + x0) * 2
                    buf[s:s + (x1 - x0 + 1) * 2] = color * (x1 - x0 + 1)
            else:
                x0 = max(0, cx - dx_out)
                x1 = min(bw - 1, cx + dx_out)
                if x1 >= x0:
                    s = (y * bw + x0) * 2
                    buf[s:s + (x1 - x0 + 1) * 2] = color * (x1 - x0 + 1)


def fill_span(buf, bw, bh, y, x0, x1, color):
    if 0 <= y < bh:
        xa = max(0, x0)
        xb = min(bw - 1, x1)
        if xb >= xa:
            s = (y * bw + xa) * 2
            buf[s:s + (xb - xa + 1) * 2] = color * (xb - xa + 1)


def draw_rounded_rect(buf, bw, bh, x, y, w, h, r, color):
    r = max(0, min(r, w // 2, h // 2))
    r2 = r * r
    for row in range(h):
        py = y + row
        if py < 0 or py >= bh:
            continue
        if row < r:
            dy = r - row
            inset = r - int(math.sqrt(max(0, r2 - dy * dy)))
        elif row >= h - r:
            dy = row - (h - r - 1)
            inset = r - int(math.sqrt(max(0, r2 - dy * dy)))
        else:
            inset = 0
        fill_span(buf, bw, bh, py, x + inset, x + w - 1 - inset, color)


def draw_ellipse(buf, bw, bh, cx, cy, rx, ry, color):
    if rx <= 0 or ry <= 0:
        return
    ry2 = float(ry * ry)
    for dy in range(-ry, ry + 1):
        y = cy + dy
        if 0 <= y < bh:
            dx = int(rx * math.sqrt(max(0.0, 1.0 - (dy * dy) / ry2)))
            fill_span(buf, bw, bh, y, cx - dx, cx + dx, color)


def draw_capsule_h(buf, bw, bh, cx, cy, half_w, half_h, color):
    r = max(1, half_h)
    rect_hw = max(0, half_w - r)
    r2 = r * r
    for dy in range(-r, r + 1):
        y = cy + dy
        if 0 <= y < bh:
            dx = rect_hw + int(math.sqrt(max(0, r2 - dy * dy)))
            fill_span(buf, bw, bh, y, cx - dx, cx + dx, color)


def draw_arc_thick(buf, bw, bh, cx, cy, r, start_deg, end_deg, thickness, color):
    rad_thick = max(1, thickness // 2)
    step = max(2, int(90 / max(1, r)))
    deg = start_deg
    while deg <= end_deg:
        rad = math.radians(deg)
        px = int(cx + r * math.cos(rad))
        py = int(cy + r * math.sin(rad))
        draw_circle(buf, bw, bh, px, py, rad_thick, color)
        deg += step


def draw_tomoe(buf, bw, bh, cx, cy, orbit_r, ang_deg, head_r, color):
    """Ve 1 phay Sharingan (dau tron + duoi cong om theo vong tron)"""
    rad = math.radians(ang_deg)
    hx = int(cx + orbit_r * math.cos(rad))
    hy = int(cy + orbit_r * math.sin(rad))
    draw_circle(buf, bw, bh, hx, hy, head_r, color)
    for step in range(1, 6):
        tail_ang = math.radians(ang_deg - step * 6.5)
        tail_r_orbit = orbit_r + step * 0.45
        tx = int(cx + tail_r_orbit * math.cos(tail_ang))
        ty = int(cy + tail_r_orbit * math.sin(tail_ang))
        tr = max(1, int(head_r * (1.0 - step * 0.16)))
        draw_circle(buf, bw, bh, tx, ty, tr, color)


def draw_line_thick(buf, bw, bh, x0, y0, x1, y1, radius, color):
    dx = x1 - x0
    dy = y1 - y0
    steps = max(1, int(math.hypot(dx, dy) / max(1, radius * 0.6)))
    for i in range(steps + 1):
        t = i / steps
        draw_circle(buf, bw, bh, int(x0 + dx * t), int(y0 + dy * t), radius, color)


def draw_vertical_slit(buf, bw, bh, cx, cy, half_w, half_h, color):
    """Dong tu xe doc nhon 2 dau (mat Cuu Vi Kurama)"""
    if half_h <= 0:
        return
    for dy in range(-half_h, half_h + 1):
        y = cy + dy
        if 0 <= y < bh:
            ratio = 1.0 - abs(dy) / float(half_h)
            w = int(half_w * (ratio ** 0.65))
            fill_span(buf, bw, bh, y, cx - w, cx + w, color)


def draw_heart(buf, bw, bh, cx, cy, size, color):
    """Ve trai tim phat sang cho bieu cam Love"""
    r = int(size * 0.34)
    offset_x = int(size * 0.30)
    top_y = cy - int(size * 0.14)
    draw_circle(buf, bw, bh, cx - offset_x, top_y, r, color)
    draw_circle(buf, bw, bh, cx + offset_x, top_y, r, color)
    # Phan tam giac duoi trai tim
    y_start = top_y + int(r * 0.25)
    y_end = cy + int(size * 0.62)
    span_top = offset_x + r - 1
    total_h = max(1, y_end - y_start)
    for y in range(y_start, y_end + 1):
        t = (y - y_start) / float(total_h)
        hw = int(span_top * (1.0 - t))
        fill_span(buf, bw, bh, y, cx - hw, cx + hw, color)


def dim_rgb565_buf(src_buf, brightness_pct):
    """Giam do sang buffer RGB565 (brightness_pct: 30..100)"""
    if brightness_pct >= 98:
        return src_buf
    factor = max(0.25, min(1.0, brightness_pct / 100.0))
    # Cache bang tra nhanh cho tung muc sang (toi uu tren ARM)
    out = bytearray(len(src_buf))
    f_int = int(factor * 256)
    mv_in = memoryview(src_buf)
    for i in range(0, len(src_buf), 2):
        hi = mv_in[i]
        lo = mv_in[i + 1]
        if hi == 0 and lo == 0:
            continue
        val = (hi << 8) | lo
        r = (((val >> 11) & 0x1F) * f_int) >> 8
        g = (((val >> 5) & 0x3F) * f_int) >> 8
        b = ((val & 0x1F) * f_int) >> 8
        nv = (r << 11) | (g << 5) | b
        out[i] = nv >> 8
        out[i + 1] = nv & 0xFF
    return out

