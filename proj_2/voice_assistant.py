import os
import time
import wave
import audioop
import collections
import subprocess
import urllib.request

# Tu dong lay IP_ADDR do deploy2.ps1 truyen sang (fallback ve IP mac dinh neu chay tay)
IP_ADDR = os.environ.get("IP_ADDR", "http://192.168.1.10:8000").rstrip("/")
PC_SERVER_URL = f"{IP_ADDR}/voice_chat"

AUDIO_DEV = "hw:0,0"
OUTPUT_WAV = "/tmp/ans.wav"

SAMPLE_RATE = 16000
CHANNELS = 2
SAMPLE_WIDTH = 2  # 16-bit = 2 bytes

CHUNK_DURATION = 0.1
CHUNK_BYTES = int(SAMPLE_RATE * CHUNK_DURATION * CHANNELS * SAMPLE_WIDTH)

PRE_ROLL_CHUNKS = 5        # Giu lai 0.5s truoc khi bat dau noi
SILENCE_LIMIT_CHUNKS = 12  # Im lang 1.2s -> tu ngat va gui
MAX_SPEECH_CHUNKS = 150    # Toi da 15s moi cau
SPEECH_MARGIN = 350        # Bien do vuot nen sau khi da khu DC offset


def get_clean_rms(stereo_pcm):
    mono_pcm = audioop.tomono(stereo_pcm, SAMPLE_WIDTH, 0.5, 0.5)
    dc_offset = audioop.avg(mono_pcm, SAMPLE_WIDTH)
    ac_pcm = audioop.bias(mono_pcm, SAMPLE_WIDTH, -dc_offset)
    return audioop.rms(ac_pcm, SAMPLE_WIDTH)


def start_audio_stream():
    cmd = [
        "arecord", "-D", AUDIO_DEV,
        "-f", "S16_LE",
        "-r", str(SAMPLE_RATE),
        "-c", str(CHANNELS),
        "-t", "raw",
        "-q"
    ]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)


def save_pcm_to_wav(pcm_bytes, wav_path):
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_bytes)


def send_audio_to_pc(wav_path):
    boundary = "----LuckfoxVoiceBoundary7MA4YWxkTrZu0gW"
    with open(wav_path, "rb") as f:
        file_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="ask.wav"\r\n'
        f"Content-Type: audio/wav\r\n\r\n"
    ).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(PC_SERVER_URL, data=body)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Content-Length", str(len(body)))

    with urllib.request.urlopen(req, timeout=30) as resp:
        with open(OUTPUT_WAV, "wb") as out_f:
            out_f.write(resp.read())


def calibrate_noise_floor(stream, num_chunks=10):
    print("[*] Dang do do on nen thuc te (giu im lang 1s)...")
    stream.stdout.read(CHUNK_BYTES * 3)
    rms_values = []
    for _ in range(num_chunks):
        data = stream.stdout.read(CHUNK_BYTES)
        if data:
            rms_values.append(get_clean_rms(data))
    avg_noise = int(sum(rms_values) / max(len(rms_values), 1))
    threshold = avg_noise + SPEECH_MARGIN
    print(f"[*] Do on nen sach: {avg_noise} -> Nguong kich hoat: {threshold}")
    return threshold


def main():
    print("==========================================")
    print("  LUCKFOX SMART VAD STREAMING ASSISTANT   ")
    print(f"  Server: {PC_SERVER_URL}")
    print("==========================================")

    stream = start_audio_stream()
    threshold = calibrate_noise_floor(stream)

    ring_buffer = collections.deque(maxlen=PRE_ROLL_CHUNKS)
    recorded_chunks = []
    is_speaking = False
    silent_chunks = 0

    print("\nSan sang! Hay thu noi vao mic...")

    while True:
        chunk = stream.stdout.read(CHUNK_BYTES)
        if not chunk:
            time.sleep(0.05)
            continue

        rms = get_clean_rms(chunk)

        if not is_speaking:
            print(f"\r[Cho] Muc am: {rms:4d} / Nguong: {threshold}   ", end="", flush=True)
            ring_buffer.append(chunk)
            if rms > threshold:
                is_speaking = True
                silent_chunks = 0
                recorded_chunks = list(ring_buffer)
                recorded_chunks.append(chunk)
                print(f"\n[!] Phat hien giong noi (RMS: {rms}) -> Dang thu...", end="", flush=True)
        else:
            recorded_chunks.append(chunk)
            if rms > threshold:
                silent_chunks = 0
                print(".", end="", flush=True)
            else:
                silent_chunks += 1

            if silent_chunks >= SILENCE_LIMIT_CHUNKS or len(recorded_chunks) >= MAX_SPEECH_CHUNKS:
                duration = len(recorded_chunks) * CHUNK_DURATION
                print(f"\n[*] Chot cau ({duration:.1f}s). Dang gui len AI Server...")

                stream.terminate()
                stream.wait()

                try:
                    input_wav = "/tmp/ask.wav"
                    save_pcm_to_wav(b"".join(recorded_chunks), input_wav)
                    send_audio_to_pc(input_wav)

                    print("[*] Dang phat phan hoi...")
                    subprocess.run(
                        ["aplay", "-D", AUDIO_DEV, OUTPUT_WAV],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception as e:
                    print(f"[X] Loi xu ly: {e}")

                is_speaking = False
                silent_chunks = 0
                recorded_chunks = []
                ring_buffer.clear()
                stream = start_audio_stream()
                stream.stdout.read(CHUNK_BYTES * 3)
                print("\nSan sang nghe luot tiep theo...")


if __name__ == "__main__":
    main()