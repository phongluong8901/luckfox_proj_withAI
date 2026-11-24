import base64
from collections import deque
import json
import os
import re
import ssl
import struct
import time
import urllib.error
import urllib.request
import wave

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_CHAT_HISTORY: deque[dict] = deque(maxlen=6)
_LAST_CALL_T = 0.0
_BACKOFF_UNTIL = 0.0
_MODEL_BACKOFF: dict[str, float] = {}


def _ssl_context() -> ssl.SSLContext:
  base_dir = os.path.dirname(os.path.abspath(__file__))
  for ca_path in (
      os.path.join(base_dir, "cacert.pem"),
      "/etc/ssl/certs/ca-certificates.crt",
      "/etc/ssl/cert.pem",
  ):
    if os.path.isfile(ca_path):
      return ssl.create_default_context(cafile=ca_path)
  return ssl.create_default_context()


def _api_key() -> str:
  return os.environ.get("GEMINI_API_KEY", "").strip()


def _chat_model() -> str:
  return os.environ.get("GEMINI_MODEL", "gemini-3.5-flash").strip() or "gemini-3.5-flash"


def _candidate_models() -> list[str]:
  raw = [_chat_model(), "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
  out: list[str] = []
  for m in raw:
    if m and m not in out:
      out.append(m)
  return out


def _tts_model() -> str:
  return (
      os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts").strip()
      or "gemini-2.5-flash-preview-tts"
  )


def _tts_voice() -> str:
  return os.environ.get("GEMINI_VOICE", "Aoede").strip() or "Aoede"


def clear_history():
  _CHAT_HISTORY.clear()


def is_backoff_active() -> float:
  rem = _BACKOFF_UNTIL - time.perf_counter()
  return rem if rem > 0 else 0.0


def is_configured() -> bool:
  k = _api_key()
  return bool(k and k != "your_gemini_api_key_here")


def _post_json(url: str, payload: dict, timeout_s: float = 20.0) -> dict:
  body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
  req = urllib.request.Request(
      url,
      data=body,
      headers={"Content-Type": "application/json"},
      method="POST",
  )
  with urllib.request.urlopen(req, timeout=timeout_s, context=_ssl_context()) as resp:
    return json.loads(resp.read().decode("utf-8", errors="ignore"))


def _parse_reply_tags(raw_reply: str) -> dict:
  reply = (raw_reply or "").strip()

  heard = ""
  m_q = re.search(r"<<\s*Q\s*:\s*(.*?)>>", reply, re.S)
  if m_q:
    heard = m_q.group(1).strip()
    reply = (reply[: m_q.start()] + reply[m_q.end() :]).strip()

  action_scene = ""
  m_sc = re.search(
      r"<<\s*SCENE\s*:\s*(auto|idle|happy|curious|drunk|fly|love|cool|sleep|angry)\s*>>",
      reply,
      re.I,
  )
  if m_sc:
    action_scene = m_sc.group(1).lower()
    reply = (reply[: m_sc.start()] + reply[m_sc.end() :]).strip()

  action_vol = None
  m_vol = re.search(r"<<\s*VOL\s*:\s*(\d+)\s*>>", reply, re.I)
  if m_vol:
    action_vol = max(10, min(60, int(m_vol.group(1))))
    reply = (reply[: m_vol.start()] + reply[m_vol.end() :]).strip()

  ignored = "[IGNORE]" in reply
  wake_only = "[WAKE_ACK]" in reply
  check_face = "[CHECK_FACE]" in reply
  for tok in ("[IGNORE]", "[WAKE_ACK]", "[CHECK_FACE]"):
    reply = reply.replace(tok, "")
  reply = re.sub(r"[*_`#]+", "", reply).strip()

  return {
      "reply": reply,
      "heard": heard,
      "scene": action_scene,
      "vol": action_vol,
      "check_face": check_face,
      "ignored": ignored,
      "wake_only": wake_only,
  }


def ask_gemini(
    text: str = "",
    wav_bytes: bytes | None = None,
    owner_name: str = "Chủ nhân",
    require_wake: bool = False,
    wake_word: str = "hey luck",
    scene_hint: str = "",
    jpg_bytes: bytes | None = None,
) -> dict:
  global _LAST_CALL_T, _BACKOFF_UNTIL
  key = _api_key()
  if not is_configured():
    return {
        "ok": False,
        "text": "",
        "check_face": False,
        "ignored": False,
        "wake_only": False,
        "rate_limited": False,
        "scene": "",
        "vol": None,
        "model": _chat_model(),
        "err": "Chua cau hinh GEMINI_API_KEY trong file .env",
    }

  now = time.perf_counter()
  if now < _BACKOFF_UNTIL:
    wait_s = int(_BACKOFF_UNTIL - now) + 1
    return {
        "ok": False,
        "text": "",
        "check_face": False,
        "ignored": False,
        "wake_only": False,
        "rate_limited": True,
        "scene": "",
        "vol": None,
        "model": _chat_model(),
        "err": f"Tam nghi {wait_s}s tranh vuot quota Gemini (429)",
    }

  min_iv = float(os.environ.get("GEMINI_MIN_INTERVAL_S", "4.0"))
  if (now - _LAST_CALL_T) < min_iv and require_wake:
    return {
        "ok": True,
        "text": "",
        "check_face": False,
        "ignored": True,
        "wake_only": False,
        "rate_limited": False,
        "scene": "",
        "vol": None,
        "model": _chat_model(),
        "err": "",
    }
  _LAST_CALL_T = now

  sys_rules = [
      f"Ban la tro ly robot thong minh Luck tren Luckfox cua {owner_name}.",
      "Tra loi bang tieng Viet tu nhien, than thien, ngan gon 1 den 3 cau, khong dung markdown hay ky tu dac biet.",
      "Neu nguoi dung yeu cau kiem tra guong mat hoac soi mat, hay chen [CHECK_FACE] o dau.",
      "Neu nguoi dung bao doi bieu cam (vui ve, to mo, tuc gian, gia vo say ruou, bat con ruoi, tha tim, deo kinh ngau, di ngu, binh thuong, tu dong), "
      "hay kem dung 1 the <<SCENE:happy>>, <<SCENE:curious>>, <<SCENE:angry>>, <<SCENE:drunk>>, <<SCENE:fly>>, <<SCENE:love>>, <<SCENE:cool>>, <<SCENE:sleep>>, <<SCENE:idle>> hoac <<SCENE:auto>>.",
      "Neu nguoi dung bao chinh am luong loa (trong khoang 10 den 60), kem <<VOL:so>> (vi du <<VOL:40>>).",
  ]
  if scene_hint:
    sys_rules.append(f"Thong tin camera hien tai: {scene_hint}.")
  if require_wake and wav_bytes:
    sys_rules.append(
        f"QUAN TRONG: Day la ghi am tu mic. Nguoi dung phai noi tu khoa danh thuc '{wake_word}' "
        "(hoac nghe gan giong 'hey luc', 'hay luck', 'hey lock', 'hây lắc', 'ê luck'). "
        "Neu trong ghi am KHONG co tu khoa danh thuc hoac chi la tap am/tieng on, CHI TRA VE DUNG 1 TU: [IGNORE]. "
        "Neu nguoi dung chi goi 'Hey Luck' ma chua hoi gi them, CHI TRA VE: [WAKE_ACK]. "
        "Neu co 'Hey Luck' kem cau hoi, hay bo qua 'Hey Luck' va tra loi cau hoi do."
    )
  if wav_bytes:
    sys_rules.append(
        "Khi tra loi (khong phai [IGNORE]), hay bat dau bang <<Q: cau nguoi dung vua noi>> roi moi tra loi."
    )

  parts = [{"text": " ".join(sys_rules)}]
  if _CHAT_HISTORY:
    hist_txt = " | ".join(f"{h['role']}: {h['text']}" for h in _CHAT_HISTORY)
    parts.append({"text": f"Ngu canh hoi thoai gan day: {hist_txt}"})
  if text and text.strip():
    parts.append({"text": f"Cau hoi cua {owner_name}: {text.strip()}"})
  if jpg_bytes:
    parts.append({"text": "Day la anh hien tai tu camera cua robot:"})
    parts.append({
        "inlineData": {
            "mimeType": "image/jpeg",
            "data": base64.b64encode(jpg_bytes).decode("ascii"),
        }
    })
  if wav_bytes:
    parts.append({"text": "Hay nghe file ghi am sau va xu ly dung theo quy tac:"})
    parts.append({
        "inlineData": {
            "mimeType": "audio/wav",
            "data": base64.b64encode(wav_bytes).decode("ascii"),
        }
    })

  payload = {
      "contents": [{"parts": parts}],
      "tools": [{"googleSearch": {}}],
      "generationConfig": {"temperature": 0.4, "maxOutputTokens": 240},
  }

  last_err = ""
  saw_429 = False
  for model_name in _candidate_models():
    if time.perf_counter() < _MODEL_BACKOFF.get(model_name, 0.0):
      saw_429 = True
      continue
    url = f"{GEMINI_BASE}/{model_name}:generateContent?key={key}"
    try:
      res = _post_json(url, payload, timeout_s=22.0)
      cands = res.get("candidates") or []
      if not cands:
        last_err = f"{model_name}: rong"
        continue
      out_parts = (cands[0].get("content") or {}).get("parts") or []
      raw_reply = " ".join(str(p.get("text", "")).strip() for p in out_parts if p.get("text")).strip()
      parsed = _parse_reply_tags(raw_reply)
      reply = parsed["reply"]
      heard = parsed["heard"]

      if parsed["ignored"]:
        return {"ok": True, "text": "", "check_face": False, "ignored": True, "wake_only": False, "rate_limited": False, "heard": heard, "scene": "", "vol": None, "model": model_name, "err": ""}
      if parsed["wake_only"]:
        return {"ok": True, "text": "Dạ, tôi đang nghe đây!", "check_face": False, "ignored": False, "wake_only": True, "rate_limited": False, "heard": heard, "scene": "", "vol": None, "model": model_name, "err": ""}

      if reply:
        if text and text.strip():
          _CHAT_HISTORY.append({"role": "User", "text": text.strip()[:120]})
        elif wav_bytes:
          _CHAT_HISTORY.append({"role": "User", "text": (heard or "(Cau hoi giong noi)")[:120]})
        _CHAT_HISTORY.append({"role": "Bot", "text": reply[:160]})

      return {
          "ok": bool(reply),
          "text": reply,
          "check_face": parsed["check_face"],
          "ignored": False,
          "wake_only": False,
          "rate_limited": False,
          "heard": heard,
          "scene": parsed["scene"],
          "vol": parsed["vol"],
          "model": model_name,
          "err": "",
      }
    except urllib.error.HTTPError as e:
      err_body = ""
      try:
        err_body = e.read().decode("utf-8", errors="ignore")[:180]
      except Exception:
        pass
      if e.code in (429, 404, 503):
        _MODEL_BACKOFF[model_name] = time.perf_counter() + (300.0 if e.code == 404 else 60.0)
        if e.code == 429:
          saw_429 = True
        last_err = f"{model_name} HTTP {e.code}"
        print(f"[GEMINI FALLBACK] {last_err}, trying next...", flush=True)
        continue
      return {"ok": False, "text": "", "check_face": False, "ignored": False, "wake_only": False, "rate_limited": False, "scene": "", "vol": None, "model": model_name, "err": f"HTTP {e.code}: {err_body}"}
    except Exception as e:
      last_err = str(e)
      continue

  if saw_429:
    _BACKOFF_UNTIL = time.perf_counter() + 45.0
    return {"ok": False, "text": "", "check_face": False, "ignored": False, "wake_only": False, "rate_limited": True, "scene": "", "vol": None, "model": _chat_model(), "err": "Cac model Gemini deu het quota (429), tam nghi 45s"}
  return {"ok": False, "text": "", "check_face": False, "ignored": False, "wake_only": False, "rate_limited": False, "scene": "", "vol": None, "model": _chat_model(), "err": last_err or "Loi goi Gemini"}


def tts_gemini(
    text: str,
    out_wav_path: str = "/dev/shm/gemini_reply.wav",
    peak_ratio: float = 0.58,
) -> bool:
  global _BACKOFF_UNTIL
  if os.environ.get("GEMINI_TTS", "1") != "1":
    return False
  if time.perf_counter() < _BACKOFF_UNTIL:
    return False
  key = _api_key()
  clean = (text or "").strip()
  if not is_configured() or not clean:
    return False

  payload = {
      "contents": [{"parts": [{"text": clean}]}],
      "generationConfig": {
          "responseModalities": ["AUDIO"],
          "speechConfig": {
              "voiceConfig": {
                  "prebuiltVoiceConfig": {"voiceName": _tts_voice()}
              }
          },
      },
  }
  url = f"{GEMINI_BASE}/{_tts_model()}:generateContent?key={key}"

  try:
    res = _post_json(url, payload, timeout_s=22.0)
    cands = res.get("candidates") or []
    if not cands:
      return False
    parts = (cands[0].get("content") or {}).get("parts") or []
    for p in parts:
      inline = p.get("inlineData") or p.get("inline_data")
      if not inline or not inline.get("data"):
        continue
      pcm = base64.b64decode(inline["data"])
      mime = str(inline.get("mimeType") or inline.get("mime_type") or "")
      m_rate = re.search(r"rate=(\d+)", mime)
      sample_rate = int(m_rate.group(1)) if m_rate else 24000

      n = len(pcm) // 2
      if n <= 0:
        return False
      samples = struct.unpack(f"<{n}h", pcm[: n * 2])
      max_abs = max(abs(s) for s in samples)
      if max_abs > 0:
        scale = (32767.0 * peak_ratio) / float(max_abs)
        samples = [max(-32767, min(32767, int(round(s * scale)))) for s in samples]
        pcm = struct.pack(f"<{n}h", *samples)

      tmp = out_wav_path + ".tmp"
      with wave.open(tmp, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
      os.replace(tmp, out_wav_path)
      return True
  except urllib.error.HTTPError as e:
    if e.code == 429:
      _MODEL_BACKOFF[_tts_model()] = time.perf_counter() + 60.0
    print(f"[GEMINI TTS ERR] HTTP {e.code}", flush=True)
  except Exception as e:
    print(f"[GEMINI TTS ERR] {e}", flush=True)
  return False
