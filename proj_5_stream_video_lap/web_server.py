import json
import os
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(BASE_DIR, "index.html")
WEB_FPS = float(os.environ.get("WEB_FPS", "8.0"))
SSE_MAX_FPS = float(os.environ.get("SSE_MAX_FPS", "20.0"))


class ReuseThreadingHTTPServer(ThreadingHTTPServer):
  allow_reuse_address = True
  daemon_threads = True


def _set_nodelay(sock):
  try:
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
  except OSError:
    pass


def make_handler(state):
  class WebHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
      return

    def _send_json(self, code: int, obj: dict):
      body = json.dumps(
          obj, ensure_ascii=False, separators=(",", ":")
      ).encode("utf-8")
      self.send_response(code)
      self.send_header("Content-Type", "application/json; charset=utf-8")
      self.send_header("Cache-Control", "no-store")
      self.send_header("Content-Length", str(len(body)))
      self.end_headers()
      self.wfile.write(body)

    def _read_json_body(self) -> dict:
      try:
        length = int(self.headers.get("Content-Length", "0"))
      except ValueError:
        return {}
      if length <= 0 or length > 65536:
        return {}
      raw = self.rfile.read(length)
      try:
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
      except Exception:
        return {}

    def do_GET(self):
      path = self.path.split("?", 1)[0]

      if path == "/":
        try:
          with open(HTML_PATH, "rb") as f:
            body = f.read()
        except OSError:
          body = b"<h1>Missing index.html</h1>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return

      if path == "/status":
        body = state.get_status_json()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return

      if path == "/api/faces":
        with state.ui_lock:
          rec_ready = bool(state.ui_status.get("rec_ready"))
        self._send_json(
            200,
            {
                "people": state.face_db.list_people(),
                "threshold": state.face_db.get_threshold(),
                "alerts": state.get_alerts(),
                "rec_ready": rec_ready,
            },
        )
        return

      if path == "/stranger.jpg":
        jpg = state.get_stranger_jpeg()
        if not jpg:
          self.send_response(404)
          self.send_header("Content-Length", "0")
          self.end_headers()
          return
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(jpg)))
        self.end_headers()
        self.wfile.write(jpg)
        return

      if path == "/events":
        _set_nodelay(self.connection)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        min_interval = 1.0 / SSE_MAX_FPS if SSE_MAX_FPS > 0 else 0.0
        try:
          with state.ui_lock:
            last_seq = state.ui_seq
            payload = state.ui_status_json
          self.wfile.write(b"data: " + payload + b"\n\n")
          self.wfile.flush()
          last_sent_t = time.perf_counter()

          while state.running:
            ui_seq, _, payload = state.wait_ui_update(last_seq, timeout=1.0)
            if not state.running:
              break
            if ui_seq != last_seq:
              if min_interval > 0:
                elapsed = time.perf_counter() - last_sent_t
                if elapsed < min_interval:
                  time.sleep(min_interval - elapsed)
                  with state.ui_lock:
                    ui_seq = state.ui_seq
                    payload = state.ui_status_json
              self.wfile.write(b"data: " + payload + b"\n\n")
              self.wfile.flush()
              last_seq = ui_seq
              last_sent_t = time.perf_counter()
            else:
              self.wfile.write(b": ping\n\n")
              self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
          pass
        return

      if path == "/stream":
        _set_nodelay(self.connection)
        self.send_response(200)
        self.send_header(
            "Content-Type", "multipart/x-mixed-replace; boundary=frame"
        )
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        min_interval = 1.0 / WEB_FPS if WEB_FPS > 0 else 0.0
        last_seq = -1
        last_sent_t = 0.0
        try:
          while state.running:
            ui_seq, jpg, _ = state.wait_ui_update(last_seq, timeout=1.0)
            if not state.running:
              break
            if ui_seq == last_seq or not jpg:
              continue
            if min_interval > 0 and last_sent_t > 0:
              elapsed = time.perf_counter() - last_sent_t
              if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
                with state.ui_lock:
                  ui_seq = state.ui_seq
                  jpg = state.ui_jpeg
                if not jpg:
                  continue
            self.wfile.write(
                b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                + str(len(jpg)).encode()
                + b"\r\n\r\n"
                + jpg
                + b"\r\n"
            )
            self.wfile.flush()
            last_seq = ui_seq
            last_sent_t = time.perf_counter()
        except (BrokenPipeError, ConnectionResetError, OSError):
          pass
        return

      self.send_response(404)
      self.send_header("Content-Length", "0")
      self.end_headers()

    def do_POST(self):
      path = self.path.split("?", 1)[0]
      body = self._read_json_body()

      if path == "/api/faces/register":
        name = str(body.get("name", "")).strip()
        if not (1 <= len(name) <= 32):
          self._send_json(
              400, {"ok": False, "err": "Ten phai tu 1 den 32 ky tu."}
          )
          return
        emb, age_s, face_count = state.get_latest_emb()
        if not emb or age_s > 2.0:
          self._send_json(
              400,
              {
                  "ok": False,
                  "err": (
                      "Khong thay khuon mat (hoac chua bat MobileFaceNet)."
                      " Hay nhin thang vao camera!"
                  ),
              },
          )
          return
        try:
          res = state.face_db.register(name, emb)
        except ValueError as e:
          self._send_json(400, {"ok": False, "err": str(e)})
          return
        state.sync_db_meta()
        self._send_json(
            200,
            {
                "ok": True,
                "name": res["name"],
                "samples": res["samples"],
                "face_count": face_count,
                "people": state.face_db.list_people(),
            },
        )
        return

      if path == "/api/faces/delete":
        name = str(body.get("name", "")).strip()
        deleted = state.face_db.delete(name)
        state.sync_db_meta()
        self._send_json(
            200,
            {"ok": deleted, "people": state.face_db.list_people()},
        )
        return

      if path == "/api/faces/clear":
        state.face_db.clear()
        state.sync_db_meta()
        self._send_json(200, {"ok": True, "people": []})
        return

      if path == "/api/faces/threshold":
        try:
          val = float(body.get("threshold", 0.45))
        except (TypeError, ValueError):
          self._send_json(
              400, {"ok": False, "err": "Threshold khong hop le."}
          )
          return
        t = state.face_db.set_threshold(val)
        state.sync_db_meta()
        self._send_json(200, {"ok": True, "threshold": t})
        return

      self._send_json(404, {"ok": False, "err": "Not found"})

  return WebHandler


def web_loop(state, host="0.0.0.0", port=8080):
  srv = ReuseThreadingHTTPServer((host, port), make_handler(state))
  print(f"[Web UI] Mo trinh duyet tai http://<IP_LUCKFOX>:{port}", flush=True)
  srv.serve_forever()
