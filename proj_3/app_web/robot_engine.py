import os
import json
import math
import time
from tft_driver import (
    BLACK, WHITE, rgb565_bytes,
    draw_circle, draw_ring, draw_ellipse, draw_capsule_h,
    draw_arc_thick, draw_heart, fill_span, dim_rgb565_buf,
)

# --- Bo cuc khuon mat Robot 320x240 ---
EYE_W = 124
EYE_H = 116
LEFT_X = 24
RIGHT_X = 172
EYE_Y = 48

MOUTH_W = 120
MOUTH_H = 34
MOUTH_X = 100
MOUTH_Y = 188

CHEEK_W = 28
CHEEK_H = 12
CHEEK_LX = 30
CHEEK_RX = 262
CHEEK_Y = 170

HUD_COLOR = rgb565_bytes(190, 200, 220)
HUD_DIM   = rgb565_bytes(105, 115, 135)

BLACK_ROW = BLACK * EYE_W
OPEN_LEVELS = [0.08, 0.35, 0.72, 1.0]

# --- Luu & doc cau hinh config.json ---
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG = {
    "mode": "uchiha",
    "variant": "auto",
    "mood": "auto",
    "hud": True,
    "speed": 3,
    "brightness": 100,
    "night_mode": False,
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k in DEFAULT_CONFIG:
                if k in data:
                    cfg[k] = data[k]
    except Exception as e:
        print(f"[Config] Khong doc duoc config.json: {e}")
    return cfg


def save_config(state):
    try:
        data = {k: state.get(k, DEFAULT_CONFIG[k]) for k in DEFAULT_CONFIG}
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[Config] Khong luu duoc config.json: {e}")


def is_night_hours():
    h = time.localtime().tm_hour
    return h >= 22 or h < 6


def effective_brightness(state):
    b = int(state.get("brightness", 100))
    if state.get("night_mode") and is_night_hours():
        return min(b, 40)
    return max(30, min(100, b))


# --- Tao cac mat na hinh mat Robot dung chung ---
def build_rect_mask(openness, radius=34):
    h = max(8, int(EYE_H * openness))
    y0 = (EYE_H - h) // 2
    y1 = y0 + h - 1
    r = min(radius, h // 2, EYE_W // 2)
    r2 = r * r
    rows = []
    for y in range(EYE_H):
        if y < y0 or y > y1:
            rows.append((-1, -1))
            continue
        local_y = y - y0
        if local_y < r:
            dy = r - local_y
            inset = r - int(math.sqrt(max(0, r2 - dy * dy)))
        elif local_y >= h - r:
            dy = local_y - (h - r - 1)
            inset = r - int(math.sqrt(max(0, r2 - dy * dy)))
        else:
            inset = 0
        rows.append((inset, EYE_W - 1 - inset))
    return rows


def build_battle_mask(base_mask, is_right):
    rows = []
    for y in range(EYE_H):
        x0, x1 = base_mask[y]
        if x0 == -1:
            rows.append((-1, -1))
            continue
        nx0, nx1 = x0, x1
        if y < 44:
            if not is_right:
                cut = int((y - 6) * (EYE_W - 1) / 38.0)
                if y < 6:
                    nx0, nx1 = -1, -1
                else:
                    nx1 = min(x1, cut)
            else:
                cut = int((EYE_W - 1) - (y - 6) * (EYE_W - 1) / 38.0)
                if y < 6:
                    nx0, nx1 = -1, -1
                else:
                    nx0 = max(x0, cut)
        rows.append((-1, -1) if nx0 > nx1 else (nx0, nx1))
    return rows


def build_sleepy_mask(base_mask):
    return [(-1, -1) if y < 44 else base_mask[y] for y in range(EYE_H)]


MASKS_OPEN = [build_rect_mask(op) for op in OPEN_LEVELS]
MASK_SURPRISED = build_rect_mask(1.0, radius=46)
MASK_BATTLE_L = build_battle_mask(MASKS_OPEN[-1], False)
MASK_BATTLE_R = build_battle_mask(MASKS_OPEN[-1], True)
MASK_SLEEPY = build_sleepy_mask(MASKS_OPEN[-1])


# --- Render bieu cam Robot dung chung ---
def render_happy_eye(main_col, bright_col, core_col):
    buf = bytearray(BLACK * (EYE_W * EYE_H))
    cx = EYE_W // 2
    cy = int(EYE_H * 0.68)
    draw_arc_thick(buf, EYE_W, EYE_H, cx, cy, 38, 205, 335, 16, main_col)
    draw_arc_thick(buf, EYE_W, EYE_H, cx, cy, 38, 210, 330, 8, bright_col)
    draw_arc_thick(buf, EYE_W, EYE_H, cx, cy, 38, 220, 320, 3, core_col)
    return buf


def render_love_eyes(main_col, bright_col, core_col):
    """Tra ve 2 khung hinh trai tim (nho / lon) de dap nhip"""
    frames = []
    for sz in (68, 78):
        buf = bytearray(BLACK * (EYE_W * EYE_H))
        cx, cy = EYE_W // 2, EYE_H // 2 + 2
        draw_heart(buf, EYE_W, EYE_H, cx, cy, sz + 8, main_col)
        draw_heart(buf, EYE_W, EYE_H, cx, cy, sz, bright_col)
        draw_circle(buf, EYE_W, EYE_H, cx - int(sz * 0.22), cy - int(sz * 0.16), 5, core_col)
        frames.append(buf)
    return frames


def render_cheek(color):
    buf = bytearray(BLACK * (CHEEK_W * CHEEK_H))
    draw_ellipse(buf, CHEEK_W, CHEEK_H, CHEEK_W // 2, CHEEK_H // 2, 12, 4, color)
    return buf


CHEEK_OFF = bytearray(BLACK * (CHEEK_W * CHEEK_H))


def render_mouth(mood, color):
    buf = bytearray(BLACK * (MOUTH_W * MOUTH_H))
    cx = MOUTH_W // 2
    if mood == "normal":
        draw_arc_thick(buf, MOUTH_W, MOUTH_H, cx, 4, 22, 38, 142, 5, color)
    elif mood in ("happy", "love"):
        draw_arc_thick(buf, MOUTH_W, MOUTH_H, cx, 2, 24, 20, 160, 6, color)
    elif mood == "battle":
        draw_capsule_h(buf, MOUTH_W, MOUTH_H, cx, 16, 20, 3, color)
    elif mood == "sleepy":
        draw_ring(buf, MOUTH_W, MOUTH_H, cx, 16, 7, 3, color)
    elif mood == "surprised":
        draw_ring(buf, MOUTH_W, MOUTH_H, cx, 17, 11, 4, color)
    return buf


# --- Blit mat 2D (ho tro nhin len/xuong/trai/phai/cheo + vien neon) ---
def blit_masked_2d(dst_buf, src_buf, mask, rim_color, gaze_dx, gaze_dy):
    row_bytes = EYE_W * 2
    bg_px = src_buf[0:2]
    first_y = -1
    last_y = -1
    for y in range(EYE_H):
        if mask[y][0] != -1:
            if first_y == -1:
                first_y = y
            last_y = y

    for y in range(EYE_H):
        dst = y * row_bytes
        dst_buf[dst:dst + row_bytes] = BLACK_ROW
        x0, x1 = mask[y]
        if x0 == -1:
            continue

        sy = y - gaze_dy
        if sy < 0 or sy >= EYE_H:
            dst_buf[dst + x0 * 2:dst + (x1 + 1) * 2] = bg_px * (x1 - x0 + 1)
        elif gaze_dx == 0:
            src_row = sy * row_bytes
            dst_buf[dst + x0 * 2:dst + (x1 + 1) * 2] = src_buf[src_row + x0 * 2:src_row + (x1 + 1) * 2]
        else:
            src_row = sy * row_bytes
            src_x0 = x0 - gaze_dx
            src_x1 = x1 - gaze_dx
            vx0 = max(0, src_x0)
            vx1 = min(EYE_W - 1, src_x1)
            if vx1 >= vx0:
                dx0 = vx0 + gaze_dx
                dx1 = vx1 + gaze_dx
                dst_buf[dst + dx0 * 2:dst + (dx1 + 1) * 2] = (
                    src_buf[src_row + vx0 * 2:src_row + (vx1 + 1) * 2]
                )
            if src_x0 < 0:
                fill_len = min(x1 - x0 + 1, -src_x0)
                dst_buf[dst + x0 * 2:dst + (x0 + fill_len) * 2] = bg_px * fill_len
            if src_x1 >= EYE_W:
                over = src_x1 - (EYE_W - 1)
                fill_len = min(x1 - x0 + 1, over)
                start_x = x1 - fill_len + 1
                dst_buf[dst + start_x * 2:dst + (x1 + 1) * 2] = bg_px * fill_len

        if rim_color is not None:
            if y <= first_y + 1 or y >= last_y - 1:
                fill_span(dst_buf, EYE_W, EYE_H, y, x0, x1, rim_color)
            else:
                px0, px1 = mask[y - 1]
                l_end = max(x0 + 1, px0) if px0 != -1 else x0 + 1
                r_start = min(x1 - 1, px1) if px1 != -1 else x1 - 1
                fill_span(dst_buf, EYE_W, EYE_H, y, x0, min(x1, l_end), rim_color)
                fill_span(dst_buf, EYE_W, EYE_H, y, max(x0, r_start), x1, rim_color)


# --- Lop co so cho moi mat Robot Naruto ---
class BaseRobotFace:
    """Quan ly chung: Idle AI 2D, Double-Blink, Power-Up, Breathing Glow, Clock HUD, Brightness"""

    AUTO_MOODS = ("normal", "normal", "battle", "normal", "happy", "surprised", "love", "sleepy")
    GAZE_POINTS = (
        (0, 0), (9, 0), (-9, 0), (0, -6), (8, -5), (-8, -5), (7, 5), (-7, 5), (0, 0)
    )

    def __init__(self):
        self.work_l = bytearray(EYE_W * EYE_H * 2)
        self.work_r = bytearray(EYE_W * EYE_H * 2)
        self.tick = 0
        self.frame_idx = 0
        self.auto_mood_idx = 0
        self.gaze_idx = 0
        self.gaze_dx = 0
        self.gaze_dy = 0
        self.gaze_tx = 0
        self.gaze_ty = 0
        self._last_mood = None
        self._last_accent = None
        self._last_hud_str = None
        self._last_hud_on = None
        self._dim_cache = {}
        self._dim_level = 100

    def _get_dimmed(self, buf, b_pct):
        if b_pct >= 98:
            return buf
        if b_pct != self._dim_level:
            self._dim_cache.clear()
            self._dim_level = b_pct
        key = id(buf)
        cached = self._dim_cache.get(key)
        if cached is None:
            cached = dim_rgb565_buf(buf, b_pct)
            self._dim_cache[key] = cached
        return cached

    def _update_hud(self, lcd, state):
        hud_on = bool(state.get("hud", True))
        if not hud_on:
            if self._last_hud_on is not False:
                lcd.fill_rect(8, 8, 72, 20, BLACK)
                lcd.fill_rect(240, 8, 72, 20, BLACK)
                self._last_hud_on = False
                self._last_hud_str = None
            return

        now = time.localtime()
        t_str = f"{now.tm_hour:02d}:{now.tm_min:02d}"
        d_str = f"{now.tm_mday:02d}/{now.tm_mon:02d}"
        key = t_str + d_str + str(effective_brightness(state))
        if key != self._last_hud_str or self._last_hud_on is not True:
            col = HUD_DIM if effective_brightness(state) <= 50 else HUD_COLOR
            lcd.draw_text(10, 10, t_str, col, BLACK, scale=2)
            lcd.draw_text(250, 10, d_str, HUD_DIM, BLACK, scale=2)
            self._last_hud_str = key
            self._last_hud_on = True

    def _do_blink(self, lcd, fl, fr, rim_l, rim_r, double=False):
        seq = (2, 1, 0, 1, 2, 3)
        count = 2 if double else 1
        for n in range(count):
            for idx in seq:
                m = MASKS_OPEN[idx]
                blit_masked_2d(self.work_l, fl, m, rim_l, self.gaze_dx, self.gaze_dy)
                blit_masked_2d(self.work_r, fr, m, rim_r, self.gaze_dx, self.gaze_dy)
                lcd.blit(LEFT_X, EYE_Y, EYE_W, EYE_H, self.work_l)
                lcd.blit(RIGHT_X, EYE_Y, EYE_W, EYE_H, self.work_r)
                time.sleep(0.016)
            if n == 0 and double:
                time.sleep(0.06)

    def _do_powerup(self, lcd, fl, fr, rim_l, rim_r, flash_col):
        """Hieu ung kich hoat Nhan Thuat: rung mat + chop sang + vao che do Battle"""
        # Chop sang nhanh
        for _ in range(2):
            blit_masked_2d(self.work_l, fl, MASK_BATTLE_L, flash_col, 0, 0)
            blit_masked_2d(self.work_r, fr, MASK_BATTLE_R, flash_col, 0, 0)
            lcd.blit(LEFT_X, EYE_Y, EYE_W, EYE_H, self.work_l)
            lcd.blit(RIGHT_X, EYE_Y, EYE_W, EYE_H, self.work_r)
            time.sleep(0.04)
            lcd.fill_rect(LEFT_X, EYE_Y, EYE_W, EYE_H, BLACK)
            lcd.fill_rect(RIGHT_X, EYE_Y, EYE_W, EYE_H, BLACK)
            time.sleep(0.025)

        # Rung nhe mat khi kich hoat
        offsets = ((-4, -2), (4, 2), (-3, 2), (3, -2), (-2, 0), (2, 0), (0, 0))
        for ox, oy in offsets:
            blit_masked_2d(self.work_l, fl, MASK_BATTLE_L, rim_l, ox, oy)
            blit_masked_2d(self.work_r, fr, MASK_BATTLE_R, rim_r, ox, oy)
            lcd.blit(LEFT_X, EYE_Y, EYE_W, EYE_H, self.work_l)
            lcd.blit(RIGHT_X, EYE_Y, EYE_W, EYE_H, self.work_r)
            time.sleep(0.028)

    def _step_gaze(self, state, mood):
        if state.get("gaze_manual"):
            self.gaze_tx = max(-12, min(12, int(state.get("gaze_x", 0))))
            self.gaze_ty = max(-10, min(10, int(state.get("gaze_y", 0))))
        elif mood not in ("normal", "sleepy", "surprised"):
            self.gaze_tx, self.gaze_ty = 0, 0

        if self.gaze_dx < self.gaze_tx:
            self.gaze_dx = min(self.gaze_tx, self.gaze_dx + 3)
        elif self.gaze_dx > self.gaze_tx:
            self.gaze_dx = max(self.gaze_tx, self.gaze_dx - 3)

        if self.gaze_dy < self.gaze_ty:
            self.gaze_dy = min(self.gaze_ty, self.gaze_dy + 2)
        elif self.gaze_dy > self.gaze_ty:
            self.gaze_dy = max(self.gaze_ty, self.gaze_dy - 2)

    def _resolve_mood(self, state):
        req = state.get("mood", "auto")
        if state.get("night_mode") and is_night_hours() and req == "auto":
            return "sleepy"
        if req == "auto":
            return self.AUTO_MOODS[self.auto_mood_idx]
        return req

    def _frame_delay(self, state):
        speed = max(1, min(5, int(state.get("speed", 3))))
        # speed 1..5 -> delay 0.11s .. 0.035s
        return 0.125 - speed * 0.018
