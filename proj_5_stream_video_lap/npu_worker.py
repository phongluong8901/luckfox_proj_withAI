from collections import deque
import json
import os
import struct
import subprocess
import threading
import time
from face_db import FaceDB

LD_PATH = "/oem/usr/lib:/usr/lib:/lib"
MODEL_DET_PATH = "/root/npu_rt/RetinaFace.rknn"
MODEL_REC_PATH = "/root/npu_rt/MobileFaceNet.rknn"
BIN_FACE_PATH = "/root/npu_rt/rknn_face_daemon"
BIN_LEGACY_PATH = "/root/npu_rt/rknn_retinaface_daemon"
TMP_IMG = "/dev/shm/frame.jpg"
STRANGER_COOLDOWN_S = float(os.environ.get("STRANGER_COOLDOWN_S", "3.0"))


class SharedState:
  def __init__(self, face_db: FaceDB | None = None):
    self.running = True
    self.cond = threading.Condition()
    self.latest_jpg = None
    self.latest_seq = 0

    self.face_db = face_db or FaceDB()

    self.ui_lock = threading.Lock()
    self.ui_cond = threading.Condition(self.ui_lock)
    self.ui_jpeg = None
    self.ui_seq = 0

    self.latest_emb: list[float] | None = None
    self.latest_emb_t: float = 0.0
    self.latest_emb_faces: int = 0
    self.stranger_jpeg: bytes | None = None
    self.last_stranger_save_t: float = 0.0
    self.stranger_seq: int = 0
    self.last_stranger_ts: str = ""
    self.alerts: deque[dict] = deque(maxlen=10)

    self.ui_status = {
        "fps": 0.0,
        "cap_fps": 0.0,
        "total_ms": 0.0,
        "npu_ms": 0.0,
        "det_ms": 0.0,
        "rec_ms": 0.0,
        "dec_ms": 0.0,
        "seq": 0,
        "w": 320,
        "h": 240,
        "faces": [],
        "rec_ready": False,
        "daemon_mode": "init",
        "known_count": 0,
        "stranger_count": 0,
        "db_count": self.face_db.count(),
        "threshold": self.face_db.get_threshold(),
        "last_stranger_ts": "",
        "stranger_seq": 0,
        "stdout": "Dang khoi dong NPU daemon...",
    }
    self.ui_status_json = json.dumps(
        self.ui_status, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")

  def push_frame(self, payload: bytes):
    with self.cond:
      self.latest_jpg = payload
      self.latest_seq += 1
      self.cond.notify()

  def update_ui(self, out_jpg: bytes | None, status: dict):
    with self.ui_cond:
      if out_jpg is not None:
        self.ui_jpeg = out_jpg
      self.ui_seq += 1
      self.ui_status.update(status)
      self.ui_status_json = json.dumps(
          self.ui_status, ensure_ascii=False, separators=(",", ":")
      ).encode("utf-8")
      self.ui_cond.notify_all()

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

  def set_latest_emb(self, emb: list[float] | None, face_count: int):
    with self.ui_lock:
      self.latest_emb = list(emb) if emb else None
      self.latest_emb_t = time.monotonic() if emb else 0.0
      self.latest_emb_faces = face_count

  def get_latest_emb(self) -> tuple[list[float] | None, float, int]:
    with self.ui_lock:
      if not self.latest_emb:
        return None, 1e9, self.latest_emb_faces
      age = time.monotonic() - self.latest_emb_t
      return list(self.latest_emb), age, self.latest_emb_faces

  def record_stranger(
      self, jpg_bytes: bytes, seq: int, stranger_count: int, best_sim: float
  ) -> tuple[str, int]:
    with self.ui_lock:
      now = time.monotonic()
      if (
          self.stranger_jpeg is None
          or (now - self.last_stranger_save_t) >= STRANGER_COOLDOWN_S
      ):
        self.stranger_jpeg = jpg_bytes
        self.last_stranger_save_t = now
        self.last_stranger_ts = time.strftime("%H:%M:%S")
        self.stranger_seq += 1
        self.alerts.appendleft({
            "time": self.last_stranger_ts,
            "seq": seq,
            "count": stranger_count,
            "sim": round(best_sim, 3),
        })
      return self.last_stranger_ts, self.stranger_seq

  def get_stranger_jpeg(self) -> bytes | None:
    with self.ui_lock:
      return self.stranger_jpeg

  def get_alerts(self) -> list[dict]:
    with self.ui_lock:
      return list(self.alerts)

  def sync_db_meta(self):
    self.update_ui(
        None,
        {
            "db_count": self.face_db.count(),
            "threshold": self.face_db.get_threshold(),
        },
    )

  def stop(self):
    self.running = False
    with self.cond:
      self.cond.notify_all()
    with self.ui_cond:
      self.ui_cond.notify_all()


def start_daemon(env) -> tuple[subprocess.Popen, bool, bool]:
  if os.path.isfile(BIN_FACE_PATH) and os.path.isfile(MODEL_REC_PATH):
    cmd = [BIN_FACE_PATH, MODEL_DET_PATH, MODEL_REC_PATH, "--bin"]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        bufsize=0,
    )
    ready = proc.stdout.readline().decode("utf-8", errors="ignore").strip()
    if ready == "READY_BIN":
      print(
          "[NPU] Face daemon READY (2-model + binary stdin zero-file)!",
          flush=True,
      )
      return proc, True, True
    if ready == "READY":
      print(
          "[NPU] Face daemon READY (2-model + /dev/shm mode)!",
          flush=True,
      )
      return proc, False, True
    err = proc.stderr.read().decode("utf-8", errors="ignore").strip()
    proc.terminate()
    raise RuntimeError(f"Face daemon init fail: {ready} | {err}")

  if not os.path.isfile(BIN_LEGACY_PATH):
    raise RuntimeError(
        f"Missing NPU binary: {BIN_FACE_PATH} or {BIN_LEGACY_PATH}"
    )

  proc = subprocess.Popen(
      [BIN_LEGACY_PATH, MODEL_DET_PATH],
      stdin=subprocess.PIPE,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      env=env,
      bufsize=0,
  )
  ready = proc.stdout.readline().decode("utf-8", errors="ignore").strip()
  if ready != "READY":
    err = proc.stderr.read().decode("utf-8", errors="ignore").strip()
    proc.terminate()
    raise RuntimeError(f"Daemon init fail: {ready} | {err}")
  print("[NPU] RetinaFace legacy daemon READY (detection only)!", flush=True)
  return proc, False, False


