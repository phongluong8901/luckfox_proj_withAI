import os
import time

import audio_io
from audio_io import play_soft_chime, play_tag, play_wav_file
import gemini_client

OWNER_GREET_COOLDOWN_S = float(os.environ.get("OWNER_GREET_COOLDOWN_S", "600.0"))
STRANGER_COOLDOWN_S = float(os.environ.get("STRANGER_COOLDOWN_S", "30.0"))
AUTO_ANNOUNCE_OBJECTS = os.environ.get("AUTO_ANNOUNCE_OBJECTS", "0") == "1"
FACE_CHECK_HOLD_S = float(os.environ.get("FACE_CHECK_HOLD_S", "7.0"))
WAKE_WORD = os.environ.get("WAKE_WORD", "hey luck").strip() or "hey luck"
WAKE_LISTEN_S = float(os.environ.get("WAKE_LISTEN_S", "6.0"))
GEMINI_REPLY_WAV = "/dev/shm/gemini_reply.wav"


def _is_face_check_cmd(text: str) -> bool:
  low = (text or "").lower()
  return any(
      kw in low
      for kw in (
          "kiem tra guong mat",
          "kiểm tra gương mặt",
          "check face",
          "soi mat",
          "soi mặt",
          "nhan dien mat",
          "nhận diện mặt",
      )
  )


def _needs_vision(text: str) -> bool:
  low = (text or "").lower()
  return any(
      kw in low
      for kw in (
          "nhìn", "nhin", "thấy", "thay", "camera", "trên bàn", "tren ban",
          "cái gì", "cai gi", "vật gì", "vat gi", "màu gì", "mau gi", "đang cầm", "dang cam",
      )
  )


def _scene_summary(state) -> str:
  with state.ui_lock:
    counts = dict(state.ui_status.get("counts") or {})
    people = [p.get("name", "?") for p in (state.ui_status.get("people") or [])]
  parts = []
  if people:
    parts.append("Nguoi: " + ", ".join(people))
  if counts:
    parts.append("Vat the: " + ", ".join(f"{k}({v})" for k, v in list(counts.items())[:5]))
  return "; ".join(parts)


def _handle_chat(state, item: dict):
  source = item.get("source", "web")
  text = item.get("text", "")
  wav_bytes = item.get("wav_bytes")

  if text:
    state.update_ui(None, {"last_user_text": text})
    state.add_chat_log("user", text)
  elif source == "mic":
    state.update_ui(None, {"last_user_text": "(Ghi am tu mic Luckfox)"})

  # 1. Lenh kiem tra guong mat -> bat camera len man TFT ngay
  if _is_face_check_cmd(text):
    state.trigger_face_check(FACE_CHECK_HOLD_S)
    state.update_ui(None, {"last_bot_reply": "Dang bat camera kiem tra guong mat..."})
    play_tag("kiem tra guong mat")
    return

  # 2. Chi cho phep goi Gemini khi da xac thuc Chu so huu
  verified, owner_name = state.is_owner_verified()
  if not verified:
    # Siri-style: mic nen khong spam loa lien tuc; chi web hoac luc bam Nghe ngay moi bao
    if source in ("web", "mic_ptt") or state.is_active_listen():
      state.clear_active_listen()
      state.trigger_face_check(FACE_CHECK_HOLD_S)
      msg = "Chua xac thuc chu so huu. Hay nhin vao camera hoac bam 'Mo khoa 5p'!"
      state.add_chat_log("sys", msg)
      state.update_ui(None, {"last_bot_reply": msg, "last_voice": "Can xac thuc chu nhan"})
      play_tag("can xac thuc chu so huu")
    else:
      state.set_bot_mood("idle")
    return

  # 3. Neu tu mic (khong phai PTT) va chua trong cua so active listen -> bat buoc co wake word "Hey Luck"
  require_wake = (source == "mic") and (not state.is_active_listen())
  jpg_bytes = None
  if (source == "web" and _needs_vision(text)) or (source in ("mic", "mic_ptt") and not require_wake):
    with state.cond:
      jpg_bytes = state.latest_jpg

  state.set_bot_mood("thinking", {"last_bot_reply": "Gemini dang xu ly..."})
  res = gemini_client.ask_gemini(
      text=text,
      wav_bytes=wav_bytes,
      owner_name=owner_name,
      require_wake=require_wake,
      wake_word=WAKE_WORD,
      scene_hint=_scene_summary(state),
      jpg_bytes=jpg_bytes,
  )

  if res.get("ignored"):
    # Khong phai "Hey Luck" -> bo qua im lang, quay ve mat binh thuong
    state.set_bot_mood("idle")
    return

  heard = (res.get("heard") or "").strip()
  if heard and source in ("mic", "mic_ptt"):
    state.update_ui(None, {"last_user_text": heard})
    state.add_chat_log("user", heard)

  if res.get("wake_only"):
    state.start_active_listen(WAKE_LISTEN_S)
    reply = res.get("text") or "Da, toi dang nghe day!"
    state.set_bot_mood("speaking", {"last_bot_reply": reply, "last_voice": reply})
    if gemini_client.tts_gemini(reply, GEMINI_REPLY_WAV):
      play_wav_file(GEMINI_REPLY_WAV)
    else:
      play_tag("ready")
    state.set_bot_mood("listening")
    return

  if res.get("check_face"):
    state.trigger_face_check(FACE_CHECK_HOLD_S)
    state.update_ui(None, {"last_bot_reply": res.get("text") or "Dang kiem tra guong mat..."})
    play_tag("kiem tra guong mat")
    return

  if not res.get("ok"):
    err = res.get("err") or "Loi ket noi Gemini"
    print(f"[GEMINI ERR] {err}", flush=True)
    if res.get("rate_limited"):
      # Khong spam chat_log bang dem nguoc 429; chi cap nhat banner he thong
      state.set_sys_notice(err)
      state.update_ui(None, {"gemini_wait_until": time.time() + gemini_client.is_backoff_active()})
      state.set_bot_mood("idle")
    else:
      state.set_sys_notice(err)
      state.add_chat_log("sys", err)
      state.set_bot_mood("denied", {"last_bot_reply": err})
      time.sleep(1.2)
      state.set_bot_mood("idle")
    return

  state.clear_active_listen()
  reply = res["text"]
  if res.get("scene"):
    state.set_temp_scene(res["scene"], 8.0)
  extra_upd = {"last_bot_reply": reply, "last_voice": reply[:48], "sys_notice": ""}
  if res.get("vol") is not None:
    extra_upd["volume"] = audio_io.set_volume(res["vol"])
  if res.get("model"):
    extra_upd["gemini_model"] = res["model"]

  state.add_chat_log("bot", reply)
  print(f"[GEMINI] {owner_name} -> {reply}", flush=True)
  state.set_bot_mood("speaking", extra_upd)

  tts_provider = os.environ.get("TTS_PROVIDER", "free").strip().lower()
  spoke_ok = False
  if tts_provider != "gemini":
    spoke_ok = state.request_pc_tts(reply, timeout_s=6.0)
  if not spoke_ok and gemini_client.tts_gemini(reply, GEMINI_REPLY_WAV):
    play_wav_file(GEMINI_REPLY_WAV)
    spoke_ok = True
  if not spoke_ok:
    play_soft_chime()

  state.set_bot_mood("idle")


