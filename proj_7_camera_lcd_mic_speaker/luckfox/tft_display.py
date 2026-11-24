import math
import os
import struct
import time
import unicodedata

try:
  import fcntl
except ImportError:
  fcntl = None

try:
  import spidev
except ImportError:
  spidev = None

_VALID_ROTATIONS = {0: 0x00, 90: 0x60, 180: 0xC0, 270: 0xA0}
_ROT_RAW = int(os.environ.get("TFT_ROTATION", "90"))
TFT_ROTATION = _ROT_RAW if _ROT_RAW in _VALID_ROTATIONS else 90

_DEF_W, _DEF_H = (320, 240) if TFT_ROTATION in (90, 270) else (240, 320)
TFT_W = int(os.environ.get("TFT_W", str(_DEF_W)))
TFT_H = int(os.environ.get("TFT_H", str(_DEF_H)))
TFT_FPS = float(os.environ.get("TFT_FPS", "10.0"))
TFT_BG_PATH = os.environ.get("TFT_RGB565_PATH", "/dev/shm/tft_bg.rgb565")
EMOJI_AUTO_CYCLE = os.environ.get("EMOJI_AUTO_CYCLE", "1") == "1"

SPI_BUS = int(os.environ.get("TFT_SPI_BUS", "0"))
SPI_DEV = int(os.environ.get("TFT_SPI_DEV", "0"))
SPI_HZ = int(os.environ.get("TFT_SPI_HZ", "40000000"))

DC_PIN = int(os.environ.get("TFT_DC_PIN", "54"))
RST_PIN = int(os.environ.get("TFT_RST_PIN", "55"))
BL_PIN = int(os.environ.get("TFT_BL_PIN", "-1"))

_SPI_IOC_WR_MODE = 0x40016B01
_SPI_IOC_WR_BITS_PER_WORD = 0x40016B03
_SPI_IOC_WR_MAX_SPEED_HZ = 0x40046B04

