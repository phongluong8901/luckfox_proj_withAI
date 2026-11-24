from collections import deque
import asyncio
import io
import json
import os
import socket
import struct
import sys
import threading
import time
import urllib.request
import wave
import cv2

try:
  import av
  import edge_tts
except ImportError:
  av = None
  edge_tts = None

try:
  from gtts import gTTS
except ImportError:
  gTTS = None

LUCKFOX_IP = os.environ.get("LUCKFOX_IP", "192.168.1.3")
LUCKFOX_PORT = int(os.environ.get("LUCKFOX_PORT", "9001"))
WEB_PORT = int(os.environ.get("WEB_PORT", "8080"))
VIDEO_SOURCE_RAW = os.environ.get("VIDEO_SOURCE", "0")
VIDEO_SOURCE = (
    int(VIDEO_SOURCE_RAW) if VIDEO_SOURCE_RAW.isdigit() else VIDEO_SOURCE_RAW
)
FRAME_W = int(os.environ.get("FRAME_W", os.environ.get("WIDTH", "320")))
FRAME_H = int(os.environ.get("FRAME_H", os.environ.get("HEIGHT", "240")))
JPEG_QUALITY = int(os.environ.get("JPEG_QUALITY", "55"))
TARGET_FPS = float(os.environ.get("TARGET_FPS", "30"))


def _calc_fps(ts_win: deque[float]) -> float:
  if len(ts_win) < 2 or ts_win[-1] <= ts_win[0]:
    return 0.0
  return (len(ts_win) - 1) / (ts_win[-1] - ts_win[0])


def open_capture(source):
  is_cam = isinstance(source, int)
  cap = None
  if is_cam and sys.platform == "win32":
    cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
    if not cap.isOpened():
      cap.release()
      cap = None
  if cap is None:
    cap = cv2.VideoCapture(source)
  if not cap.isOpened():
    raise RuntimeError(f"Cannot open video source: {source}")

  if is_cam:
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
    cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

  return cap, is_cam


