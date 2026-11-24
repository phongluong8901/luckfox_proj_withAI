from collections import deque
import json
import os
import threading
import time

from face_store import FaceStore
import gemini_client


def _clamp_conf(val: float) -> float:
  return max(0.15, min(0.95, float(val)))


class SharedState:
  def __init__(self):
    self.running = True
    self.cond = threading.Condition()
    self.latest_jpg: bytes | None = None
    self.latest_seq = 0
    self.cam_ts: deque[float] = deque(maxlen=30)

    self.faces = FaceStore()

    self.ui_lock = threading.Lock()
    self.ui_cond = threading.Condition(self.ui_lock)
    self.ui_jpeg: bytes | None = None
    self.ui_seq = 0

    self.conf_thresh = _clamp_conf(float(os.environ.get("YOLO_CONF", "0.35")))
    self.class_filter: set[str] = set()
    self.mask_enabled = True

    self.vision_lock = threading.Lock()
    self.vision_cond = threading.Condition(self.vision_lock)
    self.vision_events: deque[dict] = deque(maxlen=4)

    self.speak_lock = threading.Lock()
    self.speak_cond = threading.Condition(self.speak_lock)
    self.speak_queue: deque[str] = deque(maxlen=8)

    self.chat_lock = threading.Lock()
    self.chat_cond = threading.Condition(self.chat_lock)
    self.chat_queue: deque[dict] = deque(maxlen=4)

    self.chat_log: deque[dict] = deque(maxlen=12)

    self.tts_lock = threading.Lock()
    self.tts_cond = threading.Condition(self.tts_lock)
    self.tts_seq = 0
    self.tts_pending_text = ""
    self.tts_done_seq = 0

    self.owner_lock = threading.Lock()
    self.last_owner_ts = 0.0
    self.last_owner_name = ""
    self.owner_grace_s = float(os.environ.get("OWNER_GRACE_S", "15.0"))

    self.face_check_lock = threading.Lock()
    self.face_check_until = 0.0
    self.listen_until = 0.0
    self.manual_unlock_until = 0.0
    self.scene_revert_until = 0.0
    self.caption_until = 0.0
    self.bot_scene = "auto"
    self.last_person_seen_ts = time.perf_counter()
    self.idle_sleep_s = float(os.environ.get("IDLE_SLEEP_S", "60.0"))

    self.ui_status = {
        "fps": 0.0,
        "cap_fps": 0.0,
        "total_ms": 0.0,
        "npu_ms": 0.0,
        "dec_ms": 0.0,
        "post_ms": 0.0,
        "daemon_mode": "init",
        "decoder": "-",
        "model_size": "-",
        "has_seg": False,
        "has_face": False,
        "tft_ok": False,
        "gemini_ok": gemini_client.is_configured(),
        "mic_on": os.environ.get("ENABLE_MIC", "1") == "1",
        "bot_mood": "idle",
        "bot_scene": "auto",
        "display_state": "idle",
        "tft_mode": "emoji",
        "mask": True,
        "conf": round(self.conf_thresh, 2),
        "classes": [],
        "counts": {},
        "people": [],
        "owner_seen": False,
        "enrolled": self.faces.names(),
        "last_voice": "-",
        "last_audio_in": "-",
        "last_user_text": "-",
        "last_bot_reply": "-",
        "show_caption": False,
        "chat_log": [],
        "gemini_wait_until": 0,
        "tts_on": os.environ.get("GEMINI_TTS", "1") == "1",
        "volume": int(os.environ.get("AUDIO_MAX_VOL", "60")),
        "volume_max": int(os.environ.get("AUDIO_MAX_VOL", "60")),
        "mic_rms": 0,
        "mic_thresh": int(float(os.environ.get("MIC_VAD_THRESH", "1400"))),
        "mic_auto_vad": os.environ.get("MIC_AUTO_VAD", "0") == "1",
        "sys_notice": "",
        "owner_unlock_rem": 0,
        "cpu_temp_c": None,
        "ram_free_mb": None,
        "gemini_model": gemini_client._chat_model(),
        "seq": 0,
        "w": 320,
        "h": 240,
        "dets": [],
        "stdout": "Dang khoi dong Luckfox Chatbot + Vision...",
    }
    self.ui_status_json = json.dumps(
        self.ui_status, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")

  def mark_owner_seen(self, name: str):
    with self.owner_lock:
      self.last_owner_ts = time.perf_counter()
      self.last_owner_name = name or "Owner"

  def is_owner_verified(self) -> tuple[bool, str]:
    with self.ui_lock:
      if self.ui_status.get("owner_seen"):
        for p in self.ui_status.get("people") or []:
          if p.get("is_owner"):
            return True, str(p.get("name") or "Owner")
    now = time.perf_counter()
    with self.owner_lock:
      if self.last_owner_ts > 0 and (now - self.last_owner_ts) <= self.owner_grace_s:
        return True, self.last_owner_name or "Owner"
      if now < self.manual_unlock_until:
        names = self.faces.names()
        return True, (names[0] if names else "Owner")
    return False, ""

  def unlock_temp(self, duration_s: float = 300.0):
    with self.owner_lock:
      self.manual_unlock_until = time.perf_counter() + max(10.0, float(duration_s))
    self.update_ui(None, {"owner_unlock_rem": self.owner_unlock_rem()})

  def owner_unlock_rem(self) -> int:
    now = time.perf_counter()
    with self.owner_lock:
      rem_manual = max(0.0, self.manual_unlock_until - now)
      rem_face = max(0.0, (self.last_owner_ts + self.owner_grace_s) - now) if self.last_owner_ts > 0 else 0.0
    return int(max(rem_manual, rem_face))

  def sample_sys_health(self) -> dict:
    cpu_temp_c = None
    ram_free_mb = None
    try:
      with open("/sys/class/thermal/thermal_zone0/temp", "r", encoding="utf-8") as f:
        cpu_temp_c = round(int(f.read().strip()) / 1000.0, 1)
    except (OSError, ValueError):
      pass
    try:
      with open("/proc/meminfo", "r", encoding="utf-8") as f:
        for line in f:
          if line.startswith("MemAvailable:"):
            ram_free_mb = int(line.split()[1]) // 1024
            break
    except (OSError, ValueError, IndexError):
      pass
    return {"cpu_temp_c": cpu_temp_c, "ram_free_mb": ram_free_mb}

  def trigger_face_check(self, duration_s: float = 7.0):
    with self.face_check_lock:
      self.face_check_until = time.perf_counter() + max(2.0, float(duration_s))
    self.update_ui(None, {"tft_mode": "checking", "bot_mood": "checking"})

  def clear_face_check(self):
    with self.face_check_lock:
      self.face_check_until = 0.0
    self.update_ui(None, {"tft_mode": "emoji"})

  def is_face_check_active(self) -> bool:
    with self.face_check_lock:
      return time.perf_counter() < self.face_check_until

  def set_bot_mood(self, mood: str, extra: dict | None = None):
    payload = {"bot_mood": mood}
    if not self.is_face_check_active():
      payload["tft_mode"] = "emoji"
    if extra:
      payload.update(extra)
    self.update_ui(None, payload)

  def set_bot_scene(self, scene: str):
    clean = (scene or "auto").strip().lower()
    if clean not in (
        "auto", "idle", "happy", "curious", "drunk", "fly", "love", "cool", "sleep", "angry"
    ):
      clean = "auto"
    self.bot_scene = clean
    with self.face_check_lock:
      self.scene_revert_until = 0.0
    if clean == "auto":
      self.update_ui(None, {"bot_scene": "auto", "tft_mode": "emoji"})
    else:
      self.clear_face_check()
      self.update_ui(None, {"bot_scene": clean, "tft_mode": "emoji"})

  def trigger_pet(self, duration_s: float = 4.5):
    self.clear_face_check()
    self.bot_scene = "happy"
    with self.face_check_lock:
      self.scene_revert_until = time.perf_counter() + max(1.0, float(duration_s))
    self.update_ui(None, {"bot_scene": "happy", "tft_mode": "emoji"})

  def set_temp_scene(self, scene: str, duration_s: float = 8.0):
    clean = (scene or "auto").strip().lower()
    if clean not in (
        "auto", "idle", "happy", "curious", "drunk", "fly", "love", "cool", "sleep", "angry"
    ):
      clean = "auto"
    self.bot_scene = clean
    with self.face_check_lock:
      self.scene_revert_until = (
          time.perf_counter() + max(1.0, float(duration_s))
          if clean not in ("auto", "idle")
          else 0.0
      )
    self.update_ui(None, {"bot_scene": clean, "tft_mode": "emoji"})

  def mark_person_present(self, present: bool):
    if not present:
      return
    now = time.perf_counter()
    was_asleep = (now - self.last_person_seen_ts) >= self.idle_sleep_s
    self.last_person_seen_ts = now
    with self.ui_lock:
      cur_mood = self.ui_status.get("bot_mood", "idle")
    if was_asleep and self.bot_scene == "auto" and cur_mood == "idle":
      self.set_temp_scene("happy", 2.5)

  def set_sys_notice(self, text: str):
    self.update_ui(None, {"sys_notice": (text or "").strip()})

  def compute_display_state(self) -> str:
    if self.is_face_check_active():
      return "checking"
    cur_mood = self.ui_status.get("bot_mood", "idle")
    if cur_mood in ("listening", "thinking", "speaking", "denied", "owner"):
      return str(cur_mood)
    if self.bot_scene != "auto":
      return self.bot_scene
    if (time.perf_counter() - self.last_person_seen_ts) >= self.idle_sleep_s:
      return "sleep"
    return "idle"

  def check_scene_timers(self):
    expired = False
    with self.face_check_lock:
      if self.scene_revert_until > 0 and time.perf_counter() >= self.scene_revert_until:
        self.scene_revert_until = 0.0
        self.bot_scene = "auto"
        expired = True
    if expired:
      self.update_ui(None, {"bot_scene": "auto"})
    else:
      with self.ui_lock:
        cur_disp = self.ui_status.get("display_state", "idle")
      new_disp = self.compute_display_state()
      if cur_disp != new_disp:
        self.update_ui(None, {"display_state": new_disp})

  def is_caption_visible(self) -> bool:
    with self.face_check_lock:
      return time.perf_counter() < self.caption_until

  def start_active_listen(self, duration_s: float = 6.0):
    with self.face_check_lock:
      self.listen_until = time.perf_counter() + max(2.0, float(duration_s))

  def is_active_listen(self) -> bool:
    with self.face_check_lock:
      return time.perf_counter() < self.listen_until

  def clear_active_listen(self):
    with self.face_check_lock:
      self.listen_until = 0.0

  def add_chat_log(self, role: str, text: str):
    clean = (text or "").strip()
    if not clean:
      return
    self.chat_log.append({
        "role": role if role in ("user", "bot", "sys") else "sys",
        "text": clean[:240],
        "t": time.strftime("%H:%M"),
        "ts": time.time(),
    })
    self.update_ui(None, {"chat_log": list(self.chat_log)})

  def clear_chat_log(self):
    self.chat_log.clear()
    gemini_client.clear_history()
    self.update_ui(None, {"chat_log": [], "last_bot_reply": "-", "last_user_text": "-"})

  def request_pc_tts(self, text: str, timeout_s: float = 6.0) -> bool:
    clean = (text or "").strip()
    if not clean:
      return False
    with self.tts_cond:
      self.tts_seq += 1
      req_id = self.tts_seq
      self.tts_pending_text = clean
      self.tts_cond.notify_all()
      deadline = time.perf_counter() + max(1.0, float(timeout_s))
      while self.running and self.tts_done_seq < req_id:
        rem = deadline - time.perf_counter()
        if rem <= 0:
          if self.tts_seq == req_id:
            self.tts_pending_text = ""
          return False
        self.tts_cond.wait(timeout=rem)
      return self.tts_done_seq >= req_id

  def get_pending_tts(self) -> dict:
    with self.tts_lock:
      if self.tts_pending_text and self.tts_done_seq < self.tts_seq:
        return {"id": self.tts_seq, "text": self.tts_pending_text}
      return {"id": 0, "text": ""}

  def mark_tts_played(self, req_id: int):
    with self.tts_cond:
      if req_id > self.tts_done_seq:
        self.tts_done_seq = req_id
      if req_id >= self.tts_seq:
        self.tts_pending_text = ""
      self.tts_cond.notify_all()

  def submit_chat(self, source: str, text: str = "", wav_bytes: bytes | None = None):
    with self.chat_cond:
      self.chat_queue.append({
          "source": source,
          "text": (text or "").strip(),
          "wav_bytes": wav_bytes,
      })
      self.chat_cond.notify()

  def pop_chat(self, timeout: float = 0.2) -> dict | None:
    with self.chat_cond:
      self.chat_cond.wait_for(
          lambda: len(self.chat_queue) > 0 or not self.running,
          timeout=timeout,
      )
      if not self.running:
        return None
      if self.chat_queue:
        return self.chat_queue.popleft()
      return None

  def enroll_owner(self, name: str) -> tuple[bool, str, list[str]]:
    ok, msg, enrolled = self.faces.enroll(name)
    if ok:
      clean = (name or "").strip()
      self.mark_owner_seen(clean)
      self.update_ui(None, {"enrolled": enrolled})
      self.queue_speak(f"Da luu chu so huu {clean}")
    return ok, msg, enrolled

  def clear_owners(self) -> tuple[str, list[str]]:
    msg, enrolled = self.faces.clear()
    with self.owner_lock:
      self.last_owner_ts = 0.0
      self.last_owner_name = ""
    self.update_ui(None, {"enrolled": enrolled})
    self.queue_speak("Da xoa danh sach khuon mat")
    return msg, enrolled

  def emit_vision_event(self, ev: dict):
    with self.vision_cond:
      self.vision_events.append(ev)
      self.vision_cond.notify()

  def pop_vision_event(self, timeout: float = 0.05) -> dict | None:
    with self.vision_cond:
      self.vision_cond.wait_for(
          lambda: len(self.vision_events) > 0 or not self.running,
          timeout=timeout,
      )
      if not self.running:
        return None
      if self.vision_events:
        return self.vision_events.popleft()
      return None

  def queue_speak(self, msg: str):
    clean = (msg or "").strip()
    if not clean:
      return
    with self.speak_cond:
      self.speak_queue.append(clean)
      self.speak_cond.notify()

  def pop_speak(self, timeout: float = 0.5) -> str | None:
    with self.speak_cond:
      self.speak_cond.wait_for(
          lambda: len(self.speak_queue) > 0 or not self.running,
          timeout=timeout,
      )
      if not self.running:
        return None
      if self.speak_queue:
        return self.speak_queue.popleft()
      return None

  def push_frame(self, payload: bytes):
    now = time.perf_counter()
    with self.cond:
      self.latest_jpg = payload
      self.latest_seq += 1
      self.cam_ts.append(now)
      self.cond.notify()

  def update_ui(self, out_jpg: bytes | None, status: dict):
    if "last_bot_reply" in status:
      r = str(status.get("last_bot_reply") or "").strip()
      with self.face_check_lock:
        if r and r != "-":
          self.caption_until = time.perf_counter() + 9.0
        else:
          self.caption_until = 0.0
    with self.ui_cond:
      if out_jpg is not None:
        self.ui_jpeg = out_jpg
      self.ui_seq += 1
      self.ui_status.update(status)
      if "last_bot_reply" in status:
        r = str(status.get("last_bot_reply") or "").strip()
        self.ui_status["show_caption"] = bool(r and r != "-")
      self.ui_status["display_state"] = self.compute_display_state()
      self.ui_status_json = json.dumps(
          self.ui_status, ensure_ascii=False, separators=(",", ":")
      ).encode("utf-8")
      self.ui_cond.notify_all()

  def get_config(self) -> dict:
    with self.ui_lock:
      return {
          "conf": round(self.conf_thresh, 2),
          "classes": sorted(self.class_filter),
          "mask": self.mask_enabled,
          "enrolled": self.faces.names(),
      }

  def set_config(
      self,
      conf: float | None = None,
      classes: list[str] | None = None,
      mask: bool | None = None,
  ) -> dict:
    with self.ui_cond:
      if conf is not None:
        self.conf_thresh = _clamp_conf(conf)
      if classes is not None:
        self.class_filter = {
            str(c).strip() for c in classes if str(c).strip()
        }
      if mask is not None:
        self.mask_enabled = bool(mask)
      cfg = {
          "conf": round(self.conf_thresh, 2),
          "classes": sorted(self.class_filter),
          "mask": self.mask_enabled,
      }
      self.ui_seq += 1
      self.ui_status.update(cfg)
      if not self.mask_enabled:
        for d in self.ui_status.get("dets", []):
          if isinstance(d, dict):
            d.pop("mask", None)
      self.ui_status_json = json.dumps(
          self.ui_status, ensure_ascii=False, separators=(",", ":")
      ).encode("utf-8")
      self.ui_cond.notify_all()
      return {**cfg, "enrolled": self.faces.names()}

  def get_status_json(self) -> bytes:
    with self.ui_lock:
      return self.ui_status_json

  def wait_ui_update(
      self, last_ui_seq: int, timeout: float = 1.0
  ) -> tuple[int, bytes | None, bytes]:
    with self.ui_cond:
      self.ui_cond.wait_for(
          lambda: self.ui_seq != last_ui_seq or not self.running,
          timeout=timeout,
      )
      return self.ui_seq, self.ui_jpeg, self.ui_status_json

  def stop(self):
    self.running = False
    with self.cond:
      self.cond.notify_all()
    with self.ui_cond:
      self.ui_cond.notify_all()
    with self.vision_cond:
      self.vision_cond.notify_all()
    with self.speak_cond:
      self.speak_cond.notify_all()
    with self.chat_cond:
      self.chat_cond.notify_all()
    with self.tts_cond:
      self.tts_cond.notify_all()
