from collections import deque
import math
import os
import shutil
import struct
import subprocess
import tempfile
import threading
import time

WAV_DIR = os.environ.get("WAV_DIR", "/root/npu_rt/wav")
ALSA_PLAY_DEV = os.environ.get("ALSA_PLAY_DEV", os.environ.get("ALSA_DEV", "default"))
ALSA_CAP_DEV = os.environ.get("ALSA_CAP_DEV", "")
ENABLE_MIC = os.environ.get("ENABLE_MIC", "1") == "1"
MIC_AUTO_VAD = os.environ.get("MIC_AUTO_VAD", "0") == "1"
AUDIO_MAX_VOL = max(10, min(100, int(os.environ.get("AUDIO_MAX_VOL", "60"))))
MIC_VAD_THRESH = float(os.environ.get("MIC_VAD_THRESH", "1400"))
MIC_COOLDOWN_S = float(os.environ.get("MIC_COOLDOWN_S", "5.0"))
TONE_PATH = "/dev/shm/alert_tone.wav"

_active_play_dev = ALSA_PLAY_DEV
_active_cap_dev = ALSA_CAP_DEV


def _apply_safe_volume(max_pct: int):
  """Cap ALSA playback volume to protect onboard speaker amp with 4-ohm 3W speaker."""
  if not shutil.which("amixer"):
    return
  candidates = ["DAC LINEOUT", "DAC", "Master", "Speaker", "Playback", "PCM"]
  try:
    out = subprocess.check_output(
        ["amixer", "scontrols"], stderr=subprocess.DEVNULL, timeout=2
    ).decode("utf-8", errors="ignore")
    found = []
    for line in out.splitlines():
      if "'" in line:
        parts = line.split("'")
        if len(parts) >= 2 and parts[1]:
          found.append(parts[1])
    if found:
      candidates = found
  except Exception:
    pass

  applied = []
  for ctrl in candidates:
    try:
      res = subprocess.run(
          ["amixer", "-q", "sset", ctrl, f"{max_pct}%"],
          stdout=subprocess.DEVNULL,
          stderr=subprocess.DEVNULL,
          timeout=2,
          check=False,
      )
      if res.returncode == 0:
        applied.append(ctrl)
    except Exception:
      pass
  print(
      f"[SPEAKER] Safe volume cap: {max_pct}% (controls={applied or 'none'})",
      flush=True,
  )


def set_volume(pct: int) -> int:
  vol = max(10, min(AUDIO_MAX_VOL, int(pct)))
  _apply_safe_volume(vol)
  return vol


def set_mic_thresh(val: int) -> int:
  global MIC_VAD_THRESH
  MIC_VAD_THRESH = float(max(300, min(8000, int(val))))
  return int(MIC_VAD_THRESH)


def set_mic_auto_vad(enabled: bool) -> bool:
  global MIC_AUTO_VAD
  MIC_AUTO_VAD = bool(enabled)
  return MIC_AUTO_VAD


def play_soft_chime():
  play_wav_file(_ensure_tone_wav(880.0, 0.07, 0.12))


def play_pet_chirp(blocking: bool = False):
  """Play a short adorable 2-note ascending EMO chirp without blocking HTTP."""
  sr = 16000
  pcm = bytearray()
  peak = int(32767 * 0.14)
  for freq, dur in ((680.0, 0.065), (1020.0, 0.075)):
    n = int(sr * dur)
    for i in range(n):
      env = min(1.0, i / 120.0, (n - i) / 120.0)
      pcm += struct.pack("<h", int(peak * env * math.sin(2.0 * math.pi * freq * i / sr)))
  out_dir = "/dev/shm" if os.path.isdir("/dev/shm") else tempfile.gettempdir()
  wav_path = os.path.join(out_dir, "pet_chirp.wav")
  header = struct.pack(
      "<4sI4s4sIHHIIHH4sI",
      b"RIFF", 36 + len(pcm), b"WAVE", b"fmt ", 16, 1, 1, sr, sr * 2, 2, 16, b"data", len(pcm),
  )
  with open(wav_path, "wb") as f:
    f.write(header + pcm)
  if blocking:
    play_wav_file(wav_path)
  else:
    threading.Thread(target=play_wav_file, args=(wav_path,), daemon=True).start()


def _ensure_tone_wav(freq_hz: float, dur_s: float, amp: float = 0.18) -> str:
  sample_rate = 16000
  n_samples = int(sample_rate * dur_s)
  pcm = bytearray()
  peak = int(32767 * max(0.02, min(0.30, amp)))
  for i in range(n_samples):
    env = 1.0
    if i < 120:
      env = i / 120.0
    elif i > n_samples - 120:
      env = max(0.0, (n_samples - i) / 120.0)
    val = int(peak * env * math.sin(2.0 * math.pi * freq_hz * i / sample_rate))
    pcm += struct.pack("<h", val)

  data_sz = len(pcm)
  riff_sz = 36 + data_sz
  header = struct.pack(
      "<4sI4s4sIHHIIHH4sI",
      b"RIFF",
      riff_sz,
      b"WAVE",
      b"fmt ",
      16,
      1,
      1,
      sample_rate,
      sample_rate * 2,
      2,
      16,
      b"data",
      data_sz,
  )
  with open(TONE_PATH, "wb") as f:
    f.write(header + pcm)
  return TONE_PATH


