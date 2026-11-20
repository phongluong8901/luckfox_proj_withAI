import os
import traceback
import subprocess
import edge_tts
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from google import genai
from google.genai import types

# Nạp biến môi trường từ file .env
load_dotenv()

API_GEMINI_KEY = os.getenv("API_GEMINI_KEY")
MODEL_GEMINI = os.getenv("MODEL_GEMINI", "gemini-3.5-flash")
PORT_SERVER = int(os.getenv("PORT_SERVER", 8000))

try:
    import imageio_ffmpeg
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_EXE = "ffmpeg"

app = FastAPI()
client = genai.Client(api_key=API_GEMINI_KEY)

SYSTEM_PROMPT = (
    "Bạn là trợ lý robot thông minh chạy trên bo mạch Luckfox Pico Zero. "
    "Trả lời bằng tiếng Việt tự nhiên, ngắn gọn (2-3 câu), "
    "không dùng ký tự đặc biệt hay markdown để giọng đọc TTS mượt nhất."
)


@app.post("/voice_chat")
async def voice_chat(file: UploadFile = File(...)):
    input_wav = "user_input.wav"
    reply_mp3 = "reply.mp3"
    reply_wav = "reply.wav"

    try:
        content = await file.read()
        with open(input_wav, "wb") as f:
            f.write(content)

        print(f"\n[1/3] Da nhan file am thanh ({len(content)} bytes) tu Luckfox. Dang gui Gemini ({MODEL_GEMINI})...")

        with open(input_wav, "rb") as f:
            audio_bytes = f.read()

        response = client.models.generate_content(
            model=MODEL_GEMINI,
            contents=[
                SYSTEM_PROMPT,
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
            ],
        )
        reply_text = response.text.strip() if response.text else "Tôi không nghe rõ, bạn nói lại nhé."
        print(f"[2/3] Gemini tra loi: {reply_text}")

        communicate = edge_tts.Communicate(reply_text, voice="vi-VN-HoaiMyNeural")
        await communicate.save(reply_mp3)

        cmd = [
            FFMPEG_EXE, "-y",
            "-i", reply_mp3,
            "-ar", "16000",
            "-ac", "2",
            "-c:a", "pcm_s16le",
            reply_wav
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0:
            print(f"[!] Loi ffmpeg: {res.stderr.decode('utf-8', errors='ignore')}")
            raise RuntimeError("Loi convert audio bang ffmpeg")

        print("[3/3] Xu ly xong! Dang gui phan hoi ve Luckfox...")
        return FileResponse(reply_wav, media_type="audio/wav")

    except Exception as e:
        print("\n[X] LOI TAI SERVER:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    print(f"[*] Model: {MODEL_GEMINI} | Port: {PORT_SERVER} | FFmpeg: {FFMPEG_EXE}")
    uvicorn.run(app, host="0.0.0.0", port=PORT_SERVER)