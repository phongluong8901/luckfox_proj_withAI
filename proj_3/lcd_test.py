import os
import time
import fcntl
import struct

# Cau hinh chan ket noi SPI0 va GPIO (DC: GPIO1_C6_d = 54, RST: GPIO1_C7_d = 55)
SPI_DEV_PATH = "/dev/spidev0.0"
SPI_SPEED_HZ = 40000000  # 40MHz
PIN_DC = 54
PIN_RST = 55

WIDTH = 240
HEIGHT = 320

# Hang so ioctl chuan cua Linux spidev
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

    def write(self, val):
        with open(f"{self.path}/value", "w") as f:
            f.write("1" if val else "0")


class PureSPI:
    def __init__(self, dev_path, speed_hz=40000000, mode=0):
        self.fd = os.open(dev_path, os.O_RDWR)
        fcntl.ioctl(self.fd, SPI_IOC_WR_MODE, struct.pack("B", mode))
        fcntl.ioctl(self.fd, SPI_IOC_WR_BITS_PER_WORD, struct.pack("B", 8))
        fcntl.ioctl(self.fd, SPI_IOC_WR_MAX_SPEED_HZ, struct.pack("I", speed_hz))

    def write(self, data):
        # Chia nho goi 4096 bytes theo gioi han buffer cua Linux spidev
        for i in range(0, len(data), 4096):
            os.write(self.fd, data[i:i + 4096])


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
        self.cmd(0x01)  # Software Reset
        time.sleep(0.15)
        self.cmd(0x11)  # Sleep Out
        time.sleep(0.12)

        self.cmd(0x3A)  # 16-bit/pixel (RGB565)
        self.data(0x55)

        self.cmd(0x36)  # Huong xoay man hinh (0x00: Doc 240x320)
        self.data(0x00)

        self.cmd(0x21)  # Display Inversion On (doi thanh 0x20 neu bi nguoc mau)
        self.cmd(0x13)  # Normal Display Mode On
        self.cmd(0x29)  # Display On
        time.sleep(0.05)

    def set_window(self, x0, y0, x1, y1):
        self.cmd(0x2A)
        self.data(struct.pack(">HH", x0, x1))
        self.cmd(0x2B)
        self.data(struct.pack(">HH", y0, y1))
        self.cmd(0x2C)

    def fill_rect(self, x, y, w, h, color_rgb565):
        self.set_window(x, y, x + w - 1, y + h - 1)
        pixel_bytes = struct.pack(">H", color_rgb565) * (w * h)
        self.data(pixel_bytes)

    def fill_screen(self, color_rgb565):
        self.fill_rect(0, 0, WIDTH, HEIGHT, color_rgb565)


def rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


if __name__ == "__main__":
    print("[*] Dang khoi tao man hinh TFT 2 inch ST7789 (Pure SPI)...")
    lcd = ST7789()

    BLACK = rgb565(0, 0, 0)
    CYAN  = rgb565(0, 220, 255)
    BLUE  = rgb565(20, 80, 200)

    print("[*] Xoa nen den & ve mat robot...")
    lcd.fill_screen(BLACK)

    lcd.fill_rect(45, 90, 50, 70, CYAN)
    lcd.fill_rect(145, 90, 50, 70, CYAN)
    lcd.fill_rect(70, 210, 100, 15, BLUE)

    for _ in range(5):
        time.sleep(1.5)
        lcd.fill_rect(45, 90, 50, 70, BLACK)
        lcd.fill_rect(145, 90, 50, 70, BLACK)
        lcd.fill_rect(45, 120, 50, 10, CYAN)
        lcd.fill_rect(145, 120, 50, 10, CYAN)
        time.sleep(0.15)
        lcd.fill_rect(45, 90, 50, 70, CYAN)
        lcd.fill_rect(145, 90, 50, 70, CYAN)

    print("[*] Test thanh cong!")