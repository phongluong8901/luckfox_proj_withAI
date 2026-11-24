#!/usr/bin/env python3
import os
import signal
import threading
import time


def _load_dotenv():
  env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
  if not os.path.isfile(env_path):
    return
  try:
    with open(env_path, "r", encoding="utf-8") as f:
      for raw in f:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
          continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
          os.environ[k] = v
  except OSError:
    pass


_load_dotenv()

from audio_io import audio_io_loop
from npu_pipeline import worker_loop
from shared_state import SharedState
from tcp_receiver import tcp_server_loop
from tft_display import tft_loop
from voice_agent import voice_agent_loop
from web_server import web_loop

TCP_PORT = int(os.environ.get("TCP_PORT", "9001"))
WEB_PORT = int(os.environ.get("WEB_PORT", "8080"))


def main():
  state = SharedState()

  def _handle_sig(_signum, _frame):
    state.stop()

  signal.signal(signal.SIGINT, _handle_sig)
  signal.signal(signal.SIGTERM, _handle_sig)

  threads = [
      threading.Thread(
          target=tcp_server_loop,
          args=(state,),
          kwargs={"port": TCP_PORT},
          name="tcp-rx",
          daemon=True,
      ),
      threading.Thread(
          target=worker_loop,
          args=(state,),
          name="npu-worker",
          daemon=True,
      ),
      threading.Thread(
          target=tft_loop,
          args=(state,),
          name="tft-hud",
          daemon=True,
      ),
      threading.Thread(
          target=audio_io_loop,
          args=(state,),
          name="audio-io",
          daemon=True,
      ),
      threading.Thread(
          target=voice_agent_loop,
          args=(state,),
          name="voice-agent",
          daemon=True,
      ),
      threading.Thread(
          target=web_loop,
          args=(state,),
          kwargs={"port": WEB_PORT},
          name="web-ui",
          daemon=True,
      ),
  ]

  for t in threads:
    t.start()

  print(
      f"[MAIN] Luckfox Chatbot Vision Node started (TCP={TCP_PORT}, Web={WEB_PORT})",
      flush=True,
  )

  try:
    while state.running:
      time.sleep(0.5)
  except KeyboardInterrupt:
    pass
  finally:
    state.stop()
    print("[MAIN] Stopping Luckfox Vision Node...", flush=True)


if __name__ == "__main__":
  main()
