# ==========================================
# 1. THÔNG TIN HỆ THỐNG & PHẦN CỨNG
# ==========================================
# Xem thông tin hệ điều hành (Buildroot)
cat /etc/os-release

# Xem thông tin CPU và phiên bản nhân Linux
uname -a
cat /proc/cpuinfo

# Xem dung lượng ổ cứng eMMC 8GB và các phân vùng
df -h

# Xem dung lượng RAM Linux (180MB) & RAM rảnh
free -m

# Xem dung lượng RAM cắt riêng cho Camera ISP & AI NPU (CMA/MPI)
cat /proc/rk_dma_heap/rk-dma-heap-cma

# Đọc nhiệt độ thực tế của chip SoC RV1106G3 (chia cho 1000 để ra độ C)
cat /sys/class/thermal/thermal_zone0/temp

# Xem tải hoạt động và phiên bản driver của nhân AI NPU (1.0 TOPS)
cat /sys/kernel/debug/rknpu/load
cat /sys/kernel/debug/rknpu/version


# ==========================================
# 2. MẠNG WI-FI & KẾT NỐI
# ==========================================
# Xem địa chỉ IP hiện tại của Wi-Fi (wlan0) và USB RNDIS (usb0)
ifconfig

# Quét danh sách các mạng Wi-Fi 2.4GHz xung quanh
iwlist wlan0 scan | grep ESSID

# Xem file cấu hình tên/mật khẩu Wi-Fi đã lưu
cat /etc/wpa_supplicant.conf

# Khởi động lại kết nối Wi-Fi và xin cấp lại IP
killall wpa_supplicant 2>/dev/null
ifconfig wlan0 up
wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant.conf
udhcpc -i wlan0


# ==========================================
# 3. ĐIỀU KHIỂN ĐÈN LED TRÊN MẠCH
# ==========================================
# Xem tên đèn LED và danh sách các chế độ nháy hỗ trợ
ls /sys/class/leds/
cat /sys/class/leds/work/trigger

# Tắt chế độ nhấp nháy tự động của hệ thống để điều khiển tay
echo none > /sys/class/leds/work/trigger

# Bật sáng đèn LED tối đa (255) / Tắt đèn LED (0)
echo 255 > /sys/class/leds/work/brightness
echo 0 > /sys/class/leds/work/brightness

# Trả lại chế độ nháy tự động theo tải CPU (mặc định của Luckfox)
echo activity > /sys/class/leds/work/trigger


# ==========================================
# 4. NGOẠI VI: PINMUX, GPIO, I2C, CAMERA
# ==========================================
# Mở menu cấu hình bật/tắt chân Pin (PWM, UART, SPI, I2C, CSI)
luckfox-config

# Xem toàn bộ thiết bị phần cứng đang mở (i2c, gpiochip, video, rknpu...)
ls /dev/

# Xem trạng thái các chân GPIO đang được sử dụng
cat /sys/kernel/debug/gpio

# Quét địa chỉ các cảm biến nối trên bus I2C-4 (ví dụ OLED, TOF050C...)
i2cdetect -y 4

# Kiểm tra các chương trình mặc định của hãng trong /oem và /userdata
ls -la /oem
ls -la /userdata


# ==========================================
# 5. ÂM THANH (MIC TRÊN MẠCH & LOA SPEAKER)
# ==========================================
# Xem danh sách thiết bị thu âm (Capture) và phát tiếng (Playback)
arecord -l
aplay -l

# Chỉnh âm lượng Mic và Loa (ALSA Mixer)
alsamixer

# Thu âm thử 5 giây từ MIC trên mạch (16kHz, 16-bit, Mono)
arecord -D hw:0,0 -f S16_LE -r 16000 -c 1 -d 5 /root/test_mic.wav

# Phát lại file âm thanh vừa thu ra cổng loa Speaker trên mạch
aplay /root/test_mic.wav

# Kéo file ghi âm từ mạch về máy tính (chạy trên PowerShell của Windows)
scp root@192.168.1.9:/root/test_mic.wav .


# ==========================================
# 6. QUẢN LÝ TIẾN TRÌNH & NẠP CODE TỪ WINDOWS
# ==========================================
# Xem các chương trình đang chạy ngầm và % CPU/RAM tiêu thụ
top

# Tắt chương trình mặc định chiếm Camera (rkipc) khi tự viết code Camera/AI
killall rkipc

