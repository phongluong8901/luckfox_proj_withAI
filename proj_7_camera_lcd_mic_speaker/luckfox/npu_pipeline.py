from collections import deque
import json
import os
import struct
import subprocess
import time

import tft_display

LD_PATH = "/oem/usr/lib:/usr/lib:/lib"
MODEL_PATH = "/root/npu_rt/yolov8n.rknn"
BIN_PATH = "/root/npu_rt/rknn_vision_daemon"
FALLBACK_BIN_PATH = "/root/npu_rt/rknn_yolo_daemon"
TMP_IMG = "/dev/shm/frame.jpg"
FACE_HOLD_S = float(os.environ.get("FACE_HOLD_S", "1.2"))


def _calc_fps(ts_win: deque[float]) -> float:
  if len(ts_win) < 2 or ts_win[-1] <= ts_win[0]:
    return 0.0
  return (len(ts_win) - 1) / (ts_win[-1] - ts_win[0])


def _resolve_bin() -> str:
  if os.path.isfile(BIN_PATH):
    return BIN_PATH
  return FALLBACK_BIN_PATH


def start_daemon(env) -> tuple[subprocess.Popen, bool]:
  bin_exe = _resolve_bin()
  proc = subprocess.Popen(
      [bin_exe, MODEL_PATH, "--bin"],
      stdin=subprocess.PIPE,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      env=env,
      bufsize=0,
  )
  ready = proc.stdout.readline().decode("utf-8", errors="ignore").strip()
  if ready == "READY_BIN":
    print(
        f"[NPU] Vision daemon READY ({os.path.basename(bin_exe)} --bin)!",
        flush=True,
    )
    return proc, True
  if ready == "READY":
    print(
        f"[NPU] Vision daemon READY ({os.path.basename(bin_exe)} /dev/shm)!",
        flush=True,
    )
    return proc, False
  err = proc.stderr.read().decode("utf-8", errors="ignore").strip()
  proc.terminate()
  raise RuntimeError(f"Daemon init fail: {ready} | {err}")


