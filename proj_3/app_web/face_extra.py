import time
from tft_driver import (
    BLACK, WHITE, rgb565_bytes,
    draw_circle, draw_ring, draw_vertical_slit, draw_capsule_h,
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

# ==========================================================
# 1. KURAMA (CUU VI â€” NINE-TAILS FOX)
# ==========================================================
KUR_BG      = rgb565_bytes(30, 6, 2)
KUR_GLOW    = rgb565_bytes(140, 28, 6)
KUR_DEEP    = rgb565_bytes(210, 34, 10)
KUR_RED     = rgb565_bytes(255, 58, 14)
KUR_ORANGE  = rgb565_bytes(255, 132, 24)
KUR_CORE    = rgb565_bytes(255, 224, 175)
KUR_RIMS    = (rgb565_bytes(165, 42, 10), rgb565_bytes(235, 82, 18), rgb565_bytes(255, 145, 38))
WHISK_DIM   = rgb565_bytes(135, 36, 10)
WHISK_GLOW  = rgb565_bytes(255, 110, 25)
KUR_BLUSH   = rgb565_bytes(200, 65, 25)
MOUTH_LIGHT = rgb565_bytes(245, 240, 235)
MOUTH_FIRE  = rgb565_bytes(255, 115, 35)


class KuramaWatchFace(BaseRobotFace):
    """Mat Robot Emoji Cuu Vi (Kurama): Do cam ruc + dong tu xe doc + rau cao phat sang"""

    def __init__(self):
        super().__init__()
        self.eye_normal = self._render_kurama_eye(slit_w=9, iris_scale=1.0)
        self.eye_battle = self._render_kurama_eye(slit_w=5, iris_scale=1.05)
        self.eye_small = self._render_kurama_eye(slit_w=4, iris_scale=0.72)

        self.happy_fire = render_happy_eye(KUR_RED, KUR_ORANGE, KUR_CORE)
        self.love_fire = render_love_eyes(KUR_DEEP, KUR_ORANGE, KUR_CORE)
        self.cheek_fire = render_cheek(KUR_BLUSH)

        self.mouths = {
            m: render_mouth(m, MOUTH_LIGHT if m in ("normal", "sleepy") else MOUTH_FIRE)
            for m in ("normal", "battle", "happy", "love", "sleepy", "surprised")
        }

    def _render_kurama_eye(self, slit_w=9, iris_scale=1.0):
        buf = bytearray(KUR_BG * (EYE_W * EYE_H))
        cx, cy = EYE_W // 2, EYE_H // 2
        r = lambda v: max(2, int(v * iris_scale))

        draw_circle(buf, EYE_W, EYE_H, cx, cy, r(48), KUR_GLOW)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, r(43), BLACK)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, r(41), KUR_DEEP)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, r(36), KUR_RED)
        draw_ring(buf, EYE_W, EYE_H, cx, cy, r(30), 3, KUR_ORANGE)
        # Dong tu xe doc sac ben cua Ho Ly
        draw_vertical_slit(buf, EYE_W, EYE_H, cx, cy, slit_w, r(34), BLACK)
        draw_circle(buf, EYE_W, EYE_H, cx - 15, cy - 16, 6, WHITE)
        draw_circle(buf, EYE_W, EYE_H, cx - 6, cy - 22, 2, KUR_CORE)
        return buf

    def _draw_whiskers(self, lcd, color):
        """3 rau cao Cuu Vi phat sang hai ben ma"""
        for idx, y in enumerate((174, 186, 198)):
            w = 18 - idx * 2
            lcd.fill_rect(4, y, w, 4, color)
            lcd.fill_rect(316 - w, y, w, 4, color)

    def _update_accessories(self, lcd, mood, b_pct):
        if mood != self._last_mood:
            lcd.blit(MOUTH_X, MOUTH_Y, MOUTH_W, MOUTH_H, self._get_dimmed(self.mouths[mood], b_pct))
            if mood in ("happy", "love"):
                ck = self._get_dimmed(self.cheek_fire, b_pct)
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

        self._draw_whiskers(lcd, WHISK_GLOW)
        self._update_accessories(lcd, "normal", b_pct)
        self._update_hud(lcd, st)

        eye = self._get_dimmed(self.eye_normal, b_pct)
        for idx in (0, 1, 2, 3):
            m = MASKS_OPEN[idx]
            blit_masked_2d(self.work_l, eye, m, KUR_RIMS[1], 0, 0)
            blit_masked_2d(self.work_r, eye, m, KUR_RIMS[1], 0, 0)
            lcd.blit(LEFT_X, EYE_Y, EYE_W, EYE_H, self.work_l)
            lcd.blit(RIGHT_X, EYE_Y, EYE_W, EYE_H, self.work_r)
            time.sleep(0.024)

    def update(self, lcd, state=None):
        st = state or {}
        mood = self._resolve_mood(st)
        b_pct = effective_brightness(st)
        rim = KUR_RIMS[(0, 1, 2, 1)[(self.tick // 5) % 4]]

        if mood == "surprised":
            src = self.eye_small
        elif mood == "battle":
            src = self.eye_battle
        else:
            src = self.eye_normal
        eye = self._get_dimmed(src, b_pct)

        self._update_hud(lcd, st)
        self._update_accessories(lcd, mood, b_pct)

        if self.tick % 8 == 0:
            self._draw_whiskers(lcd, WHISK_GLOW if (self.tick // 8) % 2 == 0 else WHISK_DIM)

        if st.get("powerup"):
            st["powerup"] = False
            be = self._get_dimmed(self.eye_battle, b_pct)
            self._do_powerup(lcd, be, be, KUR_ORANGE, KUR_ORANGE, WHITE)

        if st.get("blink"):
            st["blink"] = False
            if mood not in ("happy", "love"):
                self._do_blink(lcd, eye, eye, rim, rim, double=False)

        self._step_gaze(st, mood)

        if mood == "happy":
            hb = self._get_dimmed(self.happy_fire, b_pct)
            lcd.blit(LEFT_X, EYE_Y, EYE_W, EYE_H, hb)
            lcd.blit(RIGHT_X, EYE_Y, EYE_W, EYE_H, hb)
        elif mood == "love":
            lb = self._get_dimmed(self.love_fire[(self.tick // 4) % 2], b_pct)
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


# ==========================================================
# 2. BYAKUGAN (BACH NHAN â€” HYUGA CLAN)
# ==========================================================
BYA_BG      = rgb565_bytes(22, 24, 36)
BYA_OUTER   = rgb565_bytes(175, 185, 220)
BYA_PEARL   = rgb565_bytes(228, 234, 250)
BYA_INNER   = rgb565_bytes(245, 248, 255)
BYA_RING    = rgb565_bytes(135, 145, 188)
BYA_RIMS    = (rgb565_bytes(130, 142, 185), rgb565_bytes(188, 198, 238), rgb565_bytes(235, 240, 255))
BYA_VEIN    = rgb565_bytes(165, 178, 225)
BYA_BLUSH   = rgb565_bytes(165, 145, 215)
MOUTH_ICE   = rgb565_bytes(210, 220, 252)


class ByakuganWatchFace(BaseRobotFace):
    """Mat Robot Emoji Bach Nhan (Byakugan): Trang ngoc trai tinh khiet + gan chakra"""

    def __init__(self):
        super().__init__()
        self.eye_bya = self._render_byakugan_eye(1.0)
        self.eye_small = self._render_byakugan_eye(0.72)
        self.happy_ice = render_happy_eye(BYA_RING, BYA_PEARL, WHITE)
        self.love_ice = render_love_eyes(BYA_RING, BYA_PEARL, WHITE)
        self.cheek_ice = render_cheek(BYA_BLUSH)

        self.mouths = {
            m: render_mouth(m, MOUTH_ICE)
            for m in ("normal", "battle", "happy", "love", "sleepy", "surprised")
        }

    def _render_byakugan_eye(self, scale=1.0):
        buf = bytearray(BYA_BG * (EYE_W * EYE_H))
        cx, cy = EYE_W // 2, EYE_H // 2
        r = lambda v: max(2, int(v * scale))

        draw_circle(buf, EYE_W, EYE_H, cx, cy, r(52), BYA_OUTER)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, r(44), BYA_PEARL)
        draw_ring(buf, EYE_W, EYE_H, cx, cy, r(34), 2, BYA_RING)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, r(26), BYA_INNER)
        draw_ring(buf, EYE_W, EYE_H, cx, cy, r(15), 2, BYA_OUTER)
        draw_circle(buf, EYE_W, EYE_H, cx - 14, cy - 16, 6, WHITE)
        return buf

    def _draw_veins(self, lcd, active):
        col = BYA_VEIN if active else BLACK
        # Gan chakra hai ben thai duong khi kich hoat Byakugan
        lcd.fill_rect(5, 86, 12, 3, col)
        lcd.fill_rect(9, 89, 3, 14, col)
        lcd.fill_rect(4, 102, 13, 3, col)
        lcd.fill_rect(303, 86, 12, 3, col)
        lcd.fill_rect(308, 89, 3, 14, col)
        lcd.fill_rect(303, 102, 13, 3, col)

    def _update_accessories(self, lcd, mood, b_pct):
        if mood != self._last_mood:
            lcd.blit(MOUTH_X, MOUTH_Y, MOUTH_W, MOUTH_H, self._get_dimmed(self.mouths[mood], b_pct))
            self._draw_veins(lcd, mood == "battle")
            if mood in ("happy", "love"):
                ck = self._get_dimmed(self.cheek_ice, b_pct)
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

        self._update_accessories(lcd, "normal", b_pct)
        self._update_hud(lcd, st)
        eye = self._get_dimmed(self.eye_bya, b_pct)
        for idx in (0, 1, 2, 3):
            m = MASKS_OPEN[idx]
            blit_masked_2d(self.work_l, eye, m, BYA_RIMS[1], 0, 0)
            blit_masked_2d(self.work_r, eye, m, BYA_RIMS[1], 0, 0)
            lcd.blit(LEFT_X, EYE_Y, EYE_W, EYE_H, self.work_l)
            lcd.blit(RIGHT_X, EYE_Y, EYE_W, EYE_H, self.work_r)
            time.sleep(0.024)

    def update(self, lcd, state=None):
        st = state or {}
        mood = self._resolve_mood(st)
        b_pct = effective_brightness(st)
        rim = BYA_RIMS[(0, 1, 2, 1)[(self.tick // 6) % 4]]
        eye = self._get_dimmed(self.eye_small if mood == "surprised" else self.eye_bya, b_pct)

        self._update_hud(lcd, st)
        self._update_accessories(lcd, mood, b_pct)

        if st.get("powerup"):
            st["powerup"] = False
            self._draw_veins(lcd, True)
            self._do_powerup(lcd, eye, eye, WHITE, WHITE, BYA_PEARL)

        if st.get("blink"):
            st["blink"] = False
            if mood not in ("happy", "love"):
                self._do_blink(lcd, eye, eye, rim, rim, double=False)

        self._step_gaze(st, mood)

        if mood == "happy":
            hb = self._get_dimmed(self.happy_ice, b_pct)
            lcd.blit(LEFT_X, EYE_Y, EYE_W, EYE_H, hb)
            lcd.blit(RIGHT_X, EYE_Y, EYE_W, EYE_H, hb)
        elif mood == "love":
            lb = self._get_dimmed(self.love_ice[(self.tick // 4) % 2], b_pct)
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
