# Luckfox Pico Zero AI Desk Robot · Vision + TFT 2" + Mic + Speaker + Gemini

Trợ lý robot để bàn chạy trực tiếp trên **Luckfox Pico Zero (RV1106G3)** kết hợp **YOLOv8n-Seg**, **RetinaFace + MobileFaceNet**, **màn hình TFT 2 inch (ST7789)**, **Mic & Loa onboard** và **Gemini API** (hỏi đáp thời tiết, Google Search, nhìn camera đa phương thức, điều khiển biểu cảm robot).

---

## 1. Kiến trúc thư mục

```text
proj_7_camera_lcd_mic_speaker/
├── .env / .env.example        # API Key Gemini, ngưỡng Mic VAD, cấu hình TFT/Loa
├── deploy.sh                  # Đẩy code, model, .env, wav, autostart lên Luckfox
├── colab/
│   ├── vision_all_in_one_colab.ipynb  # Notebook convert 3 model RKNN + build C++ daemon
│   ├── yolov8n.rknn
│   ├── RetinaFace.rknn
│   ├── MobileFaceNet.rknn
│   └── rknn_vision_daemon
├── luckfox/
│   ├── main_node.py           # Nạp .env, khởi chạy toàn bộ luồng hệ thống
│   ├── shared_state.py        # Trạng thái dùng chung, chat log, xác thực chủ nhân
│   ├── gemini_client.py       # Gọi Gemini (tự fallback model), parse thẻ SCENE/VOL, TTS
│   ├── npu_pipeline.py        # Giao tiếp zero-copy binary với rknn_vision_daemon
│   ├── face_store.py          # Lưu/so khớp embedding khuôn mặt chủ sở hữu
│   ├── tft_display.py         # Emoji 3D/2D (idle/fly/drunk/love/cool/sleep) + camera kiểm tra mặt
│   ├── audio_io.py            # Mic pipe VAD chống nhiễu nền + phát âm thanh an toàn 4Ω 3W
│   ├── voice_agent.py         # Điều phối "Hey Luck", cổng bảo mật chủ sở hữu & hành động robot
│   ├── web_server.py          # HTTP + SSE + MJPEG + REST API chatbot & settings
│   ├── index.html             # Web UI + Mô phỏng TFT 2" trực tiếp + Chat + Mic RMS meter
│   ├── S99luckfox_bot         # Script tự khởi chạy khi cấp nguồn (/etc/init.d/)
│   └── cacert.pem             # Kho chứng chỉ SSL gốc cho HTTPS trên Buildroot
├── pc/
│   ├── pc_vision_stream.py    # Stream camera/video từ PC sang Luckfox (TCP:9001)
│   └── gen_vietnamese_wavs.py # Tạo bộ file .wav tiếng Việt offline (edge-tts + gTTS fallback)
└── assets/wav/                # Âm thanh thông báo tiếng Việt (owner, stranger, ready...)
```

---

## 2. Cấu hình `.env`

Mở file `.env` và điền `GEMINI_API_KEY`:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.5-flash
GEMINI_TTS_MODEL=gemini-2.5-flash-preview-tts
GEMINI_VOICE=Aoede
GEMINI_TTS=1
GEMINI_MIN_INTERVAL_S=4

ENABLE_MIC=1
AUDIO_MAX_VOL=60
MIC_VAD_THRESH=1400
MIC_COOLDOWN_S=5
WAKE_WORD=hey luck
WAKE_LISTEN_S=6
EMOJI_AUTO_CYCLE=1

OWNER_GRACE_S=30
OWNER_GREET_COOLDOWN_S=600
FACE_CHECK_HOLD_S=7
TFT_ROTATION=90
TFT_DC_PIN=54
TFT_RST_PIN=55
TFT_BL_PIN=-1
```

---

## 3. Cách chạy nhanh

### Bước 1 — Deploy lên Luckfox (Git Bash)
```bash
cd /d/All_proj/Embeded/Luckfox/luckfox_proj_withAI/proj_7_camera_lcd_mic_speaker
bash deploy.sh 192.168.1.3 root
```

### Bước 2 — Stream Camera từ PC (PowerShell)
```powershell
cd d:\All_proj\Embeded\Luckfox\luckfox_proj_withAI\proj_7_camera_lcd_mic_speaker\pc
$env:LUCKFOX_IP="192.168.1.3"
uv run --with opencv-python python pc_vision_stream.py
```

### Bước 3 — Mở Web UI
Truy cập `http://192.168.1.3:8080`:
- Bấm **Enroll** để đăng ký khuôn mặt Chủ sở hữu (hoặc dùng nút **🔓 Mở khóa 5p** khi không ngồi trước camera).
- Nói **"Hey Luck, thời tiết hôm nay thế nào?"**, **"Hey Luck, trên bàn có gì?"**, **"Hey Luck, giả vờ say rượu đi"** hoặc chat trực tiếp trên Web UI.
- Dùng thanh **Độ nhạy Mic** và thanh **RMS trực tiếp** để căn chỉnh vừa với tiếng ồn phòng của bạn.
