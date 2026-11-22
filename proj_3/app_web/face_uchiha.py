import time
import math
from tft_driver import (
    BLACK, WHITE, rgb565_bytes,
    draw_circle, draw_ring, draw_capsule_h, draw_tomoe, draw_line_thick,
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

# --- Bang mau Uchiha Neon ---
SHAR_BG      = rgb565_bytes(22, 3, 6)
SHAR_GLOW    = rgb565_bytes(115, 8, 14)
SHAR_DARK    = rgb565_bytes(165, 10, 16)
SHAR_RED     = rgb565_bytes(235, 18, 28)
SHAR_BRIGHT  = rgb565_bytes(255, 65, 55)
SHAR_CORE    = rgb565_bytes(255, 195, 195)
SHAR_BLUSH   = rgb565_bytes(160, 28, 45)
SHAR_RIMS    = (rgb565_bytes(115, 12, 18), rgb565_bytes(175, 22, 32), rgb565_bytes(235, 42, 48))

RINN_BG      = rgb565_bytes(26, 15, 44)
RINN_DARK    = rgb565_bytes(115, 82, 168)
RINN_MID     = rgb565_bytes(172, 136, 224)
RINN_LIGHT   = rgb565_bytes(212, 184, 248)
RINN_RING    = rgb565_bytes(30, 16, 46)
RINN_CORE    = rgb565_bytes(240, 228, 255)
RINN_RIMS    = (rgb565_bytes(110, 82, 165), rgb565_bytes(168, 128, 232), rgb565_bytes(212, 178, 255))

MOUTH_LIGHT  = rgb565_bytes(235, 238, 245)
MOUTH_RED    = rgb565_bytes(245, 70, 80)
MOUTH_PURPLE = rgb565_bytes(198, 162, 245)

LED_W, LED_H, LED_X, LED_Y = 56, 6, 132, 18
AUTO_VARIANTS = ("sharingan", "mangekyo_itachi", "combo", "mangekyo_sasuke", "rinnegan", "mangekyo_obito")


class UchihaWatchFace(BaseRobotFace):
    """Mat Robot Emoji Uchiha: Sharingan, 3 loai Mangekyo (Itachi/Sasuke/Obito) & Rinnegan"""

    def __init__(self):
        super().__init__()
        self.auto_var_idx = 0

        # Pre-render 6 goc xoay muot cho tung kieu mat
        self.shar_frames = [self._render_sharingan(d) for d in range(0, 120, 20)]
        self.shar_small = self._render_sharingan(0, scale=0.68)
        self.ms_itachi = [self._render_ms_itachi(d) for d in range(0, 120, 20)]
        self.ms_sasuke = [self._render_ms_sasuke(d) for d in range(0, 60, 10)]
        self.ms_obito = [self._render_ms_obito(d) for d in range(0, 120, 20)]
        self.rinn_frame = self._render_rinnegan()
        self.rinn_small = self._render_rinnegan(scale=0.72)

        self.happy_red = render_happy_eye(SHAR_RED, SHAR_BRIGHT, SHAR_CORE)
        self.happy_purple = render_happy_eye(RINN_MID, RINN_LIGHT, RINN_CORE)
        self.love_red = render_love_eyes(SHAR_DARK, SHAR_BRIGHT, SHAR_CORE)
        self.love_purple = render_love_eyes(RINN_DARK, RINN_LIGHT, RINN_CORE)

        self.cheek_red = render_cheek(SHAR_BLUSH)
        self.cheek_purple = render_cheek(RINN_DARK)

        self.mouths = {}
        for m in ("normal", "battle", "happy", "love", "sleepy", "surprised"):
            col_r = MOUTH_LIGHT if m in ("normal", "sleepy") else MOUTH_RED
            col_p = MOUTH_LIGHT if m in ("normal", "sleepy") else MOUTH_PURPLE
            self.mouths[(m, "red")] = render_mouth(m, col_r)
            self.mouths[(m, "purple")] = render_mouth(m, col_p)

    def _add_catchlight(self, buf, cx, cy, core_col):
        draw_circle(buf, EYE_W, EYE_H, cx - 15, cy - 16, 6, WHITE)
        draw_circle(buf, EYE_W, EYE_H, cx - 6, cy - 22, 2, core_col)

    def _render_sharingan(self, rot_deg, scale=1.0):
        buf = bytearray(SHAR_BG * (EYE_W * EYE_H))
        cx, cy = EYE_W // 2, EYE_H // 2
        r = lambda v: max(2, int(v * scale))

        draw_circle(buf, EYE_W, EYE_H, cx, cy, r(46), SHAR_GLOW)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, r(42), BLACK)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, r(40), SHAR_DARK)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, r(36), SHAR_RED)
        draw_ring(buf, EYE_W, EYE_H, cx, cy, r(31), 2, SHAR_BRIGHT)
        draw_ring(buf, EYE_W, EYE_H, cx, cy, r(22), 2, BLACK)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, r(8), BLACK)

        for base in (90, 210, 330):
            draw_tomoe(buf, EYE_W, EYE_H, cx, cy, r(22), base + rot_deg, r(5), BLACK)

        self._add_catchlight(buf, cx, cy, SHAR_CORE)
        return buf

    def _render_ms_itachi(self, rot_deg):
        """Mangekyo Sharingan cua Itachi: 3 canh chong chong cong den ruc do"""
        buf = bytearray(SHAR_BG * (EYE_W * EYE_H))
        cx, cy = EYE_W // 2, EYE_H // 2
        draw_circle(buf, EYE_W, EYE_H, cx, cy, 46, SHAR_GLOW)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, 42, BLACK)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, 39, SHAR_RED)
        draw_ring(buf, EYE_W, EYE_H, cx, cy, 35, 2, SHAR_BRIGHT)

        # 3 canh quat cong dac trung Itachi
        for base in (0, 120, 240):
            for step in range(16):
                t = step / 15.0
                ang = math.radians(base + rot_deg + t * 72.0)
                dist = 10 + t * 27.0
                px = int(cx + dist * math.cos(ang))
                py = int(cy + dist * math.sin(ang))
                rad = max(2, int(9 * (1.0 - t * 0.72)))
                draw_circle(buf, EYE_W, EYE_H, px, py, rad, BLACK)

        # Tam den + cham do giua
        draw_circle(buf, EYE_W, EYE_H, cx, cy, 11, BLACK)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, 4, SHAR_BRIGHT)
        self._add_catchlight(buf, cx, cy, SHAR_CORE)
        return buf

    def _render_ms_sasuke(self, rot_deg):
        """Mangekyo Sharingan cua Sasuke: Ngoi sao 6 canh do tren nen den"""
        buf = bytearray(SHAR_BG * (EYE_W * EYE_H))
        cx, cy = EYE_W // 2, EYE_H // 2
        draw_circle(buf, EYE_W, EYE_H, cx, cy, 46, SHAR_GLOW)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, 42, SHAR_RED)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, 38, BLACK)

        # 3 canh elip do dan xen tao ngoi sao 6 canh
        for base in (0, 60, 120):
            rad_a = math.radians(base + rot_deg)
            ca, sa = math.cos(rad_a), math.sin(rad_a)
            for s in range(-32, 33, 2):
                # Chieu rong canh elip
                w = int(11 * math.sqrt(max(0.0, 1.0 - (s / 34.0) ** 2)))
                if w < 1:
                    continue
                px = int(cx + s * ca)
                py = int(cy + s * sa)
                draw_circle(buf, EYE_W, EYE_H, px, py, max(1, w // 2 + 1), SHAR_RED)
            # Duong vien den trong canh
            x0, y0 = int(cx - 28 * ca), int(cy - 28 * sa)
            x1, y1 = int(cx + 28 * ca), int(cy + 28 * sa)
            draw_line_thick(buf, EYE_W, EYE_H, x0, y0, x1, y1, 2, BLACK)

        draw_circle(buf, EYE_W, EYE_H, cx, cy, 7, SHAR_BRIGHT)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, 4, BLACK)
        self._add_catchlight(buf, cx, cy, SHAR_CORE)
        return buf

    def _render_ms_obito(self, rot_deg):
        """Mangekyo Sharingan cua Obito/Kakashi: 3 luoi Kamui xoay"""
        buf = bytearray(SHAR_BG * (EYE_W * EYE_H))
        cx, cy = EYE_W // 2, EYE_H // 2
        draw_circle(buf, EYE_W, EYE_H, cx, cy, 46, SHAR_GLOW)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, 42, BLACK)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, 39, SHAR_RED)
        draw_ring(buf, EYE_W, EYE_H, cx, cy, 16, 4, BLACK)

        # 3 luoi moc Kamui phat ra tu vong tam
        for base in (0, 120, 240):
            ang0 = math.radians(base + rot_deg)
            x0 = int(cx + 15 * math.cos(ang0))
            y0 = int(cy + 15 * math.sin(ang0))
            ang1 = math.radians(base + rot_deg + 16)
            x1 = int(cx + 35 * math.cos(ang1))
            y1 = int(cy + 35 * math.sin(ang1))
            draw_line_thick(buf, EYE_W, EYE_H, x0, y0, x1, y1, 4, BLACK)
            # Moc cong dau luoi
            ang2 = math.radians(base + rot_deg + 52)
            x2 = int(cx + 31 * math.cos(ang2))
            y2 = int(cy + 31 * math.sin(ang2))
            draw_line_thick(buf, EYE_W, EYE_H, x1, y1, x2, y2, 3, BLACK)

        draw_circle(buf, EYE_W, EYE_H, cx, cy, 6, SHAR_BRIGHT)
        self._add_catchlight(buf, cx, cy, SHAR_CORE)
        return buf

    def _render_rinnegan(self, scale=1.0):
        buf = bytearray(RINN_BG * (EYE_W * EYE_H))
        cx, cy = EYE_W // 2, EYE_H // 2
        r = lambda v: max(2, int(v * scale))

        draw_circle(buf, EYE_W, EYE_H, cx, cy, r(56), RINN_DARK)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, r(48), RINN_MID)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, r(38), RINN_LIGHT)
        for rad in (11, 20, 29, 38, 47):
            draw_ring(buf, EYE_W, EYE_H, cx, cy, r(rad), 2, RINN_RING)
        draw_circle(buf, EYE_W, EYE_H, cx, cy, r(4), BLACK)
        self._add_catchlight(buf, cx, cy, RINN_CORE)
        return buf

    def _draw_top_led(self, lcd, color):
        buf = bytearray(BLACK * (LED_W * LED_H))
        draw_capsule_h(buf, LED_W, LED_H, LED_W // 2, LED_H // 2, 20, 2, color)
        lcd.blit(LED_X, LED_Y, LED_W, LED_H, buf)

    def _get_pair(self, variant, mood):
        # Nhip tho cua vien neon (0 -> 1 -> 2 -> 1)
        breath = (0, 1, 2, 1)[(self.tick // 6) % 4]
        rim_r = SHAR_RIMS[breath]
        rim_p = RINN_RIMS[breath]

        # Khi ngac nhien -> dong tu thu nho lai
        if mood == "surprised":
            if variant == "rinnegan":
                return self.rinn_small, self.rinn_small, rim_p, rim_p, "purple"
            if variant == "combo":
                return self.shar_small, self.rinn_small, rim_r, rim_p, "red"
            return self.shar_small, self.shar_small, rim_r, rim_r, "red"

        if variant == "rinnegan":
            return self.rinn_frame, self.rinn_frame, rim_p, rim_p, "purple"
        if variant == "mangekyo_itachi":
            f = self.ms_itachi[self.frame_idx % len(self.ms_itachi)]
            return f, f, rim_r, rim_r, "red"
        if variant == "mangekyo_sasuke":
            f = self.ms_sasuke[self.frame_idx % len(self.ms_sasuke)]
            return f, f, rim_r, rim_r, "red"
        if variant == "mangekyo_obito":
            f = self.ms_obito[self.frame_idx % len(self.ms_obito)]
            return f, f, rim_r, rim_r, "red"
        if variant == "combo":
            f = self.shar_frames[self.frame_idx % len(self.shar_frames)]
            return f, self.rinn_frame, rim_r, rim_p, "red"

        f_l = self.shar_frames[self.frame_idx % len(self.shar_frames)]
        f_r = self.shar_frames[(-self.frame_idx) % len(self.shar_frames)]
        return f_l, f_r, rim_r, rim_r, "red"

    def _update_accessories(self, lcd, mood, accent, b_pct):
        if mood != self._last_mood or accent != self._last_accent:
            m_buf = self._get_dimmed(self.mouths[(mood, accent)], b_pct)
            lcd.blit(MOUTH_X, MOUTH_Y, MOUTH_W, MOUTH_H, m_buf)
            if mood in ("happy", "love"):
                cheek = self._get_dimmed(self.cheek_purple if accent == "purple" else self.cheek_red, b_pct)
                lcd.blit(CHEEK_LX, CHEEK_Y, CHEEK_W, CHEEK_H, cheek)
                lcd.blit(CHEEK_RX, CHEEK_Y, CHEEK_W, CHEEK_H, cheek)
            else:
                lcd.blit(CHEEK_LX, CHEEK_Y, CHEEK_W, CHEEK_H, CHEEK_OFF)
                lcd.blit(CHEEK_RX, CHEEK_Y, CHEEK_W, CHEEK_H, CHEEK_OFF)
            self._draw_top_led(lcd, RINN_MID if accent == "purple" else SHAR_RED)
            self._last_mood = mood
            self._last_accent = accent

    def on_enter(self, lcd, state=None):
        st = state or {}
        lcd.fill_screen(BLACK)
        self._last_mood = None
        self._last_accent = None
        self._last_hud_on = None
        self.gaze_dx = self.gaze_dy = self.gaze_tx = self.gaze_ty = 0
        b_pct = effective_brightness(st)

        variant = st.get("variant", "auto")
        if variant == "auto":
            variant = AUTO_VARIANTS[self.auto_var_idx]
        fl, fr, rim_l, rim_r, accent = self._get_pair(variant, "normal")
        fl, fr = self._get_dimmed(fl, b_pct), self._get_dimmed(fr, b_pct)
        self._update_accessories(lcd, "normal", accent, b_pct)
        self._update_hud(lcd, st)

        for idx in (0, 1, 2, 3):
            m = MASKS_OPEN[idx]
            blit_masked_2d(self.work_l, fl, m, rim_l, 0, 0)
            blit_masked_2d(self.work_r, fr, m, rim_r, 0, 0)
            lcd.blit(LEFT_X, EYE_Y, EYE_W, EYE_H, self.work_l)
            lcd.blit(RIGHT_X, EYE_Y, EYE_W, EYE_H, self.work_r)
            time.sleep(0.024)

    def update(self, lcd, state=None):
        st = state or {}
        mood = self._resolve_mood(st)
        req_var = st.get("variant", "auto")
        # Tu dong bung Mangekyo Itachi khi o che do Battle voi variant=auto
        if req_var == "auto":
            variant = "mangekyo_itachi" if mood == "battle" else AUTO_VARIANTS[self.auto_var_idx]
        else:
            variant = req_var

        b_pct = effective_brightness(st)
        fl, fr, rim_l, rim_r, accent = self._get_pair(variant, mood)
        fl, fr = self._get_dimmed(fl, b_pct), self._get_dimmed(fr, b_pct)

        self._update_hud(lcd, st)
        self._update_accessories(lcd, mood, accent, b_pct)

        # Kich hoat Nhan Thuat (Power-Up): rung + chop sang + bung Mangekyo
        if st.get("powerup"):
            st["powerup"] = False
            ms_f = self._get_dimmed(self.ms_itachi[0], b_pct)
            self._do_powerup(lcd, ms_f, ms_f, SHAR_BRIGHT, SHAR_BRIGHT, WHITE)
            if req_var == "auto":
                self.auto_var_idx = 1  # chuyen sang Mangekyo Itachi

        if st.get("blink"):
            st["blink"] = False
            if mood not in ("happy", "love"):
                self._do_blink(lcd, fl, fr, rim_l, rim_r, double=False)

        self._step_gaze(st, mood)

        if mood == "happy":
            hb = self._get_dimmed(self.happy_purple if accent == "purple" else self.happy_red, b_pct)
            lcd.blit(LEFT_X, EYE_Y, EYE_W, EYE_H, hb)
            lcd.blit(RIGHT_X, EYE_Y, EYE_W, EYE_H, hb)
        elif mood == "love":
            pair = self.love_purple if accent == "purple" else self.love_red
            lb = self._get_dimmed(pair[(self.tick // 4) % 2], b_pct)
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

            blit_masked_2d(self.work_l, fl, ml, rim_l, self.gaze_dx, self.gaze_dy)
            blit_masked_2d(self.work_r, fr, mr, rim_r, self.gaze_dx, self.gaze_dy)
            lcd.blit(LEFT_X, EYE_Y, EYE_W, EYE_H, self.work_l)
            lcd.blit(RIGHT_X, EYE_Y, EYE_W, EYE_H, self.work_r)

        self.frame_idx += 1
        self.tick += 1

        # Idle AI: nhin 2D ngau nhien + chop mat don/doi + doi bien the
        if not st.get("gaze_manual") and self.tick in (12, 24, 36):
            self.gaze_idx = (self.gaze_idx + 1) % len(self.GAZE_POINTS)
            self.gaze_tx, self.gaze_ty = self.GAZE_POINTS[self.gaze_idx]
        elif self.tick >= 46:
            if mood not in ("happy", "love"):
                self._do_blink(lcd, fl, fr, rim_l, rim_r, double=(self.auto_mood_idx % 3 == 0))
            if req_var == "auto":
                self.auto_var_idx = (self.auto_var_idx + 1) % len(AUTO_VARIANTS)
            if st.get("mood", "auto") == "auto":
                self.auto_mood_idx = (self.auto_mood_idx + 1) % len(self.AUTO_MOODS)
            self.tick = 0

        time.sleep(self._frame_delay(st))
