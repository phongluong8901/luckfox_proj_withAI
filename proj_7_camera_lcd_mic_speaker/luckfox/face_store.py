import json
import os
import threading

DEFAULT_DB_PATH = "/root/npu_rt/faces_db.json"
DEFAULT_THRESH = float(os.environ.get("FACE_MATCH_THRESH", "0.45"))


def cosine_sim(a: list[float], b: list[float]) -> float:
  if not a or len(a) != len(b):
    return 0.0
  return sum(float(x) * float(y) for x, y in zip(a, b))


class FaceStore:
  def __init__(self, db_path: str = DEFAULT_DB_PATH, thresh: float = DEFAULT_THRESH):
    self.db_path = db_path
    self.thresh = thresh
    self.lock = threading.Lock()
    self.db: dict[str, list[float]] = self._load()
    self.last_emb: list[float] | None = None

  def _load(self) -> dict[str, list[float]]:
    if not os.path.exists(self.db_path):
      return {}
    try:
      with open(self.db_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
      if isinstance(raw, dict):
        out = {}
        for k, v in raw.items():
          if isinstance(v, list) and v:
            out[str(k)] = [float(x) for x in v]
        return out
    except Exception:
      pass
    return {}

  def _save(self):
    parent = os.path.dirname(self.db_path)
    if parent:
      os.makedirs(parent, exist_ok=True)
    tmp = self.db_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
      json.dump(self.db, f)
    os.replace(tmp, self.db_path)

  def names(self) -> list[str]:
    with self.lock:
      return list(self.db.keys())

  def set_last_emb(self, emb: list[float] | None):
    with self.lock:
      self.last_emb = [float(x) for x in emb] if emb else None

  def enroll(self, name: str) -> tuple[bool, str, list[str]]:
    clean = (name or "").strip()
    if not clean:
      return False, "Ten chu so huu khong duoc de trong", self.names()
    with self.lock:
      if not self.last_emb:
        return False, "Khong co embedding khuon mat o khung hinh hien tai", list(self.db.keys())
      self.db[clean] = list(self.last_emb)
      self._save()
      dim = len(self.last_emb)
      enrolled = list(self.db.keys())
    return True, f"Da luu chu so huu '{clean}' ({dim}-dim)", enrolled

  def clear(self) -> tuple[str, list[str]]:
    with self.lock:
      self.db.clear()
      self._save()
    return "Da xoa danh sach khuon mat", []

  def match(self, emb: list[float]) -> tuple[str, float, bool]:
    best_name = "Stranger"
    best_sim = 0.0
    with self.lock:
      for name, ref in self.db.items():
        sim = cosine_sim(emb, ref)
        if sim > best_sim:
          best_sim = sim
          best_name = name
    if not emb or best_sim < self.thresh:
      return "Stranger", best_sim, False
    return best_name, best_sim, True