def worker_loop(state):
  last_seq = 0
  processed = 0
  ts_win = deque(maxlen=30)

  env = os.environ.copy()
  env["LD_LIBRARY_PATH"] = (
      LD_PATH + ":" + env.get("LD_LIBRARY_PATH", "")
  ).strip(":")
  env.setdefault("FACE_EVERY", "5")
  env.setdefault("TFT_EVERY", "3")
  env.setdefault("TFT_RGB565_PATH", "/dev/shm/tft_bg.rgb565")
  env.setdefault("TFT_W", str(tft_display.TFT_W))
  env.setdefault("TFT_H", str(tft_display.TFT_H))

  cached_people = []
  cached_owner_seen = False
  cached_face_ts = 0.0

  try:
    proc, is_binary_mode = start_daemon(env)
  except Exception as e:
    print(f"[NPU ERR] {e}", flush=True)
    state.update_ui(None, {"stdout": str(e), "daemon_mode": "err"})
    return

  daemon_mode = "binary" if is_binary_mode else "shm"
  state.update_ui(None, {"daemon_mode": daemon_mode})

  try:
    while state.running:
      with state.cond:
        state.cond.wait_for(
            lambda: state.latest_seq != last_seq or not state.running
        )
        if not state.running:
          break
        jpg_bytes = state.latest_jpg
        last_seq = state.latest_seq
        cam_fps = _calc_fps(state.cam_ts)

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
        if not line and proc.poll() is not None:
          data = {
              "err": f"daemon exited ({proc.returncode})",
              "dets": [],
              "npu_ms": 0.0,
          }
          time.sleep(0.5)
        else:
          data = json.loads(line) if line else {"dets": [], "npu_ms": 0.0}
      except Exception as e:
        data = {"err": str(e), "dets": [], "npu_ms": 0.0}
        if proc.poll() is not None:
          time.sleep(0.5)

      now = time.perf_counter()
      tot_ms = (now - t0) * 1000.0
      if ts_win and (now - ts_win[-1] > 2.0):
        ts_win.clear()
      ts_win.append(now)
      fps = _calc_fps(ts_win)

      with state.ui_lock:
        conf_th = state.conf_thresh
        allowed_classes = set(state.class_filter)
        mask_on = state.mask_enabled

      raw_dets = data.get("dets", [])
      dets = []
      summary_dets = []
      counts: dict[str, int] = {}
      person_boxes = []

      for d in raw_dets:
        if not isinstance(d, dict):
          continue
        score = float(d.get("score", 0.0))
        lbl = str(d.get("label", "obj"))
        box = d.get("box", [0, 0, 0, 0])
        if lbl == "person" and score >= conf_th:
          person_boxes.append(box)

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
            "box": box,
        }
        if mask_on and isinstance(d.get("mask"), dict):
          m = d["mask"]
          sd["mask"] = f"{m.get('w', 0)}x{m.get('h', 0)}"
        summary_dets.append(sd)

      # Nhanh Face + Embedding: chi chay khi co person va daemon tra ve faces/emb
      raw_faces = data.get("faces", [])
      face_ran = bool(data.get("face_ran", True))
      people_list = []
      owner_seen = False
      if person_boxes or raw_faces:
        if raw_faces and isinstance(raw_faces, list):
          if raw_faces[0].get("emb"):
            state.faces.set_last_emb(raw_faces[0]["emb"])
          for rf in raw_faces:
            if not isinstance(rf, dict):
              continue
            emb = rf.get("emb", [])
            name, sim, is_owner = state.faces.match(emb)
            if is_owner:
              owner_seen = True
            people_list.append({
                "name": name,
                "sim": round(sim, 3),
                "is_owner": is_owner,
                "box": rf.get("box", person_boxes[0] if person_boxes else [0, 0, 0, 0]),
            })
          cached_people = people_list
          cached_owner_seen = owner_seen
          cached_face_ts = now
        elif (not face_ran) and cached_people and (now - cached_face_ts) <= FACE_HOLD_S:
          people_list = cached_people
          owner_seen = cached_owner_seen
        else:
          cached_people = []
          cached_owner_seen = False
          state.faces.set_last_emb(None)
          for idx, pbox in enumerate(person_boxes):
            people_list.append({
                "name": f"Person #{idx + 1}",
                "sim": 0.0,
                "is_owner": False,
                "box": pbox,
            })
      else:
        cached_people = []
        cached_owner_seen = False
        state.faces.set_last_emb(None)

      sorted_counts = dict(
          sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
      )

      npu_ms = float(data.get("npu_ms", 0.0))
      dec_ms = float(data.get("dec_ms", 0.0))
      post_ms = float(data.get("post_ms", 0.0))
      decoder = str(data.get("decoder", "-"))
      has_seg = bool(data.get("has_seg", False))
      has_face = bool(data.get("has_face", False))
      mw = int(data.get("model_w", 0) or 0)
      mh = int(data.get("model_h", 0) or 0)
      model_size = f"{mw}x{mh}" if mw and mh else "-"

      summary_data = {
          "npu_ms": npu_ms,
          "dec_ms": dec_ms,
          "post_ms": post_ms,
          "decoder": decoder,
          "has_seg": has_seg,
          "has_face": has_face,
          "model": model_size,
          "w": data.get("w", 320),
          "h": data.get("h", 240),
          "people": [p["name"] for p in people_list],
          "dets": summary_dets,
      }
      if "err" in data:
        summary_data["err"] = data["err"]

      state.mark_person_present(bool(person_boxes or raw_faces))
      state.update_ui(
          jpg_bytes,
          {
              "fps": fps,
              "cap_fps": cam_fps,
              "total_ms": tot_ms,
              "npu_ms": npu_ms,
              "dec_ms": dec_ms,
              "post_ms": post_ms,
              "daemon_mode": daemon_mode,
              "decoder": decoder,
              "model_size": model_size,
              "has_seg": has_seg,
              "has_face": has_face,
              "mask": mask_on,
              "conf": round(conf_th, 2),
              "classes": sorted(allowed_classes),
              "counts": sorted_counts,
              "people": people_list,
              "owner_seen": owner_seen,
              "enrolled": state.faces.names(),
              "seq": last_seq,
              "w": summary_data["w"],
              "h": summary_data["h"],
              "dets": dets,
              "stdout": json.dumps(
                  summary_data, ensure_ascii=False, separators=(",", ":")
              ),
          },
      )

      if people_list or sorted_counts:
        state.emit_vision_event({
            "people": people_list,
            "owner_seen": owner_seen,
            "counts": sorted_counts,
        })

      processed += 1
      if processed % 30 == 0:
        lbls = ",".join(
            f"{d.get('label')}({d.get('score', 0):.2f})" for d in dets
        ) or "0"
        p_txt = ",".join(p["name"] for p in people_list) or "none"
        print(
            f"FPS={fps:4.1f} | cap={cam_fps:4.1f} | tot={tot_ms:5.1f}ms"
            f" | npu={npu_ms:5.1f}ms | people=[{p_txt}] | dets=[{lbls}]",
            flush=True,
        )
  finally:
    try:
      proc.terminate()
    except OSError:
      pass