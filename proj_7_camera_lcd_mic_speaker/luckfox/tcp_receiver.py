import socket
import struct
import threading

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


def tcp_client_loop(conn: socket.socket, addr, state):
  print(f"[TCP] Client ket noi tu {addr}", flush=True)
  try:
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
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


def tcp_server_loop(state, host: str = "0.0.0.0", port: int = 9001):
  srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  srv.bind((host, port))
  srv.listen(4)
  srv.settimeout(1.0)
  print(f"[TCP] Dang lang nghe frame tai {host}:{port}", flush=True)

  try:
    while state.running:
      try:
        conn, addr = srv.accept()
      except socket.timeout:
        continue
      except OSError:
        break
      threading.Thread(
          target=tcp_client_loop, args=(conn, addr, state), daemon=True
      ).start()
  finally:
    try:
      srv.close()
    except OSError:
      pass