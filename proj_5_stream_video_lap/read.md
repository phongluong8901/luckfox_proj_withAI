# --- 
1. Chạy thử NPU (RKNN) nhận diện khuôn mặt — Chuẩn bị sẵn cho Webcam
Thay vì đợi cáp về mới mò SDK, bạn làm trước phần lõi AI trên NPU của Luckfox:

Ý tưởng: Chạy model siêu nhẹ (Face Detection hoặc YOLOv5n/v8n đã convert sang .rknn) bằng NPU tích hợp.

Cách test ngay: Stream ảnh từ webcam cắm trên PC qua HTTP/WebSocket sang Luckfox để đo tốc độ inference thực tế (FPS, độ trễ).

Kết quả: Vẽ tọa độ khuôn mặt để mắt Sharingan tự động liếc theo vị trí người nhìn. Vài hôm nữa cáp về chỉ việc đổi input sang /dev/video21 là chạy độc lập 100%.

# --- check

[ Webcam trên Laptop ] 
        │  HTTP MJPEG / snapshot qua Wi-Fi
        ▼
[ Luckfox Pico Zero (RV1106G3 - 1 TOPS NPU) ]
  ├─► NPU (.rknn RetinaFace / YOLOv5n-face) ──► Tọa độ (cx, cy) khuôn mặt
  ├─► tft_watch (face_uchiha.py / face_senju.py) ──► Liếc mắt theo (cx, cy) qua SPI0 (0-flicker)
  └─► Web UI (:8080) ──► Xem trạng thái / đổi chế độ mắt / bật-tắt tracking


- 
ls -la /usr/lib/librknn* /dev/rknpu* 2>/dev/null
dmesg | grep -iE "rknpu|npu" | tail -n 10

# --- run luckfox
bash deploy.sh 192.168.1.3

# --- run pc
cd luckfox_proj_withAI
cd proj_5_stream_video_lap

$env:LUCKFOX_IP="192.168.1.3"
$env:VIDEO_SOURCE="0"
uv run --with opencv-python pc_vision_stream.py

# --- show log luckfox
$env:LUCKFOX_IP="192.168.1.3"; $env:VIDEO_SOURCE="0"; uv run --with opencv-python pc_vision_stream.py

# --- ssh check log
ssh root@192.168.1.3 "tail -f /root/npu_rt/node.log"

# --- struct
Tách gọn phần trên Luckfox thành 4 file riêng biệt theo đúng chức năng (không nhét HTML vào Python) và cập nhật deploy.sh để đẩy tất cả trong 1 lần scp:

index.html: Giao diện Web UI theo dõi luồng ảnh và output NPU.

web_server.py: HTTP server (cổng 8080) phục vụ UI, /status và /stream.

npu_worker.py: Trạng thái dùng chung (SharedState) và vòng lặp gọi rknn_retinaface_demo trên NPU.

luckfox_vision_node.py: Điểm khởi chạy chính + TCP socket nhận frame từ PC (cổng 9001).

# --- check truyen du lieu
Với địa chỉ 192.168.1.3, gần như chắc chắn bạn đang truyền qua WiFi (đi qua router nhà bạn), còn dây USB cắm vào PC lúc này chỉ có tác dụng cấp nguồn (trừ khi bạn tự cấu hình lại IP cho cổng USB).Mạng WiFi (wlan0): Thường nhận dải IP của router như 192.168.1.x hoặc 192.168.0.x.Dây cáp USB (usb0 / RNDIS): Mặc định trên Luckfox Pico thường có IP tĩnh là 172.32.0.93.Để kiểm tra chắc chắn 100%, bạn chạy nhanh lệnh này từ PC xem 192.168.1.3 đang gắn trên card mạng nào:Bashssh root@192.168.1.3 "ip -4 a | grep 192.168.1.3"
Nếu cuối dòng hiện wlan0 $\rightarrow$ đang chạy qua WiFi.Nếu cuối dòng hiện usb0 $\rightarrow$ đang chạy trực tiếp qua dây USB.