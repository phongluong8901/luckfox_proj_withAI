# ---
Chuyển sang YOLOv8n (INT8) là lựa chọn hợp lý nhất cho NPU 1 TOPS của RV1106: rknn_model_zoo có sẵn bản ONNX đã tách sẵn đầu ra tối ưu cho NPU, không bị nghẽn post-processing trên CPU Cortex-A7.Hiệu năng dự kiến trên RV1106 (Zero-Copy)ModelInputThời gian NPUĐộ chính xácYOLOv8n (INT8)640x640~25–35 msNhận diện tốt vật nhỏ, đủ 80 class COCOYOLOv8n (INT8)416x416~12–18 msRất nhanh (~40–50 FPS NPU), hợp stream real-timeTa giữ nguyên kiến trúc TCP $\rightarrow$ C++ Zero-Copy Daemon $\rightarrow$ SSE + Web UI đã chạy ổn ở project trước, chỉ cần làm 2 bước:Trên Colab: Convert yolov8n.rknn (target rv1106) + biên dịch rknn_yolo_daemon.Trên Laptop/Luckfox: Thay npu_worker.py, index.html (vẽ box + nhãn 80 vật thể COCO) và deploy.sh.


- 
cd luckfox_proj_withAI
cd proj_6_yolo_object
cd 

# --- luckfox
bash deploy.sh 192.168.1.3

# --- pc
$env:LUCKFOX_IP="192.168.1.3"; $env:VIDEO_SOURCE="0"; uv run --with opencv-python pc_vision_stream.py

# --- 