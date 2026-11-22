import time
from tft_driver import (
    BLACK, WHITE, rgb565_bytes,
    draw_circle, draw_ring, draw_capsule_h,
)
from robot_engine import (
    EYE_W, EYE_H, LEFT_X, RIGHT_X, EYE_Y,
    MOUTH_W, MOUTH_H, MOUTH_X, MOUTH_Y,
    CHEEK_W, CHEEK_H, CHEEK_LX, CHEEK_RX, CHEEK_Y,
    MASKS_OPEN, MASK_BATTLE_L, MASK_BATTLE_R, MASK_SLEEPY, MASK_SURPRISED,
    CHEEK_OFF, BaseRobotFace,
    render_happy_eye, render_love_eyes, render_cheek, render_mouth,
    blit_masked_2d, effective_brightness,
)

# --- Bang mau Senju / Tien Nhan Thuat (Sage Mode) ---
SAGE_BG     = rgb565_bytes(26, 16, 2)
SAGE_GLOW   = rgb565_bytes(110, 62, 6)
SAGE_AMBER  = rgb565_bytes(205, 125, 12)
SAGE_GOLD   = rgb565_bytes(250, 196, 28)
SAGE_BRIGHT = rgb565_bytes(255, 228, 95)
SAGE_CORE   = rgb565_bytes(255, 248, 210)
SAGE_RIMS   = (rgb565_bytes(155, 102, 14), rgb565_bytes(225, 162, 24), rgb565_bytes(255, 212, 68))

MARK_DIM    = rgb565_bytes(135, 22, 24)
MARK_BRIGHT = rgb565_bytes(235, 50, 42)
BLUSH_WARM  = rgb565_bytes(195, 105, 25)
MOUTH_LIGHT = rgb565_bytes(245, 242, 232)
MOUTH_GOLD  = rgb565_bytes(250, 198, 45)

SEAL_SIZE = 34
SEAL_X = (320 - SEAL_SIZE) // 2
SEAL_Y = 6