def _synth_free_wav(text: str) -> bytes | None:
  if av is None or (edge_tts is None and gTTS is None):
    return None
  mp3_bytes = b""
  if edge_tts is not None:
    try:
      async def _run():
        comm = edge_tts.Communicate(text, "vi-VN-HoaiMyNeural")
        buf = bytearray()
        async for ch in comm.stream():
          if ch.get("type") == "audio":
            buf.extend(ch["data"])
        return bytes(buf)
      mp3_bytes = asyncio.run(_run())
    except Exception:
      mp3_bytes = b""
  if not mp3_bytes and gTTS is not None:
    try:
      b = io.BytesIO()
      gTTS(text=text, lang="vi").write_to_fp(b)
      mp3_bytes = b.getvalue()
    except Exception:
      mp3_bytes = b""
  if not mp3_bytes:
    return None

  container = av.open(io.BytesIO(mp3_bytes), format="mp3")
  resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
  samples = []
  for frame in container.decode(audio=0):
    outs = resampler.resample(frame)
    for of in (outs if isinstance(outs, list) else [outs]):
      raw = bytes(of.planes[0])[: of.samples * 2]
      if raw:
        samples.extend(struct.unpack(f"<{len(raw) // 2}h", raw))
  for of in resampler.resample(None):
    raw = bytes(of.planes[0])[: of.samples * 2]
    if raw:
      samples.extend(struct.unpack(f"<{len(raw) // 2}h", raw))
  container.close()
  if not samples:
    return None
  max_abs = max(abs(s) for s in samples)
  if max_abs > 0:
    scale = (32767.0 * 0.60) / float(max_abs)
    samples = [max(-32767, min(32767, int(round(s * scale)))) for s in samples]
  pcm = struct.pack(f"<{len(samples)}h", *samples)
  out = io.BytesIO()
  with wave.open(out, "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(16000)
    wf.writeframes(pcm)
  return out.getvalue()


def _free_tts_loop(stop_event: threading.Event):
  if av is None or (edge_tts is None and gTTS is None):
    print(
        "[FREE TTS] Bo qua (muon loa Luckfox doc tieng Viet free, chay voi: "
        "--with edge-tts --with gtts --with av)",
        flush=True,
    )
    return
  print("[FREE TTS] San sang dich vu doc tieng Viet FREE (Edge-TTS + gTTS) -> loa Luckfox!", flush=True)
  base_url = f"http://{LUCKFOX_IP}:{WEB_PORT}"
  last_id = 0
  while not stop_event.is_set():
    try:
      with urllib.request.urlopen(f"{base_url}/api/tts_pending", timeout=2.0) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore"))
      req_id = int(data.get("id", 0) or 0)
      txt = str(data.get("text", "") or "").strip()
      if req_id > last_id and txt:
        last_id = req_id
        wav_bytes = _synth_free_wav(txt)
        if wav_bytes:
          req = urllib.request.Request(
              f"{base_url}/api/play_wav?id={req_id}",
              data=wav_bytes,
              headers={"Content-Type": "audio/wav"},
              method="POST",
          )
          with urllib.request.urlopen(req, timeout=15.0) as _:
            pass
    except Exception:
      pass
    time.sleep(0.25)


def main():
  cap, is_cam = open_capture(VIDEO_SOURCE)
  file_fps = TARGET_FPS
  if not is_cam:
    src_fps = cap.get(cv2.CAP_PROP_FPS)
    if src_fps and src_fps > 1.0:
      file_fps = src_fps

  cond = threading.Condition()
  stop_event = threading.Event()
  mailbox = {
      "seq": 0,
      "payload": None,
      "cam_ts": deque(maxlen=30),
  }

  def capture_loop():
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
    next_t = time.perf_counter()
    while not stop_event.is_set():
      ok, frame = cap.read()
      if not ok or frame is None:
        if not is_cam:
          cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
          continue
        time.sleep(0.01)
        continue

      if frame.shape[1] != FRAME_W or frame.shape[0] != FRAME_H:
        frame = cv2.resize(
            frame, (FRAME_W, FRAME_H), interpolation=cv2.INTER_AREA
        )

      ok_enc, buf = cv2.imencode(".jpg", frame, encode_params)
      if ok_enc:
        payload = buf.tobytes()
        now = time.perf_counter()
        with cond:
          mailbox["seq"] += 1
          mailbox["payload"] = payload
          mailbox["cam_ts"].append(now)
          cond.notify()

      if not is_cam and file_fps > 0:
        next_t += 1.0 / file_fps
        sleep_s = next_t - time.perf_counter()
        if sleep_s > 0:
          time.sleep(sleep_s)
        else:
          next_t = time.perf_counter()

  cap_thread = threading.Thread(target=capture_loop, daemon=True)
  cap_thread.start()
  tts_thread = threading.Thread(target=_free_tts_loop, args=(stop_event,), daemon=True)
  tts_thread.start()

  last_sent_seq = 0
  sent = 0
  dropped = 0

  try:
    while not stop_event.is_set():
      sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      try:
        sock.settimeout(3.0)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
        sock.connect((LUCKFOX_IP, LUCKFOX_PORT))
        sock.settimeout(5.0)
        print(
            f"Da ket noi toi {LUCKFOX_IP}:{LUCKFOX_PORT} "
            f"(source={VIDEO_SOURCE}, {FRAME_W}x{FRAME_H}, Q={JPEG_QUALITY})",
            flush=True,
        )

        send_ts: deque[float] = deque(maxlen=30)
        size_win: deque[int] = deque(maxlen=30)

        while not stop_event.is_set():
          with cond:
            cond.wait_for(
                lambda: mailbox["seq"] != last_sent_seq or stop_event.is_set(),
                timeout=1.0,
            )
            if stop_event.is_set():
              break
            cur_seq = mailbox["seq"]
            if cur_seq == last_sent_seq or mailbox["payload"] is None:
              continue
            payload = mailbox["payload"]
            cam_fps = _calc_fps(mailbox["cam_ts"])

          dropped += max(0, cur_seq - last_sent_seq - 1)
          last_sent_seq = cur_seq

          header = struct.pack("!I", len(payload))
          sock.sendall(header + payload)

          now = time.perf_counter()
          send_ts.append(now)
          size_win.append(len(payload))
          sent += 1

          if sent % 30 == 0:
            send_fps = _calc_fps(send_ts)
            avg_kb = (sum(size_win) / len(size_win)) / 1024.0
            kbps = avg_kb * send_fps
            print(
                f"Sent={sent} | Cam FPS={cam_fps:.1f} | Send FPS={send_fps:.1f}"
                f" | Drop={dropped} | Avg={avg_kb:.1f}KB ({kbps:.0f}KB/s)",
                flush=True,
            )
      except (
          OSError,
          BrokenPipeError,
          ConnectionRefusedError,
          ConnectionResetError,
      ) as e:
        if stop_event.is_set():
          break
        print(f"[TCP] Mat ket noi ({e}), thu lai sau 1s...", flush=True)
        time.sleep(1.0)
      finally:
        try:
          sock.close()
        except OSError:
          pass
  except KeyboardInterrupt:
    print("\nDung stream.", flush=True)
  finally:
    stop_event.set()
    with cond:
      cond.notify_all()
    cap_thread.join(timeout=2.0)
    cap.release()


if __name__ == "__main__":
  main()