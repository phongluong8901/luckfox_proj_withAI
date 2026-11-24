from collections import deque
import os
import socket
import struct
import sys
import threading
import time
import cv2

LUCKFOX_IP = os.environ.get("LUCKFOX_IP", "192.168.1.3")
LUCKFOX_PORT = int(os.environ.get("LUCKFOX_PORT", "9001"))
VIDEO_SOURCE_RAW = os.environ.get("VIDEO_SOURCE", "0")
VIDEO_SOURCE = int(VIDEO_SOURCE_RAW) if VIDEO_SOURCE_RAW.isdigit() else VIDEO_SOURCE_RAW
WIDTH = int(os.environ.get("WIDTH", "320"))
HEIGHT = int(os.environ.get("HEIGHT", "240"))
JPEG_QUALITY = int(os.environ.get("JPEG_QUALITY", "50"))
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
    raise RuntimeError(f"Khong mo duoc nguon video: {source}")

  if is_cam:
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

  return cap, is_cam


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
      if not ok:
        if not is_cam:
          cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
          continue
        time.sleep(0.01)
        continue

      if frame.shape[1] != WIDTH or frame.shape[0] != HEIGHT:
        frame = cv2.resize(frame, (WIDTH, HEIGHT))

      ok, buf = cv2.imencode(".jpg", frame, encode_params)
      if ok:
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
            f"(source={VIDEO_SOURCE}, {WIDTH}x{HEIGHT}, Q={JPEG_QUALITY})"
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

          header = struct.pack(">I", len(payload))
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
                f" | Drop={dropped} | Avg={avg_kb:.1f}KB ({kbps:.0f}KB/s)"
            )
      except (
          OSError,
          BrokenPipeError,
          ConnectionRefusedError,
          ConnectionResetError,
      ) as e:
        if stop_event.is_set():
          break
        print(f"Mat ket noi ({e}) — thu ket noi lai sau 1s...")
        time.sleep(1.0)
      finally:
        try:
          sock.close()
        except OSError:
          pass
  except KeyboardInterrupt:
    pass
  finally:
    stop_event.set()
    with cond:
      cond.notify_all()
    cap_thread.join(timeout=2.0)
    cap.release()


if __name__ == "__main__":
  main()