def voice_agent_loop(state):
  last_owner_greet_t = 0.0
  last_stranger_t = 0.0
  last_obj_t = 0.0
  last_health_t = 0.0
  was_checking = False
  was_listening = False

  while state.running:
    state.check_scene_timers()
    now_loop = time.perf_counter()
    if (now_loop - last_health_t) >= 4.0:
      last_health_t = now_loop
      health = state.sample_sys_health()
      health["owner_unlock_rem"] = state.owner_unlock_rem()
      health["show_caption"] = state.is_caption_visible()
      state.update_ui(None, health)

    chat_item = state.pop_chat(timeout=0.15)
    if chat_item:
      _handle_chat(state, chat_item)
      continue

    checking_now = state.is_face_check_active()
    if was_checking and not checking_now:
      state.clear_face_check()
      state.set_bot_mood("idle")
    was_checking = checking_now

    listening_now = state.is_active_listen()
    if was_listening and not listening_now and not checking_now:
      state.set_bot_mood("idle")
    was_listening = listening_now

    ev = state.pop_vision_event(timeout=0.05)
    if not ev:
      continue

    people = ev.get("people") or []
    counts = ev.get("counts") or {}
    now = time.perf_counter()

    if people:
      first = people[0]
      if first.get("is_owner"):
        owner_name = str(first.get("name", "Owner"))
        state.mark_owner_seen(owner_name)
        if checking_now:
          state.set_bot_mood("owner", {"last_bot_reply": f"Xin chao chu nhan {owner_name}!"})
        if (now - last_owner_greet_t) >= OWNER_GREET_COOLDOWN_S or checking_now:
          if (now - last_owner_greet_t) >= 8.0:
            last_owner_greet_t = now
            state.queue_speak(f"Chao chu so huu {owner_name}")
      else:
        if checking_now:
          state.set_bot_mood("denied", {"last_bot_reply": "Phat hien nguoi la!"})
          if (now - last_stranger_t) >= STRANGER_COOLDOWN_S:
            last_stranger_t = now
            state.queue_speak("Phat hien nguoi la")
    elif AUTO_ANNOUNCE_OBJECTS and (now - last_obj_t) >= 12.0:
      top_objs = [f"{k}({v})" for k, v in list(counts.items())[:2]]
      if top_objs:
        last_obj_t = now
        state.queue_speak("Vat the: " + ", ".join(top_objs))
