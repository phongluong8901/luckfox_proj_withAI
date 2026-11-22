# Luckfox Pico Zero - Tài Liệu Setup & Deploy Dự Án

## 1. Sơ Đồ Đấu Dây (Pinout) - TFT LCD 2 inch (ST7789)

Sử dụng bus phần cứng **SPI0_M0** (mức logic 3.3V) trên thanh 40-pin của **Luckfox Pico Zero**.

| Chân TFT LCD 2" | Số Pin vật lý | Tên chân Luckfox | Số GPIO Linux | Chức năng |
| :--- | :---: | :--- | :---: | :--- |
| **VCC** | Pin 1 (hoặc 17) | `3.3V` | - | Nguồn nuôi 3.3V |
| **GND** | Pin 6 (hoặc 9, 14, 20, 25, 30, 34, 39) | `GND` | - | Mass chung |
| **DIN / SDA / MOSI** | Pin 19 | `GPIO1_C2_d` | 50 | `SPI0_MOSI_M0` (Dữ liệu SPI) |
| **CLK / SCK / SCL** | Pin 23 | `GPIO1_C1_d` | 49 | `SPI0_CLK_M0` (Xung nhịp SPI) |
| **CS** | Pin 24 | `GPIO1_C0_d` | 48 | `SPI0_CS0_M0` (Chip Select) |
| **DC / RS** | Pin 12 | `GPIO1_C6_d` | 54 | Data / Command (`0`: Lệnh, `1`: Dữ liệu) |
| **RST / RES** | Pin 36 | `GPIO1_C7_d` | 55 | Reset phần cứng màn hình |
| **BL / LED** | Pin 17 (hoặc 1) | `3.3V` | - | Đèn nền Backlight (sáng tối đa) |

> **Công thức tính số GPIO trên Linux RV1106:** `GPIO = Bank * 32 + (Group * 8 + Index)` với `A=0, B=1, C=2, D=3`.

---

## 2. Cấu Hình Phần Cứng Trên Luckfox Pico Zero (SSH)

Kết nối vào mạch:
```bash
ssh root@192.168.1.9
```

### 2.1. Bật SPI0_M0
1. Chạy `luckfox-config` -> **Advanced Options** -> **SPI**.
2. Chọn `SPI0_M0` (bấm **Space** để chọn rồi **Enter**):
   - **Speed:** `40000000` (40 MHz)
   - **CS0 Enable:** `1 enable`
   - **MISO Enable:** `0 disable`
3. Thoát ra menu chính -> chọn `<Cancel>` để về terminal. Kiểm tra file `/etc/luckfox.cfg`:
   ```ini
   SPI0_M0_CS_ENABLE=1
   SPI0_M0_MODE=1
   SPI0_M0_STATUS=1
   SPI0_M0_MISO_ENABLE=0
   SPI0_M0_SPEED=40000000
   ```

### 2.2. Tự động nạp SPI0 mỗi khi khởi động lại (Reboot)
Do bản Buildroot tối giản không tự gọi `luckfox-config load` lúc boot, cần tạo script trong `/etc/init.d/`:

```bash
cat << 'EOF' > /etc/init.d/S99luckfox_cfg
#!/bin/sh
case "$1" in
    start)
        /usr/bin/luckfox-config load
        ;;
esac
exit 0
EOF
chmod +x /etc/init.d/S99luckfox_cfg
reboot
```

Kiểm tra sau khi khởi động lại:
```bash
ls /dev/spidev*
# Kết quả chuẩn: /dev/spidev0.0
```

### 2.3. Lưu cấu hình âm thanh (Loa 4 Ohm 3W)
- Hạ `DAC LINEOUT` xuống khoảng ~60% trong `alsamixer` để tránh rè/sập nguồn.
- Lưu cố định cấu hình: `alsactl store`.
- Luồng âm thanh chuẩn phần cứng `rv1106-acodec` yêu cầu 2 kênh (`-c 2`), 16kHz, `S16_LE`.

---

## 3. Setup & Chạy Dự Án

### 3.1. Cấu hình file `.env` (Trên PC Windows)
```env
API_GEMINI_KEY="YOUR_GEMINI_API_KEY"
MODEL_GEMINI=gemini-2.5-flash
PORT_SERVER=8000
IP_ADDR=http://192.168.1.10:8000
```

### 3.2. Chạy AI Voice Server (Trên PC Windows)
Cài đặt thư viện cần thiết trong `.venv`:
```powershell
pip install fastapi uvicorn google-genai edge-tts imageio-ffmpeg python-dotenv python-multipart
```
Khởi chạy server:
```powershell
python pc_voice_server.py
```

### 3.3. Deploy & Chạy Test Màn Hình TFT (`deploy.ps1`)
Sử dụng driver Pure Python (`fcntl` + `/dev/spidev0.0` + `/sys/class/gpio`), không cần cài thêm thư viện `spidev` trên mạch.

```powershell
$LuckfoxIP = "192.168.1.9"
$User = "root"
$LocalFile = "lcd_test.py"
$RemoteFile = "/root/$LocalFile"

$UnixContent = (Get-Content -Path $LocalFile -Raw) -replace "`r`n", "`n"
[System.IO.File]::WriteAllText("$PWD\$LocalFile", $UnixContent)

scp "$LocalFile" "${User}@${LuckfoxIP}:${RemoteFile}"
if ($LASTEXITCODE -eq 0) {
    ssh -t "$User@$LuckfoxIP" "python3 -u $RemoteFile"
}
```
Chạy trên PowerShell: `.\deploy.ps1`

### 3.4. Deploy & Chạy Trợ Lý Giọng Nói (`deploy2.ps1`)
Tự động đọc `IP_ADDR` từ `.env` trên Windows và truyền sang biến môi trường của Luckfox:

```powershell
$LuckfoxIP = "192.168.1.9"
$User = "root"
$LocalFile = "voice_assistant.py"
$RemoteFile = "/root/$LocalFile"

$ServerAddr = "http://192.168.1.10:8000"
if (Test-Path ".env") {
    $EnvLine = Get-Content ".env" | Where-Object { $_ -match "^IP_ADDR=" } | Select-Object -First 1
    if ($EnvLine) {
        $ServerAddr = ($EnvLine -split "=", 2)[1].Trim(' "''')
    }
}

$UnixContent = (Get-Content -Path $LocalFile -Raw) -replace "`r`n", "`n"
$UnixContent | ssh -t "$User@$LuckfoxIP" "pkill -9 -f 'voice_assistant|arecord' 2>/dev/null || true; cat > $RemoteFile && IP_ADDR='$ServerAddr' python3 -u $RemoteFile"
```
Chạy trên PowerShell: `.\deploy2.ps1`

---

## 4. Ghi Chú Xử Lý Lỗi Nhanh

- **Màn hình bị ngược màu (trắng thành đen):** Đổi lệnh `self.cmd(0x21)` thành `self.cmd(0x20)` trong `ST7789.init_display()`.
- **Lỗi font tiếng Việt trong code trên Luckfox:** Lưu file định dạng `UTF-8`, chuyển xuống dòng `LF` (không dùng `CRLF`), và hạn chế dấu tiếng Việt trong comment/print của file chạy trên Buildroot.
- **Tránh lỗi `pkill` tự ngắt phiên SSH:** Không chạy `pkill -9 -f 'ten_file.py'` trong cùng một dòng lệnh SSH có chứa chính chuỗi `ten_file.py` ở phía sau; ưu tiên tách riêng `scp` và `ssh -t`.