def _pick_wav(tag: str) -> str:
  low = tag.lower()
  if "da xoa" in low or "clear" in low:
    candidates = ["cleared.wav"]
    fallback_tone = (520.0, 0.14, 0.16)
  elif "kiem tra" in low or "check_face" in low:
    candidates = ["check_face.wav"]
    fallback_tone = (680.0, 0.16, 0.18)
  elif "xac thuc" in low or "need_owner" in low:
    candidates = ["need_owner.wav", "stranger.wav", "alert.wav"]
    fallback_tone = (880.0, 0.20, 0.18)
  elif "san sang" in low or "ready" in low:
    candidates = ["ready.wav"]
    fallback_tone = (640.0, 0.14, 0.16)
  elif "enroll" in low or "luu chu" in low:
    candidates = ["enrolled.wav", "ok.wav"]
    fallback_tone = (660.0, 0.14, 0.18)
  elif "chu so huu" in low or "owner" in low:
    candidates = ["owner.wav", "hello.wav"]
    fallback_tone = (740.0, 0.16, 0.18)
  elif "nguoi la" in low or "stranger" in low:
    candidates = ["stranger.wav", "alert.wav"]
    fallback_tone = (980.0, 0.22, 0.20)
  elif "vat the:" in low:
    cls_part = low.split("vat the:", 1)[1].split("(", 1)[0].strip()
    cls_norm = cls_part.replace(" ", "_").replace("-", "_")
    candidates = [f"obj_{cls_norm}.wav", "object.wav", "beep.wav"] if cls_norm else ["object.wav", "beep.wav"]
    fallback_tone = (580.0, 0.10, 0.15)
  else:
    candidates = ["object.wav", "beep.wav"]
    fallback_tone = (580.0, 0.10, 0.15)

  for name in candidates:
    p = os.path.join(WAV_DIR, name)
    if os.path.isfile(p):
      return p
  return _ensure_tone_wav(*fallback_tone)


def _run_aplay(dev: str, wav_file: str) -> int:
  cmd = ["aplay", "-q"]
  if dev and dev != "default":
    cmd += ["-D", dev]
  cmd.append(wav_file)
  res = subprocess.run(cmd, timeout=15, check=False)
  return res.returncode


def play_wav_file(wav_file: str):
  global _active_play_dev
  if not shutil.which("aplay") or not os.path.isfile(wav_file):
    return
  try:
    rc = _run_aplay(_active_play_dev, wav_file)
    if rc != 0 and _active_play_dev == "default":
      if _run_aplay("plughw:0,0", wav_file) == 0:
        _active_play_dev = "plughw:0,0"
        print("[SPEAKER] Auto-switched ALSA device to plughw:0,0", flush=True)
  except Exception:
    pass


def play_tag(tag: str):
  play_wav_file(_pick_wav(tag))


def _pcm16_rms(pcm: bytes) -> float:
  """AC RMS (mean-subtracted) so ADC DC bias never triggers false speech."""
  n = len(pcm) // 2
  if n <= 0:
    return 0.0
  samples = struct.unpack(f"<{n}h", pcm[: n * 2])
  step = 4 if n >= 64 else 1
  vals = samples[::step]
  cnt = len(vals)
  if cnt <= 0:
    return 0.0
  mean = sum(vals) / float(cnt)
  sq = sum((v - mean) * (v - mean) for v in vals)
  return math.sqrt(sq / float(cnt))


def _pack_wav_16k(pcm: bytes) -> bytes:
  data_sz = len(pcm)
  header = struct.pack(
      "<4sI4s4sIHHIIHH4sI",
      b"RIFF",
      36 + data_sz,
      b"WAVE",
      b"fmt ",
      16,
      1,
      1,
      16000,
      32000,
      2,
      16,
      b"data",
      data_sz,
  )
  return header + pcm


def _read_exact_pipe(stream, size: int) -> bytes:
  buf = bytearray()
  while len(buf) < size:
    chunk = stream.read(size - len(buf))
    if not chunk:
      break
    buf.extend(chunk)
  return bytes(buf)