def worker_loop(state: SharedState):
  last_seq = 0
  processed = 0
  ts_win = deque(maxlen=30)

  env = os.environ.copy()
  env["LD_LIBRARY_PATH"] = (
      LD_PATH + ":" + env.get("LD_LIBRARY_PATH", "")
  ).strip(":")

  try:
    proc, is_binary_mode, rec_ready = start_daemon(env)
  except Exception as e:
    print(f"[NPU ERR] {e}", flush=True)
    state.update_ui(None, {"stdout": str(e), "daemon_mode": "err"})
    return

  daemon_mode = "binary" if is_binary_mode else "shm"
  state.update_ui(
      None,
      {
          "rec_ready": rec_ready,
          "daemon_mode": daemon_mode,
          "stdout": f"Daemon ready ({daemon_mode}, rec={rec_ready})",
      },
  )

  while state.running:
    with state.cond:
      state.cond.wait_for(
          lambda: state.latest_seq != last_seq or not state.running
      )
      if not state.running:
        break
      jpg_bytes = state.latest_jpg
      last_seq = state.latest_seq

    t0 = time.perf_counter()
    try:
      if is_binary_mode:
        proc.stdin.write(struct.pack(">I", len(jpg_bytes)) + jpg_bytes)
        proc.stdin.flush()
      else:
        with open(TMP_IMG, "wb") as f:
          f.write(jpg_bytes)
        proc.stdin.write((TMP_IMG + "\n").encode("utf-8"))
        proc.stdin.flush()

      line = proc.stdout.readline().decode("utf-8", errors="ignore").strip()
      data = json.loads(line) if line else {"faces": [], "npu_ms": 0.0}
    except Exception as e:
      data = {"err": str(e), "faces": [], "npu_ms": 0.0}

    now = time.perf_counter()
    tot_ms = (now - t0) * 1000.0
    if ts_win and (now - ts_win[-1] > 2.0):
      ts_win.clear()
    ts_win.append(now)
    if len(ts_win) >= 2 and ts_win[-1] > ts_win[0]:
      fps = (len(ts_win) - 1) / (ts_win[-1] - ts_win[0])
    else:
      fps = 0.0
    cap_fps = 1000.0 / tot_ms if tot_ms > 0 else 0.0

    raw_faces = data.get("faces", [])
    primary_emb = None
    best_area = -1.0
    known_count = 0
    stranger_count = 0
    max_stranger_sim = 0.0

    clean_faces = []
    for f in raw_faces:
      emb = f.pop("emb", None)
      box = f.get("box", [0, 0, 0, 0])
      if isinstance(emb, list) and emb and len(box) == 4:
        area = max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])
        if area > best_area:
          best_area = area
          primary_emb = emb

      if rec_ready and isinstance(emb, list) and emb:
        name, sim, is_known = state.face_db.match(emb)
        f["name"] = name
        f["sim"] = round(sim, 3)
        f["known"] = is_known
        if is_known:
          known_count += 1
        else:
          stranger_count += 1
          if sim > max_stranger_sim:
            max_stranger_sim = sim
      else:
        f["name"] = ""
        f["sim"] = 0.0
        f["known"] = None
      clean_faces.append(f)

    state.set_latest_emb(primary_emb, len(raw_faces))

    with state.ui_lock:
      last_stranger_ts = state.last_stranger_ts
      stranger_seq = state.stranger_seq

    if rec_ready and stranger_count > 0:
      last_stranger_ts, stranger_seq = state.record_stranger(
          jpg_bytes, last_seq, stranger_count, max_stranger_sim
      )

    npu_ms = float(data.get("npu_ms", 0.0))
    det_ms = float(data.get("det_ms", npu_ms))
    rec_ms = float(data.get("rec_ms", 0.0))
    dec_ms = float(data.get("dec_ms", 0.0))

    summary_data = {
        "npu_ms": npu_ms,
        "det_ms": det_ms,
        "rec_ms": rec_ms,
        "dec_ms": dec_ms,
        "w": data.get("w", 320),
        "h": data.get("h", 240),
        "faces": clean_faces,
    }
    if "err" in data:
      summary_data["err"] = data["err"]

    state.update_ui(
        jpg_bytes,
        {
            "fps": fps,
            "cap_fps": cap_fps,
            "total_ms": tot_ms,
            "npu_ms": npu_ms,
            "det_ms": det_ms,
            "rec_ms": rec_ms,
            "dec_ms": dec_ms,
            "seq": last_seq,
            "w": summary_data["w"],
            "h": summary_data["h"],
            "faces": clean_faces,
            "rec_ready": rec_ready,
            "daemon_mode": daemon_mode,
            "known_count": known_count,
            "stranger_count": stranger_count,
            "db_count": state.face_db.count(),
            "threshold": state.face_db.get_threshold(),
            "last_stranger_ts": last_stranger_ts,
            "stranger_seq": stranger_seq,
            "stdout": json.dumps(
                summary_data, ensure_ascii=False, separators=(",", ":")
            ),
        },
    )

    processed += 1
    if processed % 30 == 0:
      print(
          f"FPS={fps:4.1f} | cap={cap_fps:4.1f} | total={tot_ms:5.1f}ms"
          f" | det={det_ms:4.1f} rec={rec_ms:4.1f} | known={known_count}"
          f" stranger={stranger_count} | mode={daemon_mode} | seq={last_seq}",
          flush=True,
      )

  proc.terminate()