_FONT_5X7 = {
    " ": (0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00),
    "!": (0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x04),
    "#": (0x0A, 0x0A, 0x1F, 0x0A, 0x1F, 0x0A, 0x0A),
    "%": (0x18, 0x19, 0x02, 0x04, 0x08, 0x13, 0x03),
    "'": (0x04, 0x04, 0x08, 0x00, 0x00, 0x00, 0x00),
    "(": (0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02),
    ")": (0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08),
    "*": (0x00, 0x0A, 0x04, 0x1F, 0x04, 0x0A, 0x00),
    "+": (0x00, 0x04, 0x04, 0x1F, 0x04, 0x04, 0x00),
    ",": (0x00, 0x00, 0x00, 0x00, 0x04, 0x04, 0x08),
    "-": (0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00),
    ".": (0x00, 0x00, 0x00, 0x00, 0x00, 0x06, 0x06),
    "/": (0x01, 0x02, 0x02, 0x04, 0x08, 0x08, 0x10),
    ":": (0x00, 0x06, 0x06, 0x00, 0x06, 0x06, 0x00),
    "=": (0x00, 0x00, 0x1F, 0x00, 0x1F, 0x00, 0x00),
    "?": (0x0E, 0x11, 0x01, 0x02, 0x04, 0x00, 0x04),
    "0": (0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E),
    "1": (0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "2": (0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F),
    "3": (0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E),
    "4": (0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02),
    "5": (0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E),
    "6": (0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E),
    "7": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08),
    "8": (0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E),
    "9": (0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C),
    "A": (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "B": (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    "C": (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E),
    "D": (0x1C, 0x12, 0x11, 0x11, 0x11, 0x12, 0x1C),
    "E": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F),
    "F": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10),
    "G": (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F),
    "H": (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "I": (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "J": (0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C),
    "K": (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11),
    "L": (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    "M": (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11),
    "N": (0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11),
    "O": (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "P": (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    "Q": (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D),
    "R": (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    "S": (0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E),
    "T": (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    "U": (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "V": (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    "W": (0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11),
    "X": (0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11),
    "Y": (0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04),
    "Z": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F),
}

_IDLE_SCENES = ("idle", "curious", "happy", "fly", "drunk", "love", "cool", "sleep")


def _vn_to_ascii(text: str) -> str:
  if not text:
    return ""
  s = text.replace("đ", "d").replace("Đ", "D")
  s = unicodedata.normalize("NFD", s)
  return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


def _wrap_ascii(text: str, max_chars: int, max_lines: int = 3) -> list[str]:
  words = _vn_to_ascii(text).upper().split()
  if not words:
    return []
  lines: list[str] = []
  cur = ""
  for w in words:
    if not cur:
      cur = w[:max_chars]
    elif len(cur) + 1 + len(w) <= max_chars:
      cur += " " + w
    else:
      lines.append(cur)
      if len(lines) >= max_lines:
        return lines
      cur = w[:max_chars]
  if cur and len(lines) < max_lines:
    lines.append(cur)
  return lines


class _RawSpiDev:
  def __init__(self):
    self.fd: int | None = None
    self._mode = 0
    self._max_speed_hz = SPI_HZ

  def open(self, bus: int, dev: int):
    if fcntl is None:
      raise OSError("fcntl is unavailable on this OS")
    path = f"/dev/spidev{bus}.{dev}"
    self.fd = os.open(path, os.O_RDWR)
    fcntl.ioctl(self.fd, _SPI_IOC_WR_BITS_PER_WORD, struct.pack("B", 8))
    self.mode = self._mode
    self.max_speed_hz = self._max_speed_hz

  @property
  def mode(self) -> int:
    return self._mode

  @mode.setter
  def mode(self, val: int):
    self._mode = int(val) & 0xFF
    if self.fd is not None and fcntl is not None:
      fcntl.ioctl(self.fd, _SPI_IOC_WR_MODE, struct.pack("B", self._mode))

  @property
  def max_speed_hz(self) -> int:
    return self._max_speed_hz

  @max_speed_hz.setter
  def max_speed_hz(self, hz: int):
    self._max_speed_hz = int(hz)
    if self.fd is not None and fcntl is not None:
      fcntl.ioctl(
          self.fd, _SPI_IOC_WR_MAX_SPEED_HZ, struct.pack("I", self._max_speed_hz)
      )

  def writebytes(self, seq):
    if self.fd is not None:
      os.write(self.fd, bytes(seq))

  def writebytes2(self, buf):
    if self.fd is not None:
      os.write(self.fd, bytes(buf))

  def close(self):
    if self.fd is not None:
      try:
        os.close(self.fd)
      except OSError:
        pass
      self.fd = None


def _rgb565(r: int, g: int, b: int) -> int:
  return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def _export_gpio(pin: int):
  if pin < 0:
    return None
  p = f"/sys/class/gpio/gpio{pin}"
  if not os.path.exists(p):
    try:
      with open("/sys/class/gpio/export", "w", encoding="utf-8") as f:
        f.write(str(pin))
      time.sleep(0.05)
    except OSError:
      return None
  val_path = os.path.join(p, "value")
  dir_path = os.path.join(p, "direction")
  try:
    with open(dir_path, "w", encoding="utf-8") as f:
      f.write("out")
  except OSError:
    pass
  return val_path if os.path.exists(val_path) else None


def _write_gpio(val_path: str | None, v: int):
  if not val_path:
    return
  try:
    with open(val_path, "w", encoding="utf-8") as f:
      f.write("1" if v else "0")
  except OSError:
    pass


class ST7789Display:
  def __init__(
      self,
      width: int = TFT_W,
      height: int = TFT_H,
      rotation: int = TFT_ROTATION,
  ):
    self.w = width
    self.h = height
    self.rotation = rotation if rotation in _VALID_ROTATIONS else 90
    self.spi = None
    self.dc_path = _export_gpio(DC_PIN)
    self.rst_path = _export_gpio(RST_PIN)
    self.bl_path = _export_gpio(BL_PIN)
    self._bg_565 = 0x0000
    self._bg_buf = bytes([0x00, 0x00]) * (self.w * self.h)
    self.fb = bytearray(self._bg_buf)

  def open(self) -> bool:
    if not self.dc_path and os.path.exists(f"/dev/spidev{SPI_BUS}.{SPI_DEV}"):
      print(
          f"[TFT WARN] Khong export duoc GPIO DC={DC_PIN} (hay chay voi quyen root).",
          flush=True,
      )
    try:
      s = spidev.SpiDev() if spidev is not None else _RawSpiDev()
      s.open(SPI_BUS, SPI_DEV)
      s.max_speed_hz = SPI_HZ
      s.mode = 0
      self.spi = s
      _write_gpio(self.bl_path, 1)
      self._reset()
      self._init_cmds()
      self.fb[:] = self._bg_buf
      self.flush()
      backend = "spidev" if spidev is not None else "raw-ioctl"
      print(
          f"[TFT] ST7789 init OK ({backend}) /dev/spidev{SPI_BUS}.{SPI_DEV} "
          f"({self.w}x{self.h}, rot={self.rotation}, DC={DC_PIN}, RST={RST_PIN})",
          flush=True,
      )
      return True
    except OSError as e:
      print(f"[TFT] Khong mo duoc SPI ({e}), bo qua hien thi TFT.", flush=True)
      self.spi = None
      return False

  def _cmd(self, c: int, data: bytes = b""):
    if not self.spi:
      return
    _write_gpio(self.dc_path, 0)
    self.spi.writebytes([c])
    if data:
      _write_gpio(self.dc_path, 1)
      self.spi.writebytes2(data)

  def _reset(self):
    if not self.rst_path:
      return
    _write_gpio(self.rst_path, 0)
    time.sleep(0.05)
    _write_gpio(self.rst_path, 1)
    time.sleep(0.12)

  def _init_cmds(self):
    madctl = _VALID_ROTATIONS.get(self.rotation, 0x60)
    self._cmd(0x01)
    time.sleep(0.12)
    self._cmd(0x11)
    time.sleep(0.12)
    self._cmd(0x3A, b"\x55")
    self._cmd(0x36, bytes([madctl]))
    self._cmd(0x21)
    self._cmd(0x13)
    self._cmd(0x29)
    time.sleep(0.05)

  def fill_rect(self, x: int, y: int, w: int, h: int, color565: int):
    x0 = max(0, int(x))
    y0 = max(0, int(y))
    x1 = min(self.w, int(x + w))
    y1 = min(self.h, int(y + h))
    if x1 <= x0 or y1 <= y0:
      return
    hi = (color565 >> 8) & 0xFF
    lo = color565 & 0xFF
    span = bytes([hi, lo]) * (x1 - x0)
    row_bytes = self.w * 2
    for yy in range(y0, y1):
      off = yy * row_bytes + x0 * 2
      self.fb[off : off + len(span)] = span

  def fill_circle(self, cx: int, cy: int, r: int, color565: int):
    if r <= 0:
      return
    r2 = r * r
    for dy in range(-r, r + 1):
      dx = int(math.sqrt(max(0, r2 - dy * dy)))
      self.fill_rect(cx - dx, cy + dy, dx * 2 + 1, 1, color565)

  def fill_round_rect(self, x: int, y: int, w: int, h: int, r: int, color565: int):
    r = max(0, min(int(r), int(w) // 2, int(h) // 2))
    w = int(w)
    h = int(h)
    x = int(x)
    y = int(y)
    if w <= 0 or h <= 0:
      return
    if r == 0:
      self.fill_rect(x, y, w, h, color565)
      return
    self.fill_rect(x + r, y, w - 2 * r, h, color565)
    self.fill_rect(x, y + r, w, h - 2 * r, color565)
    for cx, cy in (
        (x + r, y + r),
        (x + w - r - 1, y + r),
        (x + r, y + h - r - 1),
        (x + w - r - 1, y + h - r - 1),
    ):
      self.fill_circle(cx, cy, r, color565)

  def draw_rect_border(
      self, x1: int, y1: int, x2: int, y2: int, color565: int, thick: int = 2
  ):
    w = max(1, x2 - x1)
    h = max(1, y2 - y1)
    self.fill_rect(x1, y1, w, thick, color565)
    self.fill_rect(x1, y2 - thick, w, thick, color565)
    self.fill_rect(x1, y1, thick, h, color565)
    self.fill_rect(x2 - thick, y1, thick, h, color565)

  def draw_text(
      self, x: int, y: int, text: str, color565: int, scale: int = 1
  ):
    scale = max(1, int(scale))
    hi = (color565 >> 8) & 0xFF
    lo = color565 & 0xFF
    pix = bytes([hi, lo]) * scale
    row_bytes = self.w * 2
    cx = int(x)
    cy = int(y)
    step = 6 * scale

    for ch in _vn_to_ascii(text).upper():
      if cx + 5 * scale > self.w:
        break
      glyph = _FONT_5X7.get(ch, _FONT_5X7[" "])
      if cx >= 0:
        for r_idx, row_bits in enumerate(glyph):
          yy0 = cy + r_idx * scale
          for c_idx in range(5):
            if (row_bits >> (4 - c_idx)) & 1:
              xx0 = cx + c_idx * scale
              for sy in range(scale):
                yy = yy0 + sy
                if 0 <= yy < self.h and 0 <= xx0 and xx0 + scale <= self.w:
                  off = yy * row_bytes + xx0 * 2
                  self.fb[off : off + len(pix)] = pix
      cx += step

  def _draw_emo_eye(
      self,
      cx: int,
      cy: int,
      ew: int,
      eh: int,
      r: int = 18,
      main_col: int = 0,
      glow_col: int = 0,
      hi_col: int = 0,
      slant_l: int = 0,
      slant_r: int = 0,
      arch_bot: int = 0,
      scanline: bool = True,
  ):
    if ew <= 4 or eh <= 4:
      return
    x0 = int(cx - ew // 2)
    y0 = int(cy - eh // 2)

    # 1. Outer 3D neon halo
    if glow_col:
      self.fill_round_rect(x0 - 3, y0 - 3, ew + 6, eh + 6, r + 3, glow_col)

    # 2. Solid glowing EMO squircle (no black pupil!)
    self.fill_round_rect(x0, y0, ew, eh, r, main_col)

    # 3. Top 3D bevel highlight
    if hi_col and eh >= 18:
      self.fill_round_rect(
          x0 + 6, y0 + 4, max(8, ew - 12), max(5, eh // 5), max(3, r // 2), hi_col
      )

    # 4. Subtle OLED horizontal scanlines
    if scanline and eh >= 20:
      scan_col = ((main_col >> 1) & 0x7BEF) + ((main_col >> 2) & 0x39E7)
      for yy in range(y0 + 3, y0 + eh - 2, 4):
        self.fill_rect(x0 + 4, yy, max(1, ew - 8), 1, scan_col)

    # 5. Diagonal angry/drunk eyelid cut
    if slant_l > 0 or slant_r > 0:
      step = 4
      for col in range(0, ew, step):
        t = col / float(max(1, ew - 1))
        h_cut = int(slant_l + (slant_r - slant_l) * t)
        if h_cut > 0:
          sw = min(step, ew - col)
          self.fill_rect(x0 + col, y0 - 4, sw, h_cut + 4, 0x0000)

    # 6. Happy upward bottom arch
    if arch_bot > 0:
      step = 4
      half = max(1.0, ew * 0.52)
      y_bot = y0 + eh
      for col in range(0, ew, step):
        dx = (col + step * 0.5) - (ew * 0.5)
        k = 1.0 - (dx / half) ** 2
        if k > 0.0:
          cut = int(arch_bot * k)
          if cut > 0:
            sw = min(step, ew - col)
            self.fill_rect(x0 + col, y_bot - cut, sw, cut + 4, 0x0000)

  def _draw_heart(self, cx: int, cy: int, size: int, col: int, hi: int):
    r = max(8, size // 4)
    self.fill_circle(cx - r, cy - r // 2, r, col)
    self.fill_circle(cx + r, cy - r // 2, r, col)
    for dy in range(0, size // 2 + 4):
      w = max(1, (size - dy * 2))
      self.fill_rect(cx - w // 2, cy - r // 2 + dy, w, 1, col)
    self.fill_circle(cx - r - 3, cy - r // 2 - 3, 4, hi)
    scan_col = ((col >> 1) & 0x7BEF) + ((col >> 2) & 0x39E7)
    for yy in range(cy - r, cy + size // 2, 4):
      self.fill_rect(cx - size // 2, yy, size, 1, scan_col)

  def _draw_bottle(self, x: int, y: int):
    bottle_g = _rgb565(0, 230, 120)
    bottle_d = _rgb565(0, 140, 70)
    cork = _rgb565(245, 158, 11)
    label = _rgb565(254, 243, 199)
    self.fill_rect(x + 7, y, 6, 4, cork)
    self.fill_rect(x + 6, y + 4, 8, 12, bottle_d)
    self.fill_round_rect(x, y + 15, 20, 30, 5, bottle_g)
    self.fill_rect(x + 3, y + 23, 14, 12, label)
    self.fill_rect(x + 5, y + 26, 10, 2, _rgb565(180, 83, 9))
    self.fill_rect(x + 2, y + 18, 3, 20, _rgb565(167, 243, 208))

  def _draw_fly(self, fx: int, fy: int, tick: int):
    wing_col = _rgb565(226, 232, 240)
    body_col = _rgb565(51, 65, 85)
    eye_col = _rgb565(255, 60, 80)
    flap = -3 if (tick % 2) == 0 else 2
    self.fill_circle(fx - 4, fy - 4 + flap, 4, wing_col)
    self.fill_circle(fx + 4, fy - 4 - flap, 4, wing_col)
    self.fill_circle(fx, fy, 4, body_col)
    self.fill_rect(fx - 2, fy - 2, 2, 2, eye_col)
    self.fill_rect(fx + 1, fy - 2, 2, 2, eye_col)

  def render_emoji(self, status: dict, tick: int = 0):
    mood = str(status.get("bot_mood", "idle"))
    owner_seen = bool(status.get("owner_seen", False))
    show_cap = bool(status.get("show_caption", False)) or mood in (
        "listening",
        "thinking",
        "speaking",
    )
    reply = str(status.get("last_bot_reply", "") or "")

    active_mode = str(status.get("display_state") or mood or "idle")
    if active_mode == "auto":
      active_mode = "idle"

    self.fb[:] = self._bg_buf

    # Signature EMO Neon Colors
    emo_cyan = _rgb565(0, 242, 206)
    emo_glow = _rgb565(0, 68, 60)
    emo_hi = _rgb565(155, 255, 240)

    mint = _rgb565(34, 245, 140)
    mint_glow = _rgb565(0, 74, 42)
    mint_hi = _rgb565(170, 255, 210)

    blue = _rgb565(59, 155, 255)
    blue_glow = _rgb565(15, 45, 95)
    blue_hi = _rgb565(165, 215, 255)

    amber = _rgb565(250, 175, 20)
    amber_glow = _rgb565(75, 45, 0)
    amber_hi = _rgb565(255, 232, 130)

    pink = _rgb565(255, 70, 165)
    pink_glow = _rgb565(75, 12, 46)
    pink_hi = _rgb565(255, 185, 225)

    red = _rgb565(255, 45, 75)
    red_glow = _rgb565(80, 10, 20)
    red_hi = _rgb565(255, 155, 170)

    white = _rgb565(241, 245, 249)
    muted = _rgb565(148, 163, 184)

    # Tiny unobtrusive 5x5 owner/lock LED dot at top-right corner
    dot_col = mint if owner_seen else _rgb565(45, 55, 72)
    self.fill_rect(self.w - 10, 6, 5, 5, dot_col)

    cx = self.w // 2
    cy = (86 if show_cap else 114) if self.h >= 220 else self.h // 2
    eye_dx = max(46, int(self.w * 0.185))
    lx, rx = cx - eye_dx, cx + eye_dx
    base_w, base_h = (72, 82) if self.w >= 300 else (56, 66)

    if active_mode in ("happy", "owner"):
      bounce = int(math.sin(tick * 0.7) * 5)
      c_m, c_g, c_h = (mint, mint_glow, mint_hi) if owner_seen or active_mode == "owner" else (emo_cyan, emo_glow, emo_hi)
      self._draw_emo_eye(lx, cy + bounce, base_w + 4, base_h - 4, 20, c_m, c_g, c_h, arch_bot=36)
      self._draw_emo_eye(rx, cy + bounce, base_w + 4, base_h - 4, 20, c_m, c_g, c_h, arch_bot=36)
      # Twinkling pixel sparkles
      if (tick % 4) < 2:
        self.fill_rect(lx - base_w // 2 - 12, cy - 28, 8, 2, c_h)
        self.fill_rect(lx - base_w // 2 - 9, cy - 31, 2, 8, c_h)
        self.fill_rect(rx + base_w // 2 + 5, cy - 26, 8, 2, c_h)
        self.fill_rect(rx + base_w // 2 + 8, cy - 29, 2, 8, c_h)

    elif active_mode == "curious":
      tilt = int(math.sin(tick * 0.25) * 6)
      self._draw_emo_eye(lx + tilt, cy - 6, base_w + 6, base_h + 10, 20, emo_cyan, emo_glow, emo_hi)
      self._draw_emo_eye(rx + tilt, cy + 8, base_w - 4, int(base_h * 0.65), 16, emo_cyan, emo_glow, emo_hi, slant_l=8)

    elif active_mode in ("angry", "denied"):
      shk = -2 if (tick % 2) == 0 else 2
      self._draw_emo_eye(lx + shk, cy, base_w, base_h - 6, 16, red, red_glow, red_hi, slant_l=0, slant_r=30)
      self._draw_emo_eye(rx + shk, cy, base_w, base_h - 6, 16, red, red_glow, red_hi, slant_l=30, slant_r=0)

    elif active_mode == "drunk":
      wx = int(math.sin(tick * 0.45) * 7)
      wy = int(math.cos(tick * 0.35) * 5)
      self._draw_emo_eye(lx + wx, cy + wy, base_w, base_h - 6, 18, pink, pink_glow, pink_hi, slant_l=32, slant_r=4)
      self._draw_emo_eye(rx + wx, cy - wy, base_w, base_h - 6, 18, emo_cyan, emo_glow, emo_hi, slant_l=4, slant_r=32)
      for k in range(3):
        ang = tick * 0.4 + k * 2.1
        sx = cx + int(math.cos(ang) * 76)
        sy = cy - 48 + int(math.sin(ang) * 10)
        self.fill_circle(sx, sy, 3, amber)
      self._draw_bottle(self.w - 30, cy - 10)

    elif active_mode == "fly":
      fx = cx + int(math.sin(tick * 0.32) * (self.w * 0.34))
      fy = cy - 14 + int(math.sin(tick * 0.64) * 34)
      gx = max(-16, min(16, (fx - cx) // 5))
      gy = max(-14, min(14, (fy - cy) // 4))
      # 3D perspective scaling toward fly
      lw = int(base_w * (1.10 if gx < -3 else (0.90 if gx > 3 else 1.0)))
      rw = int(base_w * (1.10 if gx > 3 else (0.90 if gx < -3 else 1.0)))
      squint = 12 if abs(fx - cx) < 28 else 0
      self._draw_emo_eye(lx + gx, cy + gy, lw, base_h - 4, 18, emo_cyan, emo_glow, emo_hi, slant_l=squint, slant_r=squint)
      self._draw_emo_eye(rx + gx, cy + gy, rw, base_h - 4, 18, emo_cyan, emo_glow, emo_hi, slant_l=squint, slant_r=squint)
      self._draw_fly(fx, fy, tick)

    elif active_mode == "love":
      pulse = 6 if (tick % 6) < 3 else 0
      self._draw_heart(lx, cy + 4, 56 + pulse, pink, white)
      self._draw_heart(rx, cy + 4, 56 + pulse, pink, white)

    elif active_mode == "cool":
      vw = base_w * 2 + 46
      vx = cx - vw // 2
      self.fill_round_rect(vx, cy - 32, vw, 64, 18, _rgb565(18, 28, 46))
      self.draw_rect_border(vx, cy - 32, vx + vw, cy + 32, emo_cyan, thick=3)
      self.fill_round_rect(lx - 26, cy - 14, 52, 26, 8, emo_cyan)
      self.fill_round_rect(rx - 26, cy - 14, 52, 26, 8, emo_cyan)
      beam_x = vx + 10 + ((tick * 16) % max(24, vw - 30))
      self.fill_rect(beam_x, cy - 26, 10, 52, emo_hi)

    elif active_mode == "sleep":
      bob = 2 if (tick % 10) < 5 else 0
      self.fill_round_rect(lx - base_w // 2, cy + 4 + bob, base_w, 9, 4, _rgb565(0, 125, 110))
      self.fill_round_rect(rx - base_w // 2, cy + 4 + bob, base_w, 9, 4, _rgb565(0, 125, 110))
      z_off = (tick * 3) % 30
      self.draw_text(cx + 46, cy - 18 - z_off, "Z", emo_hi, scale=1)
      self.draw_text(cx + 62, cy - 34 - (z_off // 2), "Z", emo_cyan, scale=2)

    elif active_mode == "listening":
      p = 5 if (tick % 4) < 2 else 0
      self._draw_emo_eye(lx, cy, base_w + 4 + p, base_h + 6 + p, 20, blue, blue_glow, blue_hi)
      self._draw_emo_eye(rx, cy, base_w + 4 + p, base_h + 6 + p, 20, blue, blue_glow, blue_hi)
      for idx in range(5):
        hv = 8 + ((tick + idx) % 3) * 6
        self.fill_round_rect(cx - 32 + idx * 14, cy + 56 - hv // 2, 7, hv, 3, emo_cyan)

    elif active_mode == "thinking":
      shift = int(math.sin(tick * 0.55) * 14)
      self._draw_emo_eye(lx + shift, cy - 6, base_w, base_h, 18, amber, amber_glow, amber_hi)
      self._draw_emo_eye(rx + shift, cy + 6, base_w - 6, int(base_h * 0.62), 16, amber, amber_glow, amber_hi, slant_l=8)
      for idx in range(3):
        dc = emo_cyan if (tick % 3) == idx else _rgb565(25, 35, 52)
        self.fill_circle(cx - 20 + idx * 20, cy + 56, 5, dc)

    elif active_mode == "speaking":
      arch = 20 + ((tick % 4) * 5)
      self._draw_emo_eye(lx, cy, base_w + 2, base_h, 20, emo_cyan, emo_glow, emo_hi, arch_bot=arch)
      self._draw_emo_eye(rx, cy, base_w + 2, base_h, 20, emo_cyan, emo_glow, emo_hi, arch_bot=arch)
      bars = (10, 24, 14, 30, 16, 24, 10)
      for idx, bh in enumerate(bars):
        hv = bh if ((tick + idx) % 2 == 0) else max(6, bh // 2)
        self.fill_round_rect(cx - 42 + idx * 12, cy + 56 - hv // 2, 7, hv, 3, mint)

    else:
      # Iconic EMO Idle: 3D perspective glance + natural quick blink
      cycle = tick % 44
      if cycle in (42, 43):
        # Crisp EMO squash blink
        self.fill_round_rect(lx - base_w // 2 - 4, cy - 4, base_w + 8, 9, 4, emo_cyan)
        self.fill_round_rect(rx - base_w // 2 - 4, cy - 4, base_w + 8, 9, 4, emo_cyan)
      else:
        gx = 0
        if 12 <= cycle <= 20:
          gx = -14
        elif 26 <= cycle <= 34:
          gx = 14
        # 3D perspective scale: closer eye looks slightly wider & taller!
        lw = int(base_w * (1.10 if gx < 0 else (0.90 if gx > 0 else 1.0)))
        lh = int(base_h * (1.06 if gx < 0 else (0.94 if gx > 0 else 1.0)))
        rw = int(base_w * (1.10 if gx > 0 else (0.90 if gx < 0 else 1.0)))
        rh = int(base_h * (1.06 if gx > 0 else (0.94 if gx < 0 else 1.0)))
        self._draw_emo_eye(lx + gx, cy, lw, lh, 18, emo_cyan, emo_glow, emo_hi)
        self._draw_emo_eye(rx + gx, cy, rw, rh, 18, emo_cyan, emo_glow, emo_hi)

    # Bottom floating subtitle ONLY when speaking/thinking/listening or recent reply!
    if show_cap:
      card_y = self.h - 48
      self.fill_round_rect(8, card_y, self.w - 16, 42, 10, _rgb565(12, 18, 32))
      self.draw_rect_border(8, card_y, self.w - 8, self.h - 6, _rgb565(0, 140, 125), thick=1)
      if mood == "listening":
        caption = "DANG NGHE... NOI CAU HOI CUA BAN!"
      elif mood == "thinking":
        caption = "GEMINI DANG SUY NGHI..."
      else:
        caption = reply if (reply and reply != "-") else ""
      lines = _wrap_ascii(caption, max_chars=max(16, (self.w - 28) // 6), max_lines=12)
      if len(lines) > 3:
        start_idx = (tick // 12) % (len(lines) - 2)
        vis_lines = lines[start_idx : start_idx + 3]
      else:
        vis_lines = lines
      for idx, ln in enumerate(vis_lines):
        self.draw_text(14, card_y + 5 + idx * 12, ln, white if idx == 0 else muted, scale=1)

  def render_hud(self, status: dict, tick: int = 0):
    tft_mode = str(status.get("tft_mode", "emoji"))
    disp_state = str(status.get("display_state") or "")
    if tft_mode == "checking" or disp_state == "checking":
      pass
    else:
      self.render_emoji(status, tick=tick)
      return

    owner_seen = bool(status.get("owner_seen", False))
    people = status.get("people", [])
    counts = status.get("counts", {})
    fps = float(status.get("fps", 0.0))

    white = _rgb565(241, 245, 249)
    muted = _rgb565(203, 213, 225)
    green = _rgb565(74, 222, 128)
    amber = _rgb565(245, 158, 11)
    cyan = _rgb565(56, 189, 248)

    banner_col = (
        _rgb565(22, 163, 74)
        if owner_seen
        else (_rgb565(220, 38, 38) if people else _rgb565(37, 99, 235))
    )

    loaded_bg = False
    if TFT_BG_PATH and os.path.isfile(TFT_BG_PATH):
      try:
        with open(TFT_BG_PATH, "rb") as f:
          raw = f.read()
        if len(raw) == len(self.fb):
          self.fb[:] = raw
          loaded_bg = True
      except OSError:
        pass
    if not loaded_bg:
      self.fb[:] = self._bg_buf

    src_w = max(1.0, float(status.get("w", self.w)))
    src_h = max(1.0, float(status.get("h", self.h)))

    for d in (status.get("dets", []) or [])[:8]:
      box = d.get("box", [])
      if len(box) < 4:
        continue
      rx1 = max(0, int((float(box[0]) / src_w) * self.w))
      ry1 = max(22, int((float(box[1]) / src_h) * self.h))
      rx2 = min(self.w - 1, int((float(box[2]) / src_w) * self.w))
      ry2 = min(self.h - 19, int((float(box[3]) / src_h) * self.h))
      if rx2 <= rx1 or ry2 <= ry1:
        continue
      lbl = str(d.get("label", "obj"))
      c565 = green if lbl == "person" else cyan
      self.draw_rect_border(rx1, ry1, rx2, ry2, c565, thick=2)
      self.draw_text(rx1 + 3, max(24, ry1 + 3), lbl[:8], c565, scale=1)

    for p in (people or [])[:3]:
      box = p.get("box", [])
      if len(box) < 4:
        continue
      rx1 = max(0, int((float(box[0]) / src_w) * self.w))
      ry1 = max(22, int((float(box[1]) / src_h) * self.h))
      rx2 = min(self.w - 1, int((float(box[2]) / src_w) * self.w))
      ry2 = min(self.h - 19, int((float(box[3]) / src_h) * self.h))
      if rx2 <= rx1 or ry2 <= ry1:
        continue
      is_own = bool(p.get("is_owner", False))
      pc = green if is_own else amber
      self.draw_rect_border(rx1, ry1, rx2, ry2, pc, thick=2)
      pname = str(p.get("name", "USER"))[:10]
      self.draw_text(rx1 + 3, max(24, ry1 - 9), pname, pc, scale=1)

    self.fill_rect(0, 0, self.w, 22, banner_col)
    if owner_seen:
      owners = [p.get("name", "OWNER") for p in people if p.get("is_owner")]
      title = f"OWNER: {owners[0]}" if owners else "OWNER"
    elif people:
      title = f"STRANGER! ({len(people)})"
    else:
      title = "CHECKING FACE..."
    self.draw_text(6, 7, title[:22], white, scale=1)

    fps_txt = f"FPS:{fps:.1f}"
    fps_x = max(6, self.w - len(fps_txt) * 6 - 6)
    self.draw_text(fps_x, 7, fps_txt, white, scale=1)

    self.fill_rect(0, self.h - 18, self.w, 18, _rgb565(15, 23, 42))
    top_items = [f"{k}:{v}" for k, v in list(counts.items())[:3]]
    obj_txt = "OBJ: " + (" ".join(top_items) if top_items else "NONE")
    self.draw_text(6, self.h - 14, obj_txt[: (self.w - 12) // 6], muted, scale=1)

    bar_max = max(1, self.w - 12)
    fps_bar = min(bar_max, max(4, int((fps / 30.0) * bar_max)))
    self.fill_rect(6, self.h - 4, bar_max, 3, _rgb565(30, 41, 59))
    self.fill_rect(6, self.h - 4, fps_bar, 3, green)

  def flush(self):
    if not self.spi:
      return
    self._cmd(0x2A, struct.pack(">HH", 0, self.w - 1))
    self._cmd(0x2B, struct.pack(">HH", 0, self.h - 1))
    self._cmd(0x2C)
    _write_gpio(self.dc_path, 1)
    mv = memoryview(self.fb)
    chunk = 4096
    for off in range(0, len(self.fb), chunk):
      self.spi.writebytes2(mv[off : off + chunk])

  def close(self):
    if self.spi:
      try:
        self.spi.close()
      except OSError:
        pass
      self.spi = None


def tft_loop(state):
  disp = ST7789Display()
  has_hw = disp.open()
  state.update_ui(None, {"tft_ok": has_hw})
  if not has_hw:
    disp.close()
    return

  tick = 0
  interval = 1.0 / TFT_FPS if TFT_FPS > 0 else 0.1

  try:
    while state.running:
      with state.ui_lock:
        snap = dict(state.ui_status)
      disp.render_hud(snap, tick=tick)
      disp.flush()
      tick += 1
      time.sleep(interval)
  finally:
    disp.close()
