import signal
import socket
import struct
import threading
import time

from npu_worker import SharedState, worker_loop
from web_server import web_loop

TCP_HOST = "0.0.0.0"
TCP_PORT = 9001
WEB_HOST = "0.0.0.0"
WEB_PORT = 8080
MAX_FRAME_BYTES = 2 * 1024 * 1024


def recv_exact(conn: socket.socket, size: int) -> bytes | None:
  buf = bytearray(size)
  view = memoryview(buf)
  pos = 0
  while pos < size:
    n = conn.recv_into(view[pos:], size - pos)
    if n <= 0:
      return None
    pos += n
  return bytes(buf)


def tcp_client_loop(conn: socket.socket, addr, state: SharedState):
  print(f"[TCP] Client ket noi tu {addr}", flush=True)
  try:
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
  except OSError:
    pass

  try:
    while state.running:
      hdr = recv_exact(conn, 4)
      if not hdr:
        break
      (frame_len,) = struct.unpack("!I", hdr)
      if frame_len <= 0 or frame_len > MAX_FRAME_BYTES:
        print(
            f"[TCP WARN] Kich thuoc frame khong hop le: {frame_len}", flush=True
        )
        break
      payload = recv_exact(conn, frame_len)
      if not payload:
        break
      state.push_frame(payload)
  except OSError as e:
    print(f"[TCP] Loi nhan du lieu tu {addr}: {e}", flush=True)
  finally:
    try:
      conn.close()
    except OSError:
      pass
    print(f"[TCP] Ngat ket noi {addr}", flush=True)


def tcp_server_loop(state: SharedState):
  srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  srv.bind((TCP_HOST, TCP_PORT))
  srv.listen(4)
  srv.settimeout(1.0)
  print(f"[TCP] Dang lang nghe frame tai {TCP_HOST}:{TCP_PORT}", flush=True)

  try:
    while state.running:
      try:
        conn, addr = srv.accept()
      except socket.timeout:
        continue
      except OSError:
        break
      t = threading.Thread(
          target=tcp_client_loop, args=(conn, addr, state), daemon=True
      )
      t.start()
  finally:
    try:
      srv.close()
    except OSError:
      pass


def main():
  state = SharedState()

  def handle_stop(signum, frame):
    state.stop()

  signal.signal(signal.SIGTERM, handle_stop)
  signal.signal(signal.SIGINT, handle_stop)

  t_worker = threading.Thread(target=worker_loop, args=(state,), daemon=True)
  t_tcp = threading.Thread(target=tcp_server_loop, args=(state,), daemon=True)
  t_web = threading.Thread(
      target=web_loop, args=(state, WEB_HOST, WEB_PORT), daemon=True
  )

  t_worker.start()
  t_tcp.start()
  t_web.start()

  try:
    while state.running:
      time.sleep(0.5)
  finally:
    state.stop()


if __name__ == "__main__":
  main()