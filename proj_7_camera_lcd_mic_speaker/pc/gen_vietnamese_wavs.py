import asyncio
import io
import os
import struct
import wave

import av
import edge_tts

try:
  from gtts import gTTS
except ImportError:
  gTTS = None

VOICE = os.environ.get("TTS_VOICE", "vi-VN-HoaiMyNeural")
OUT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "wav")
)

PHRASES = {
    "owner.wav": "Xin chào chủ nhân",
    "stranger.wav": "Cảnh báo phát hiện người lạ",
    "enrolled.wav": "Đã lưu khuôn mặt chủ nhân thành công",
    "cleared.wav": "Đã xóa danh sách khuôn mặt",
    "ready.wav": "Hệ thống nhận diện đã sẵn sàng",
    "check_face.wav": "Vui lòng nhìn vào camera để kiểm tra gương mặt",
    "need_owner.wav": "Chưa xác thực chủ nhân vui lòng kiểm tra gương mặt",
    "object.wav": "Phát hiện vật thể",
    "obj_cell_phone.wav": "Phát hiện điện thoại",
    "obj_bottle.wav": "Phát hiện chai nước",
    "obj_cup.wav": "Phát hiện cái cốc",
    "obj_laptop.wav": "Phát hiện máy tính xách tay",
    "obj_book.wav": "Phát hiện quyển sách",
    "obj_chair.wav": "Phát hiện cái ghế",
    "obj_backpack.wav": "Phát hiện ba lô",
    "obj_cat.wav": "Phát hiện con mèo",
    "obj_dog.wav": "Phát hiện con chó",
    "obj_keyboard.wav": "Phát hiện bàn phím",
    "obj_mouse.wav": "Phát hiện chuột máy tính",
}


async def _tts_mp3(text: str, voice: str) -> bytes:
  last_err = None
  for attempt in range(2):
    try:
      comm = edge_tts.Communicate(text, voice)
      buf = bytearray()
      async for chunk in comm.stream():
        if chunk.get("type") == "audio":
          buf.extend(chunk["data"])
      if buf:
        return bytes(buf)
    except Exception as e:
      last_err = e
    await asyncio.sleep(0.5 * (attempt + 1))

  if gTTS is not None:
    buf = io.BytesIO()
    gTTS(text=text, lang="vi").write_to_fp(buf)
    data = buf.getvalue()
    if data:
      print(f"    (fallback gTTS OK for: {text})")
      return data

  raise last_err or RuntimeError(f"TTS failed for {text!r}")


def _mp3_to_pcm16_mono_16k(mp3_bytes: bytes, peak_ratio: float = 0.60) -> bytes:
  container = av.open(io.BytesIO(mp3_bytes), format="mp3")
  resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
  samples = []
  for frame in container.decode(audio=0):
    out_frames = resampler.resample(frame)
    if not isinstance(out_frames, list):
      out_frames = [out_frames]
    for of in out_frames:
      raw = bytes(of.planes[0])[: of.samples * 2]
      if raw:
        samples.extend(struct.unpack(f"<{len(raw) // 2}h", raw))
  # Flush resampler
  for of in resampler.resample(None):
    raw = bytes(of.planes[0])[: of.samples * 2]
    if raw:
      samples.extend(struct.unpack(f"<{len(raw) // 2}h", raw))
  container.close()

  if not samples:
    raise RuntimeError("Empty decoded audio")

  max_abs = max(abs(s) for s in samples)
  if max_abs > 0:
    target_peak = 32767.0 * peak_ratio
    scale = target_peak / float(max_abs)
    samples = [max(-32767, min(32767, int(round(s * scale)))) for s in samples]

  return struct.pack(f"<{len(samples)}h", *samples)


def _write_wav(path: str, pcm_bytes: bytes):
  with wave.open(path, "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(16000)
    wf.writeframes(pcm_bytes)


async def main():
  os.makedirs(OUT_DIR, exist_ok=True)
  print(f"Generating {len(PHRASES)} Vietnamese WAV clips ({VOICE}) -> {OUT_DIR}")
  for fname, text in PHRASES.items():
    out_path = os.path.join(OUT_DIR, fname)
    if os.path.isfile(out_path) and os.path.getsize(out_path) > 4096:
      print(f"  SKIP {fname:<19s} (already exists, {os.path.getsize(out_path):,} bytes)")
      continue
    mp3 = await _tts_mp3(text, VOICE)
    pcm = _mp3_to_pcm16_mono_16k(mp3, peak_ratio=0.60)
    _write_wav(out_path, pcm)
    dur_s = (len(pcm) // 2) / 16000.0
    print(f"  OK {fname:<20s} ({dur_s:.2f}s, {os.path.getsize(out_path):,} bytes)")
    await asyncio.sleep(0.35)


if __name__ == "__main__":
  asyncio.run(main())