# Lệnh chạy trên PowerShell (VS Code Windows) để Cross-Compile Go cho mạch:
$env:CGO_ENABLED="0"; $env:GOOS="linux"; $env:GOARCH="arm"; $env:GOARM="7"
go build -ldflags="-s -w" -o app_luckfox main.go
scp ./app_luckfox root@192.168.1.9:/root/

# Lưu dữ liệu từ bộ đệm RAM xuống eMMC và khởi động lại mạch an toàn
sync && reboot

# ------------------------------------------

# 1. Kiểm tra phần cứng & hệ thống
| Mục đích thao tác | Lệnh CLI | Ghi chú / Giải thích |
| :--- | :--- | :--- |
| Xem thông tin OS & CPU | `cat /etc/os-release && uname -a` | Kiểm tra bản Buildroot và nhân Linux 5.10 |
| Kiểm tra dung lượng ổ cứng | `df -h` | Kiểm tra phân vùng eMMC 8GB |
| Kiểm tra RAM & NPU memory | `free -m && cat /proc/rk_dma_heap/rk-dma-heap-cma` | Xem RAM Linux và RAM cấp riêng cho NPU/ISP |
| Kiểm tra nhiệt độ chip SoC | `cat /sys/thermal/thermal_zone0/temp` | Chia kết quả cho 1000 để ra độ C thực tế |

# 2. Quản lý mạng Wi-Fi
| Mục đích thao tác | Lệnh CLI | Ghi chú / Giải thích |
| :--- | :--- | :--- |
| Kiểm tra IP hiện tại | `ifconfig` | Xem IP Wi-Fi (`wlan0`) hoặc RNDIS (`usb0`) |
| Kết nối lại Wi-Fi thủ công | `killall wpa_supplicant 2>/dev/null; wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant.conf && udhcpc -i wlan0` | Ép mạch kết nối lại mạng và xin cấp lại IP |

# 3. Điều khiển đèn LED
| Mục đích thao tác | Lệnh CLI | Ghi chú / Giải thích |
| :--- | :--- | :--- |
| Tắt chế độ nháy tự động | `echo none > /sys/class/leds/work/trigger` | Chuyển sang chế độ điều khiển thủ công bằng tay |
| Bật / Tắt đèn LED | `echo 255 > /sys/class/leds/work/brightness`<br>`echo 0 > /sys/class/leds/work/brightness` | `255` là sáng tối đa, `0` là tắt hẳn |
| Trả về chế độ nháy hệ thống | `echo activity > /sys/class/leds/work/trigger` | Phục hồi đèn nháy theo nhịp hoạt động của CPU |

# 4. Ngoại vi & Cảm biến
| Mục đích thao tác | Lệnh CLI | Ghi chú / Giải thích |
| :--- | :--- | :--- |
| Cấu hình chân Pin (GPIO/PWM) | `luckfox-config` | Mở menu giao diện bật tắt các tính năng ngoại vi |
| Quét thiết bị trên bus I2C | `i2cdetect -y 4` | Dùng để kiểm tra các cảm biến nối vào chân I2C-4 |

# 5. Âm thanh (Mic & Loa)
| Mục đích thao tác | Lệnh CLI | Ghi chú / Giải thích |
| :--- | :--- | :--- |
| Kiểm tra thiết bị âm thanh | `arecord -l && aplay -l` | Liệt kê card thu âm và phát tiếng |
| Thu âm từ MIC trên mạch | `arecord -D hw:0,0 -f S16_LE -r 16000 -c 1 -d 5 /root/test_mic.wav` | Ghi file âm thanh 5 giây lưu vào `/root/` |
| Phát lại âm thanh ra loa | `aplay /root/test_mic.wav` | Phát file wav ra giắc cắm `Speaker` trên mạch |

# 6. Quản lý tiến trình & Khởi động lại
| Mục đích thao tác | Lệnh CLI | Ghi chú / Giải thích |
| :--- | :--- | :--- |
| Xem tiến trình đang chạy | `top` | Kiểm tra mức tiêu thụ CPU và RAM |
| Tắt dịch vụ Camera mặc định | `killall rkipc` | Dừng tiến trình stream camera của hãng để nhường phần cứng |
| Lưu dữ liệu & Khởi động lại | `sync && reboot` | Ghi sạch cache RAM xuống eMMC trước khi reboot |