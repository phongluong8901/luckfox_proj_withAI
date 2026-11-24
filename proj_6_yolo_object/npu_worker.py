from collections import deque
import json
import os
import struct
import subprocess
import threading
import time

LD_PATH = "/oem/usr/lib:/usr/lib:/lib"
MODEL_PATH = "/root/npu_rt/yolov8n.rknn"
BIN_PATH = "/root/npu_rt/rknn_yolo_daemon"
TMP_IMG = "/dev/shm/frame.jpg"


def _clamp_conf(val: float) -> float:
  return max(0.20, min(0.90, float(val)))


class SharedState:
  def __init__(self):
    self.running = True
    self.cond = threading.Condition()
    self.latest_jpg = None
    self.latest_seq = 0

    self.ui_lock = threading.Lock()
    self.ui_cond = threading.Condition(self.ui_lock)
    self.ui_jpeg = None
    self.ui_seq = 0

    self.conf_thresh = _clamp_conf(float(os.environ.get("YOLO_CONF", "0.35")))
    self.class_filter: set[str] = set()
    self.mask_enabled = True

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
        "mask": True,
        "conf": round(self.conf_thresh, 2),
        "classes": [],
        "counts": {},
        "seq": 0,
        "w": 320,
        "h": 240,
        "dets": [],
        "stdout": "Dang khoi dong YOLOv8 NPU daemon...",
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

  def get_config(self) -> dict:
    with self.ui_lock:
      return {
          "conf": round(self.conf_thresh, 2),
          "classes": sorted(self.class_filter),
          "mask": self.mask_enabled,
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
      return cfg

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


def start_daemon(env) -> tuple[subprocess.Popen, bool]:
  proc = subprocess.Popen(
      [BIN_PATH, MODEL_PATH, "--bin"],
      stdin=subprocess.PIPE,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      env=env,
      bufsize=0,
  )
  ready = proc.stdout.readline().decode("utf-8", errors="ignore").strip()
  if ready == "READY_BIN":
    print(
        "[NPU] YOLOv8 zero-copy daemon READY (binary stdin zero-file)!",
        flush=True,
    )
    return proc, True
  if ready == "READY":
    print(
        "[NPU] YOLOv8 zero-copy daemon READY (/dev/shm mode)!",
        flush=True,
    )
    return proc, False
  err = proc.stderr.read().decode("utf-8", errors="ignore").strip()
  proc.terminate()
  raise RuntimeError(f"Daemon init fail: {ready} | {err}")


def worker_loop(state: SharedState):
  last_seq = 0
  processed = 0
  ts_win = deque(maxlen=30)

  env = os.environ.copy()
  env["LD_LIBRARY_PATH"] = (
      LD_PATH + ":" + env.get("LD_LIBRARY_PATH", "")
  ).strip(":")

  try:
    proc, is_binary_mode = start_daemon(env)
  except Exception as e:
    print(f"[NPU ERR] {e}", flush=True)
    state.update_ui(None, {"stdout": str(e), "daemon_mode": "err"})
    return

  daemon_mode = "binary" if is_binary_mode else "shm"
  state.update_ui(None, {"daemon_mode": daemon_mode})

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
      data = json.loads(line) if line else {"dets": [], "npu_ms": 0.0}
    except Exception as e:
      data = {"err": str(e), "dets": [], "npu_ms": 0.0}

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

    with state.ui_lock:
      conf_th = state.conf_thresh
      allowed_classes = set(state.class_filter)
      mask_on = state.mask_enabled

    raw_dets = data.get("dets", [])
    dets = []
    summary_dets = []
    counts: dict[str, int] = {}
    for d in raw_dets:
      score = float(d.get("score", 0.0))
      lbl = str(d.get("label", "obj"))
      if score < conf_th:
        continue
      if allowed_classes and lbl not in allowed_classes:
        continue
      if not mask_on:
        d.pop("mask", None)
      dets.append(d)
      counts[lbl] = counts.get(lbl, 0) + 1

      sd = {
          "label": lbl,
          "cls": d.get("cls", 0),
          "score": round(score, 3),
          "box": d.get("box", []),
      }
      if mask_on and isinstance(d.get("mask"), dict):
        m = d["mask"]
        sd["mask"] = f"{m.get('w', 0)}x{m.get('h', 0)}"
      summary_dets.append(sd)

    sorted_counts = dict(
        sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    )

    npu_ms = float(data.get("npu_ms", 0.0))
    dec_ms = float(data.get("dec_ms", 0.0))
    post_ms = float(data.get("post_ms", 0.0))
    decoder = str(data.get("decoder", "-"))
    has_seg = bool(data.get("has_seg", False))
    mw = int(data.get("model_w", 0) or 0)
    mh = int(data.get("model_h", 0) or 0)
    model_size = f"{mw}x{mh}" if mw and mh else "-"

    summary_data = {
        "npu_ms": npu_ms,
        "dec_ms": dec_ms,
        "post_ms": post_ms,
        "decoder": decoder,
        "has_seg": has_seg,
        "model": model_size,
        "w": data.get("w", 320),
        "h": data.get("h", 240),
        "dets": summary_dets,
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
            "dec_ms": dec_ms,
            "post_ms": post_ms,
            "daemon_mode": daemon_mode,
            "decoder": decoder,
            "model_size": model_size,
            "has_seg": has_seg,
            "mask": mask_on,
            "conf": round(conf_th, 2),
            "classes": sorted(allowed_classes),
            "counts": sorted_counts,
            "seq": last_seq,
            "w": summary_data["w"],
            "h": summary_data["h"],
            "dets": dets,
            "stdout": json.dumps(
                summary_data, ensure_ascii=False, separators=(",", ":")
            ),
        },
    )

    processed += 1
    if processed % 30 == 0:
      lbls = ",".join(
          f"{d.get('label')}({d.get('score', 0):.2f})" for d in dets
      ) or "0"
      task_tag = "seg" if has_seg else "det"
      print(
          f"FPS={fps:4.1f} | cap={cap_fps:4.1f} | total={tot_ms:5.1f}ms"
          f" | npu={npu_ms:5.1f}ms | dec={dec_ms:4.1f} | post={post_ms:4.1f}"
          f" | {model_size}/{task_tag}/{decoder}/{daemon_mode}"
          f" | dets={len(dets)} [{lbls}] | seq={last_seq}",
          flush=True,
      )

  proc.terminate()
