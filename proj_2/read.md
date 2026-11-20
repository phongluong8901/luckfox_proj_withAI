# ---
Vì bo mạch Luckfox Pico Zero chỉ có 256MB RAM và dùng hệ điều hành Buildroot Linux gọn nhẹ, kiến trúc tối ưu nhất (ít tốn RAM, độ trễ thấp, không cần cài thư viện nặng) là:

Trên mạch Luckfox Pico Zero: Dùng script Python siêu nhẹ (chỉ dùng thư viện chuẩn có sẵn của Python + arecord + aplay) để thu âm giọng nói -> gửi file .wav lên Server trên máy tính Windows qua HTTP -> nhận lại file phản hồi .wav và phát thẳng ra loa 4Ω 3W.

Trên máy tính Windows (Server xử lý AI): Chạy một server Python nhỏ (FastAPI/Flask) nhận file .wav từ Luckfox -> gọi Gemini API (Gemini xử lý trực tiếp file âm thanh gốc nên không cần bước trung gian STT, hiểu tiếng Việt cực chuẩn và cực nhanh) -> chuyển câu trả lời thành giọng nói tiếng Việt (dùng edge-tts miễn phí + ffmpeg đổi sang .wav) và trả về cho Luckfox phát loa.


# --- cmd
- quet ip tat ca trong dai
arp -a | findstr "192.168.1."

- ping
ping 192.168.1.9

- xoa ma khoa cu
ssh-keygen -R 192.168.1.9

- ssh
ssh root@192.168.1.9

- pass: luckfox

- ls
- pwd
- free -h


# --- check card am thanh
arecord -l && aplay -l

# --- chuyen dung cho speadker 8om 1w
nhung do co 4om 3w -> chuyen am luong xuong 60 % bao ve mach

alsamixer

Trong ảnh thứ 2 bạn chụp, bạn đang chọn đúng cột cuối cùng bên phải tên là <DAC LINE> (DAC LINEOUT), hiện tại nó đang ở mức 79.   Bạn chỉ cần chỉnh duy nhất cột DAC LINEOUT này thôi (tất cả các cột ADC... ở ảnh 1 và ALC... ở ảnh 2 là của Micro/bộ lọc thu âm, cứ giữ nguyên mặc định):
Ngay tại vị trí hiện tại (cột <DAC LINE> đang sáng đỏ ở góc phải dưới cùng), bạn bấm phím mũi tên Xuống để hạ con số 79 xuống khoảng 55 – 60 (nằm trọn trong vùng vạch màu xanh lá cây, dưới vạch trắng).

hoac dung cli
amixer -c 0 sset 'DAC LINEOUT' 60% 2>/dev/null || amixer -c 0 set Master 60% 2>/dev/null || alsamixer

- luu cau hinh vinh vien
alsactl store


# Test thu 3 giây từ Mic (2 kênh) và phát lại ngay ra Loa
arecord -D hw:0,0 -f S16_LE -r 16000 -c 2 -d 3 /tmp/test.wav && aplay -D hw:0,0 /tmp/test.wav


# --- tao server python tren pc
1. Tạo môi trường ảo tên là .venv
python -m venv .venv

2. Kích hoạt môi trường ảo (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Cập nhật pip và cài các thư viện cần thiết
python -m pip install --upgrade pip
pip install fastapi uvicorn python-multipart google-genai edge-tts
pip install imageio-ffmpeg
pip install python-dotenv

# Chạy server AI
python pc_voice_server.py

# --- tao client tren windows de deploy sang luckfox
- check LAN
ipconfig
192.168.1.10

# --- deploy cho luckfox
.\deploy.ps1


# --- killl tien trinh lucfox
pkill -9 -f "voice_assistant|arecord"

- check tien trinh da kill
ps | grep -E "voice|arecord"

