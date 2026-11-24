import json
import math
from operator import mul
import os
import threading
import time

DB_PATH = os.environ.get("FACE_DB_PATH", "/root/npu_rt/faces_db.json")
DEFAULT_THRESHOLD = float(os.environ.get("FACE_THRESHOLD", "0.45"))
MAX_SAMPLES_PER_PERSON = 5


def _clamp_threshold(val: float) -> float:
  return max(0.20, min(0.90, float(val)))


def _l2_norm(vec: list[float]) -> list[float]:
  if not vec:
    return []
  sq = sum(v * v for v in vec)
  if sq <= 1e-18:
    return []
  inv = 1.0 / math.sqrt(sq)
  return [float(v) * inv for v in vec]


def _dot(a: list[float], b: list[float]) -> float:
  return float(sum(map(mul, a, b)))


def _compute_centroid(samples: list[list[float]]) -> list[float]:
  if not samples:
    return []
  dim = len(samples[0])
  acc = [0.0] * dim
  valid = 0
  for s in samples:
    if len(s) != dim:
      continue
    for i in range(dim):
      acc[i] += s[i]
    valid += 1
  if valid == 0:
    return []
  return _l2_norm(acc)


class FaceDB:
  def __init__(self, path: str = DB_PATH):
    self.path = path
    self._lock = threading.Lock()
    self._threshold = _clamp_threshold(DEFAULT_THRESHOLD)
    self._people: dict[str, dict] = {}
    self._load()

  def _load(self):
    if not os.path.isfile(self.path):
      return
    try:
      with open(self.path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    except Exception:
      return

    if isinstance(raw, dict):
      if "threshold" in raw:
        try:
          self._threshold = _clamp_threshold(raw["threshold"])
        except (TypeError, ValueError):
          pass
      people = raw.get("people", {})
      if isinstance(people, dict):
        for name, info in people.items():
          if not isinstance(name, str) or not isinstance(info, dict):
            continue
          clean_samples = []
          for s in info.get("samples", []):
            if isinstance(s, list) and s:
              normed = _l2_norm([float(x) for x in s])
              if normed:
                clean_samples.append(normed)
          clean_samples = clean_samples[-MAX_SAMPLES_PER_PERSON:]
          if not clean_samples:
            continue
          centroid = _compute_centroid(clean_samples)
          self._people[name] = {
              "samples": clean_samples,
              "centroid": centroid,
              "updated_at": str(info.get("updated_at", "")),
          }

  def _save_locked(self):
    parent = os.path.dirname(self.path)
    if parent:
      os.makedirs(parent, exist_ok=True)
    tmp_path = self.path + ".tmp"
    payload = {
        "threshold": self._threshold,
        "people": self._people,
    }
    with open(tmp_path, "w", encoding="utf-8") as f:
      json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp_path, self.path)

  def get_threshold(self) -> float:
    with self._lock:
      return self._threshold

  def set_threshold(self, val: float) -> float:
    with self._lock:
      self._threshold = _clamp_threshold(val)
      self._save_locked()
      return self._threshold

  def count(self) -> int:
    with self._lock:
      return len(self._people)

  def list_people(self) -> list[dict]:
    with self._lock:
      return [
          {
              "name": name,
              "samples": len(info["samples"]),
              "updated_at": info.get("updated_at", ""),
          }
          for name, info in sorted(self._people.items(), key=lambda kv: kv[0].lower())
      ]

  def register(self, name: str, embedding: list[float]) -> dict:
    clean_name = name.strip()
    if not (1 <= len(clean_name) <= 32):
      raise ValueError("Ten phai tu 1 den 32 ky tu")
    normed = _l2_norm([float(x) for x in embedding])
    if not normed:
      raise ValueError("Embedding khong hop le")

    with self._lock:
      entry = self._people.get(clean_name)
      if entry is None:
        samples = [normed]
      else:
        existing = entry.get("samples", [])
        if existing and len(existing[0]) != len(normed):
          samples = [normed]
        else:
          samples = (existing + [normed])[-MAX_SAMPLES_PER_PERSON:]

      centroid = _compute_centroid(samples)
      updated_at = time.strftime("%H:%M:%S")
      self._people[clean_name] = {
          "samples": samples,
          "centroid": centroid,
          "updated_at": updated_at,
      }
      self._save_locked()
      return {"name": clean_name, "samples": len(samples)}

  def delete(self, name: str) -> bool:
    clean_name = name.strip()
    with self._lock:
      if clean_name not in self._people:
        return False
      del self._people[clean_name]
      self._save_locked()
      return True

  def clear(self) -> None:
    with self._lock:
      self._people.clear()
      self._save_locked()

  def match(self, embedding: list[float]) -> tuple[str, float, bool]:
    normed = _l2_norm([float(x) for x in embedding])
    if not normed:
      return ("Nguoi la", 0.0, False)

    dim = len(normed)
    with self._lock:
      if not self._people:
        return ("Nguoi la", 0.0, False)

      best_name = "Nguoi la"
      best_sim = -1.0
      for name, info in self._people.items():
        centroid = info.get("centroid", [])
        if len(centroid) == dim:
          sim = _dot(normed, centroid)
          if sim > best_sim:
            best_sim = sim
            best_name = name
        for sample in info.get("samples", []):
          if len(sample) == dim:
            sim = _dot(normed, sample)
            if sim > best_sim:
              best_sim = sim
              best_name = name

      if best_sim < 0.0:
        best_sim = 0.0
      if best_sim >= self._threshold:
        return (best_name, best_sim, True)
      return ("Nguoi la", best_sim, False)