def _mic_loop(state):
  global _active_cap_dev
  if not ENABLE_MIC or not shutil.which("arecord"):
    state.update_ui(None, {"mic_on": False})
    return

  # 0.25s per block @ 16kHz 16-bit mono = 8000 bytes
  chunk_bytes = 8000
  pre_roll: deque[bytes] = deque(maxlen=2)
  print(f"[MIC] Continuous pipe listening (VAD={MIC_VAD_THRESH:.0f})", flush=True)
  state.update_ui(None, {"mic_on": True})

  while state.running:
    cmd = ["arecord", "-q", "-t", "raw", "-f", "S16_LE", "-r", "16000", "-c", "1"]
    if _active_cap_dev:
      cmd += ["-D", _active_cap_dev]
    try:
      proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except Exception as e:
      print(f"[MIC ERR] {e}", flush=True)
      time.sleep(1.0)
      continue

    got_any = False
    recording = False
    rec_chunks: list[bytes] = []
    rec_ptt = False
    silent_blocks = 0
    hot_blocks = 0
    calib_left = 8
    calib_sum = 0.0
    noise_floor = 250.0
    last_submit_t = 0.0
    last_ui_t = 0.0
    last_ui_rms = -1000.0

    try:
      while state.running:
        pcm = _read_exact_pipe(proc.stdout, chunk_bytes)
        if len(pcm) < chunk_bytes:
          break
        got_any = True

        with state.ui_lock:
          mood = state.ui_status.get("bot_mood", "idle")
        if mood in ("speaking", "thinking"):
          pre_roll.clear()
          recording = False
          rec_chunks.clear()
          hot_blocks = 0
          continue

        rms = _pcm16_rms(pcm)
        if calib_left > 0:
          calib_sum += rms
          calib_left -= 1
          if calib_left == 0:
            noise_floor = max(120.0, calib_sum / 8.0)
          pre_roll.append(pcm)
          continue

        ptt_active = state.is_active_listen()
        dyn_thresh = (
            max(250.0, noise_floor * 1.8)
            if ptt_active
            else max(MIC_VAD_THRESH, noise_floor * 2.2)
        )
        now_ui = time.perf_counter()
        if not recording and ((now_ui - last_ui_t) >= 0.8 or abs(rms - last_ui_rms) > 350.0):
          last_ui_t = now_ui
          last_ui_rms = rms
          state.update_ui(None, {
              "mic_rms": int(rms),
              "mic_thresh": int(dyn_thresh),
              "mic_auto_vad": MIC_AUTO_VAD,
              "last_audio_in": f"AC {rms:.0f} / {dyn_thresh:.0f}",
          })

        if not recording:
          pre_roll.append(pcm)
          if not ptt_active and not MIC_AUTO_VAD:
            hot_blocks = 0
            noise_floor = 0.95 * noise_floor + 0.05 * rms
            continue

          now_t = time.perf_counter()
          if not ptt_active and (now_t - last_submit_t) < MIC_COOLDOWN_S:
            hot_blocks = 0
            noise_floor = 0.95 * noise_floor + 0.05 * rms
            continue

          if rms >= dyn_thresh:
            hot_blocks += 1
            need_hot = 1 if ptt_active else 2
            if hot_blocks >= need_hot:
              recording = True
              rec_ptt = ptt_active
              rec_chunks = list(pre_roll)
              silent_blocks = 0
              hot_blocks = 0
              print(f"[MIC] Speech start (AC_RMS={rms:.0f}, th={dyn_thresh:.0f}, ptt={rec_ptt})", flush=True)
              state.set_bot_mood("listening", {"last_user_text": "(Dang nghe mic...)"})
            else:
              noise_floor = 0.99 * noise_floor + 0.01 * rms
          else:
            hot_blocks = 0
            noise_floor = 0.95 * noise_floor + 0.05 * rms
        else:
          rec_chunks.append(pcm)
          if rms < max(200.0, dyn_thresh * 0.65):
            silent_blocks += 1
          else:
            silent_blocks = 0

          if silent_blocks >= 3 or len(rec_chunks) >= 16:
            wav_bytes = _pack_wav_16k(b"".join(rec_chunks))
            rec_chunks.clear()
            pre_roll.clear()
            recording = False
            last_submit_t = time.perf_counter()
            state.submit_chat("mic_ptt" if rec_ptt else "mic", text="", wav_bytes=wav_bytes)
    finally:
      try:
        proc.terminate()
        proc.wait(timeout=1.0)
      except Exception:
        pass

    if not got_any and not _active_cap_dev:
      _active_cap_dev = "plughw:0,0"
      print("[MIC] Auto-switched capture device to plughw:0,0", flush=True)
    else:
      time.sleep(0.5)


def audio_io_loop(state):
  _apply_safe_volume(AUDIO_MAX_VOL)
  if os.path.isfile(os.path.join(WAV_DIR, "ready.wav")):
    play_tag("He thong san sang")
  if ENABLE_MIC:
    threading.Thread(target=_mic_loop, args=(state,), daemon=True).start()

  while state.running:
    tag = state.pop_speak(timeout=0.5)
    if not tag:
      continue
    state.update_ui(None, {"last_voice": tag})
    print(f"[SPEAKER] {tag}", flush=True)
    play_tag(tag)
    time.sleep(0.05)