class SenjuWatchFace(BaseRobotFace):
    """Mat Robot Emoji Senju / Tien Nhan Thuat (Sage Mode)"""

    def __init__(self):
        super().__init__()
        self.eye_sage = self._render_sage_eye(1.0)
        self.eye_small = self._render_sage_eye(0.68)
        self.happy_gold = render_happy_eye(SAGE_AMBER, SAGE_GOLD, SAGE_CORE)
        self.love_gold = render_love_eyes(SAGE_AMBER, SAGE_GOLD, SAGE_CORE)
        self.seal_dim = self._render_forehead_seal(MARK_DIM)
        self.seal_glow = self._render_forehead_seal(MARK_BRIGHT)
        self.cheek_warm = render_cheek(BLUSH_WARM)

        self.mouths = {
            m: render_mouth(m, MOUTH_LIGHT if m in ("normal", "sleepy") else MOUTH_GOLD)
            for m in ("normal", "battle", "happy", "love", "sleepy", "surprised")
        }

    def _render_sage_eye(self, scale=1.0):
        buf = bytearray(SAGE_BG * (EYE_W * EYE_H))
        cx, cy = EYE_W // 2, EYE_H // 2
        r = lambda v: max(2, int(v * scale))

        draw_circle(buf, EYE_W, EYE_H, cx, cy, r(46), SAGE_GLOW)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, r(42), BLACK)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, r(40), SAGE_AMBER)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, r(35), SAGE_GOLD)
        draw_ring(buf, EYE_W, EYE_H, cx, cy, r(30), 2, SAGE_BRIGHT)
        draw_capsule_h(buf, EYE_W, EYE_H, cx, cy, r(24), r(6), BLACK)
        draw_circle(buf, EYE_W, EYE_H, cx - 15, cy - 16, 6, WHITE)
        draw_circle(buf, EYE_W, EYE_H, cx - 6, cy - 22, 2, SAGE_CORE)
        return buf

    def _render_forehead_seal(self, color):
        buf = bytearray(BLACK * (SEAL_SIZE * SEAL_SIZE))
        c = SEAL_SIZE // 2
        draw_ring(buf, SEAL_SIZE, SEAL_SIZE, c, c, 13, 3, color)
        draw_circle(buf, SEAL_SIZE, SEAL_SIZE, c, c, 5, color)
        return buf

    def _draw_side_marks(self, lcd, color):
        lcd.fill_rect(4, 96, 12, 6, color)
        lcd.fill_rect(4, 108, 8, 4, color)
        lcd.fill_rect(304, 96, 12, 6, color)
        lcd.fill_rect(308, 108, 8, 4, color)

    def _update_accessories(self, lcd, mood, b_pct):
        if mood != self._last_mood:
            lcd.blit(MOUTH_X, MOUTH_Y, MOUTH_W, MOUTH_H, self._get_dimmed(self.mouths[mood], b_pct))
            if mood in ("happy", "love"):
                ck = self._get_dimmed(self.cheek_warm, b_pct)
                lcd.blit(CHEEK_LX, CHEEK_Y, CHEEK_W, CHEEK_H, ck)
                lcd.blit(CHEEK_RX, CHEEK_Y, CHEEK_W, CHEEK_H, ck)
            else:
                lcd.blit(CHEEK_LX, CHEEK_Y, CHEEK_W, CHEEK_H, CHEEK_OFF)
                lcd.blit(CHEEK_RX, CHEEK_Y, CHEEK_W, CHEEK_H, CHEEK_OFF)
            self._last_mood = mood

    def on_enter(self, lcd, state=None):
        st = state or {}
        lcd.fill_screen(BLACK)
        self._last_mood = None
        self._last_hud_on = None
        self.gaze_dx = self.gaze_dy = self.gaze_tx = self.gaze_ty = 0
        b_pct = effective_brightness(st)

        lcd.blit(SEAL_X, SEAL_Y, SEAL_SIZE, SEAL_SIZE, self._get_dimmed(self.seal_glow, b_pct))
        self._draw_side_marks(lcd, MARK_BRIGHT)
        self._update_accessories(lcd, "normal", b_pct)
        self._update_hud(lcd, st)

        eye = self._get_dimmed(self.eye_sage, b_pct)
        for idx in (0, 1, 2, 3):
            m = MASKS_OPEN[idx]
            blit_masked_2d(self.work_l, eye, m, SAGE_RIMS[1], 0, 0)
            blit_masked_2d(self.work_r, eye, m, SAGE_RIMS[1], 0, 0)
            lcd.blit(LEFT_X, EYE_Y, EYE_W, EYE_H, self.work_l)
            lcd.blit(RIGHT_X, EYE_Y, EYE_W, EYE_H, self.work_r)
            time.sleep(0.024)

    def update(self, lcd, state=None):
        st = state or {}
        mood = self._resolve_mood(st)
        b_pct = effective_brightness(st)
        rim = SAGE_RIMS[(0, 1, 2, 1)[(self.tick // 6) % 4]]
        eye = self._get_dimmed(self.eye_small if mood == "surprised" else self.eye_sage, b_pct)

        self._update_hud(lcd, st)
        self._update_accessories(lcd, mood, b_pct)

        if self.tick % 10 == 0:
            glow = (self.tick // 10) % 2 == 0
            seal = self._get_dimmed(self.seal_glow if glow else self.seal_dim, b_pct)
            lcd.blit(SEAL_X, SEAL_Y, SEAL_SIZE, SEAL_SIZE, seal)
            self._draw_side_marks(lcd, MARK_BRIGHT if glow else MARK_DIM)

        if st.get("powerup"):
            st["powerup"] = False
            self._do_powerup(lcd, eye, eye, SAGE_BRIGHT, SAGE_BRIGHT, WHITE)

        if st.get("blink"):
            st["blink"] = False
            if mood not in ("happy", "love"):
                self._do_blink(lcd, eye, eye, rim, rim, double=False)

        self._step_gaze(st, mood)

        if mood == "happy":
            hb = self._get_dimmed(self.happy_gold, b_pct)
            lcd.blit(LEFT_X, EYE_Y, EYE_W, EYE_H, hb)
            lcd.blit(RIGHT_X, EYE_Y, EYE_W, EYE_H, hb)
        elif mood == "love":
            lb = self._get_dimmed(self.love_gold[(self.tick // 4) % 2], b_pct)
            lcd.blit(LEFT_X, EYE_Y, EYE_W, EYE_H, lb)
            lcd.blit(RIGHT_X, EYE_Y, EYE_W, EYE_H, lb)
        else:
            if mood == "battle":
                ml, mr = MASK_BATTLE_L, MASK_BATTLE_R
            elif mood == "sleepy":
                ml, mr = MASK_SLEEPY, MASK_SLEEPY
            elif mood == "surprised":
                ml, mr = MASK_SURPRISED, MASK_SURPRISED
            else:
                ml, mr = MASKS_OPEN[3], MASKS_OPEN[3]

            blit_masked_2d(self.work_l, eye, ml, rim, self.gaze_dx, self.gaze_dy)
            blit_masked_2d(self.work_r, eye, mr, rim, self.gaze_dx, self.gaze_dy)
            lcd.blit(LEFT_X, EYE_Y, EYE_W, EYE_H, self.work_l)
            lcd.blit(RIGHT_X, EYE_Y, EYE_W, EYE_H, self.work_r)

        self.tick += 1
        if not st.get("gaze_manual") and self.tick in (12, 24, 36):
            self.gaze_idx = (self.gaze_idx + 1) % len(self.GAZE_POINTS)
            self.gaze_tx, self.gaze_ty = self.GAZE_POINTS[self.gaze_idx]
        elif self.tick >= 46:
            if mood not in ("happy", "love"):
                self._do_blink(lcd, eye, eye, rim, rim, double=(self.auto_mood_idx % 3 == 0))
            if st.get("mood", "auto") == "auto":
                self.auto_mood_idx = (self.auto_mood_idx + 1) % len(self.AUTO_MOODS)
            self.tick = 0

        time.sleep(self._frame_delay(st))
