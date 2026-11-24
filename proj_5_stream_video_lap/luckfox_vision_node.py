import os
import socket
import struct
import threading
import time
from npu_worker import SharedState, worker_loop
from web_server import web_loop

HOST = "0.0.0.0"
PORT = int(os.environ.get("STREAM_PORT", "9001"))
WEB_PORT = int(os.environ.get("WEB_PORT", "8080"))


def recv_exact(conn: socket.socket, n: int) -> bytes | None:
  buf = bytearray(n)
  view = memoryview(buf)
  received = 0
  while received < n:
    got = conn.recv_into(view[received:])
    if got == 0:
      return None
    received += got
  return bytes(buf)


def reader_loop(state: SharedState):
  srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  srv.bind((HOST, PORT))
  srv.listen(1)
  print(f"[Luckfox] Dang cho luong video tai {HOST}:{PORT} ...", flush=True)

  while state.running:
    conn, addr = srv.accept()
    try:
      conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
      conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
    except OSError:
      pass
    print(f"[Luckfox] PC ket noi tu {addr}", flush=True)
    try:
      while state.running:
        hdr = recv_exact(conn, 4)
        if not hdr:
          break
        (size,) = struct.unpack(">I", hdr)
        if size <= 0 or size > 4 * 1024 * 1024:
          break
        payload = recv_exact(conn, size)
        if not payload:
          break
        state.push_frame(payload)
    finally:
      conn.close()
      print("[Luckfox] PC ngat ket noi.", flush=True)

  srv.close()


if __name__ == "__main__":
  state = SharedState()
  threading.Thread(
      target=web_loop, args=(state, HOST, WEB_PORT), daemon=True
  ).start()
  threading.Thread(target=reader_loop, args=(state,), daemon=True).start()
  threading.Thread(target=worker_loop, args=(state,), daemon=True).start()

  try:
    while True:
      time.sleep(1.0)
  except KeyboardInterrupt:
    state.stop()