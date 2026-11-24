# Quy trình vận hành hệ thống nhận diện khuôn mặt NPU trên Luckfox Pico Zero

Tài liệu này tóm tắt kiến trúc toàn hệ thống và từng bước từ **convert model AI trên Google Colab**, **biên dịch binary C++ cho RV1106**, **deploy lên board Luckfox**, cho tới **stream webcam từ Laptop & dùng Web UI**.

---

## 1. Tổng quan kiến trúc hệ thống

```text
[Laptop Webcam / Video]
   │  pc_vision_stream.py (CAP_DSHOW + MJPG, JPEG Q=50, 320x240)
   │  TCP port 9001 ([4-byte size][JPEG bytes])
   ▼
[Luckfox Pico Zero - RV1106G3 (1-core Cortex-A7 + 1 TOPS NPU)]
   ├─► luckfox_vision_node.py : Nhận frame TCP, luôn giữ frame mới nhất
   ├─► npu_worker.py          : Giao tiếp binary/shm với C++ daemon
   │      └─► rknn_face_daemon (C++ Zero-Copy trên NPU)
   │            ├─ Model 1: RetinaFace.rknn    ──► Box mặt + 5 điểm landmark
   │            └─ Model 2: MobileFaceNet.rknn ──► Align 112x112 + Vector đặc trưng
   ├─► face_db.py             : So khớp Cosine với /root/npu_rt/faces_db.json
   │                            (Chủ nhân vs Người lạ + lưu ảnh cảnh báo)
   └─► web_server.py (:8080)  : SSE (/events), MJPEG (/stream), API (/api/faces)
          │
          ▼
   [Trình duyệt Web UI (index.html)]
     • Xem live stream + khung tên / cảnh báo người lạ
     • Đăng ký khuôn mặt mới, xóa, chỉnh ngưỡng Cosine
```

---

## 2. Cấu trúc thư mục & vai trò từng file

| File | Trạng thái | Vai trò |
|---|---|---|
| `pc_vision_stream.py` | **Đang dùng (Laptop)** | Đọc webcam/video trên PC, nén JPEG (`Q=50`), gửi TCP cổng `9001` với cơ chế tự kết nối lại (`auto-reconnect`). |
| `luckfox_vision_node.py` | **Đang dùng (Luckfox)** | Điểm khởi chạy chính trên board: mở socket `0.0.0.0:9001`, web server `:8080`, và luồng `npu_worker`. |
| `npu_worker.py` | **Đang dùng (Luckfox)** | Quản lý `SharedState`, chạy daemon NPU, so khớp embedding với `FaceDB`, lưu ảnh/log người lạ. |
| `face_db.py` | **Đang dùng (Luckfox)** | Cơ sở dữ liệu khuôn mặt thuần Python (lưu tối đa `5` mẫu/người + vector trung bình tại `/root/npu_rt/faces_db.json`). |
| `web_server.py` | **Đang dùng (Luckfox)** | HTTP server cổng `8080`: phục vụ `/`, `/events` (SSE), `/stream` (MJPEG), `/stranger.jpg`, và `/api/faces/*`. |
| `index.html` | **Đang dùng (Luckfox)** | Giao diện Dashboard: KPI tốc độ, khung video + overlay, đăng ký khuôn mặt, chỉnh ngưỡng, ảnh người lạ. |
| `deploy.sh` | **Đang dùng (Laptop)** | Script `scp` + `ssh` đẩy toàn bộ code, UI, model, binary lên `/root/npu_rt` và chạy nền. |
| `colab/RetinaFace.rknn` | **Đang dùng (NPU)** | Model phát hiện khuôn mặt & 5 điểm mắt/mũi/miệng (`320x320`, INT8 RV1106). |
| `colab/MobileFaceNet.rknn` | **Đang dùng (NPU)** | Model trích xuất vector đặc trưng khuôn mặt (`112x112`, INT8 RV1106). |
| `colab/rknn_face_daemon` | **Đang dùng (Luckfox)** | Binary C++ Zero-Copy chạy nối tiếp 2 model `.rknn` trên NPU. |
| `colab/face_daemon_bin.cc` | **Mã nguồn C++** | Source C++ nâng cấp hỗ trợ cờ `--bin` (`READY_BIN`: đọc JPEG qua `stdin` RAM, không ghi file `/dev/shm/frame.jpg`). |
| `colab/face recog luckfox (2).ipynb` | **Notebook Colab** | Ghi lại toàn bộ các bước tải ONNX, convert `.rknn`, và biên dịch binary trên Google Colab. |
| `colab/rknn_retinaface_daemon` | Dự phòng | Daemon 1 model cũ (chỉ phát hiện mặt, dùng khi thiếu `rknn_face_daemon` hoặc `MobileFaceNet.rknn`). |
| `colab/rknn_retinaface_demo` | Không dùng (cũ) | Binary test 1 ảnh gốc của `rknn_model_zoo` (không giữ model trong RAM). |

---

## 3. Bước 1: Convert 2 model AI sang `.rknn` trên Google Colab

NPU **1 TOPS** trên chip **RV1106** chỉ chạy được định dạng **`.rknn` (INT8)** qua RKNN Runtime — không chạy trực tiếp `.onnx` bằng ONNX Runtime. Công cụ `rknn-toolkit2` chạy trên Linux `x86_64` nên ta thực hiện trên Google Colab (hoặc WSL2/Docker):

1. **Model 1 — Phát hiện khuôn mặt (`RetinaFace.rknn`)**:
   - Cài `rknn-toolkit2` (`setuptools<81`) trong môi trường Python 3.11.
   - Clone `airockchip/rknn_model_zoo` và chạy `download_model.sh` để lấy `RetinaFace_mobile320.onnx`.
   - Chạy `convert.py ../model/RetinaFace_mobile320.onnx rv1106` → thu được **`RetinaFace.rknn`** (~1.7 MB).

2. **Model 2 — Nhận diện danh tính (`MobileFaceNet.rknn`)**:
   - Dùng model pre-trained `mobilefacenet.onnx` (đầu vào `112x112`, `mean=[127.5, 127.5, 127.5]`, `std=[127.5, 127.5, 127.5]`).
   - Lượng tử hóa INT8 (`quantized_dtype="asymmetric_quantized-8"`, `target_platform="rv1106"`) với tập ảnh mẫu khuôn mặt `dataset.txt` → thu được **`MobileFaceNet.rknn`** (~3.6 MB).

> **Quan trọng:** Khi chuyển sang môi trường thực tế, ảnh calib trong `dataset.txt` nên là ảnh khuôn mặt rõ nét `112x112` để độ chính xác lượng tử hóa INT8 đạt mức tốt nhất.

---

## 4. Bước 2: Biên dịch daemon C++ Zero-Copy trên Colab (`rknn_face_daemon`)

Luckfox chạy Linux **ARMv7 + uClibc**, nên phải cross-compile bằng toolchain chính thức của Luckfox (`arm-rockchip830-linux-uclibcgnueabihf-g++`):

1. Trên Colab (đã có `luckfox-pico` toolchain và `rknn_model_zoo` như trong `colab/face recog luckfox (2).ipynb`), upload file **`colab/face_daemon_bin.cc`** lên `/content/face_daemon_bin.cc` và chạy lệnh biên dịch:

```bash
CXX=/content/luckfox-pico/tools/linux/toolchain/arm-rockchip830-linux-uclibcgnueabihf/bin/arm-rockchip830-linux-uclibcgnueabihf-g++
$CXX -O3 -mfpu=neon -mfloat-abi=hard -std=c++11 /content/face_daemon_bin.cc \
  -I/content/rknn_model_zoo/3rdparty/rknpu2/include \
  -I/content/rknn_model_zoo/3rdparty/stb_image \
  -L/content/rknn_model_zoo/3rdparty/rknpu2/Linux/armhf-uclibc -lrknnmrt -lpthread -lm \
  -o /content/rknn_face_daemon
```

2. Cơ chế hoạt động của binary:
   - Khi chạy với cờ `--bin`: in `READY_BIN`, đọc `[4-byte size][JPEG bytes]` trực tiếp từ `stdin` và giải mã ảnh trong RAM bằng `stbi_load_from_memory` (**loại bỏ hoàn toàn bước ghi/đọc file `/dev/shm/frame.jpg`**).
   - Khi chạy không có cờ `--bin` (hoặc dùng bản build cũ): in `READY` và đọc đường dẫn `/dev/shm/frame.jpg`. `npu_worker.py` tự động nhận biết `READY_BIN` hay `READY` để chạy tương thích cả hai.

3. Tải `RetinaFace.rknn`, `MobileFaceNet.rknn`, và `rknn_face_daemon` về đặt trong thư mục **`colab/`** trên Laptop.

---

## 5. Bước 3: Deploy & chạy NPU + Web Server trên Luckfox Pico Zero

Từ thư mục `proj_5_stream_video_lap` trên Laptop (Git Bash / WSL):

```bash
bash deploy.sh 192.168.1.3
```

*(Thay `192.168.1.3` bằng IP hiện tại của Luckfox.)*

Script `deploy.sh` tự động làm 3 việc:
1. **`[1/3]`** Tạo `/root/npu_rt` và dừng các tiến trình cũ (`luckfox_vision_node.py`, `rknn_face_daemon`, `rknn_retinaface_daemon`). File dữ liệu **`/root/npu_rt/faces_db.json`** được giữ nguyên để không mất danh sách khuôn mặt đã đăng ký.
2. **`[2/3]`** Chuyển đổi xuống dòng LF (`tr -d '\r'`) cho các file code/HTML và `scp` toàn bộ sang `/root/npu_rt/`.
3. **`[3/3]`** Cấp quyền thực thi `chmod +x`, nạp `LD_LIBRARY_PATH=/oem/usr/lib:/usr/lib:/lib`, chạy nền `luckfox_vision_node.py` và in log khởi động.

Để theo dõi log NPU realtime trên board:

```bash
ssh root@192.168.1.3 "tail -f /root/npu_rt/node.log"
```

Dấu hiệu khởi động thành công:
- Chế độ tối ưu nhất: `[NPU] Face daemon READY (2-model + binary stdin zero-file)!`
- Chế độ tương thích file RAM: `[NPU] Face daemon READY (2-model + /dev/shm mode)!`

---

## 6. Bước 4: Stream video từ Laptop sang Luckfox

Mở PowerShell tại `proj_5_stream_video_lap`:

```powershell
$env:LUCKFOX_IP="192.168.1.3"
$env:VIDEO_SOURCE="0"
uv run --with opencv-python pc_vision_stream.py
```

Các biến môi trường tùy chỉnh (nếu cần):
- `LUCKFOX_IP`: IP của Luckfox (mặc định `192.168.1.3`).
- `LUCKFOX_PORT`: Cổng TCP nhận frame (mặc định `9001`).
- `VIDEO_SOURCE`: `0` cho webcam mặc định, hoặc đường dẫn file `.mp4` để test lặp video.
- `WIDTH` / `HEIGHT`: Độ phân giải gửi đi (mặc định `320` x `240`).
- `JPEG_QUALITY`: Chất lượng nén JPEG (mặc định `50`, rất nhẹ cho Wi-Fi).
- `TARGET_FPS`: FPS mục tiêu của camera (mặc định `30`).

Script có sẵn **auto-reconnect** (tự nối lại sau `1s` khi bạn chạy lại `deploy.sh`) và in thống kê mỗi 30 frame:
`Sent=300 | Cam FPS=30.0 | Send FPS=29.8 | Drop=0 | Avg=6.2KB (185KB/s)`.

---

## 7. Bước 5: Sử dụng Web UI (`http://192.168.1.3:8080`)

Mở trình duyệt tới **`http://192.168.1.3:8080`**:

1. **Theo dõi chỉ số hiệu năng**:
   - **`FPS Thực`**: Tốc độ xử lý thực tế (đo theo cửa sổ trượt 30 frame).
   - **`NPU Cap`**: Công suất tối đa ước tính của pipeline (`1000 / Total ms`).
   - **`Det / Rec`**: Thời gian NPU cho RetinaFace (`~14–15 ms`) và MobileFaceNet (`~5–10 ms`).
   - **`Mode`**: `BIN` (đọc thẳng RAM qua `stdin`) hoặc `SHM` (qua `/dev/shm/frame.jpg`).
   - **`Tắt Video Preview`**: Ngắt luồng `/stream` để tiết kiệm băng thông Wi-Fi, vẫn vẽ khung mặt & landmark trực tiếp qua SSE.

2. **Đăng ký khuôn mặt mới**:
   - Nhìn thẳng vào camera, nhập tên vào ô **Đăng ký khuôn mặt** rồi bấm **Đăng ký**.
   - Bấm **2–3 lần** ở các góc mặt hơi nghiêng trái/phải để hệ thống lưu tối đa **5 mẫu/người** và tự tính vector trung bình (`centroid`) chính xác hơn.

3. **Chỉnh ngưỡng nhận diện (Cosine Threshold)**:
   - Thanh trượt từ `0.25` đến `0.80` (mặc định `0.45`):
     - Giảm (`0.35–0.42`): dễ nhận người quen hơn (ít báo nhầm người lạ khi thiếu sáng/nghiêng mặt).
     - Tăng (`0.50–0.65`): chặt hơn (giảm nhận nhầm người lạ thành chủ nhân).

4. **Phát hiện người lạ**:
   - Khung mặt chuyển **màu đỏ (`NGƯỜI LẠ`)**, banner phía trên chuyển cảnh báo đỏ, và ảnh chụp gần nhất được cập nhật vào mục **Cảnh báo người lạ** (cooldown `3s`/lần qua `/stranger.jpg`).

---

## 8. Xử lý lỗi nhanh & bước phát triển tiếp theo

| Tình huống | Cách xử lý |
|---|---|
| `Mode` đang hiện `SHM` thay vì `BIN` | Rebuild lại `colab/face_daemon_bin.cc` thành `colab/rknn_face_daemon` theo **Bước 2** rồi `bash deploy.sh 192.168.1.3`. |
| Bấm Đăng ký báo *"Không thấy khuôn mặt"* | Kiểm tra `Mode` đã bật 2 model (`Rec > 0 ms` khi có mặt), nhìn thẳng vào camera sao cho có khung nhận diện rồi bấm lại. |
| FPS bị tụt khi mở nhiều tab Web | Đóng bớt tab trình duyệt hoặc bấm **Tắt Video Preview** trên Web UI để giải phóng băng thông Wi-Fi. |
| Muốn tăng tốc Wi-Fi lên mức tối đa | Cắm cáp USB Type-C sang Laptop dùng IP RNDIS `172.32.0.93` thay cho Wi-Fi. |

### Nâng cấp tiếp theo
- **Chạy độc lập hoàn toàn với Camera CSI (`/dev/video21`)**: Thay nguồn ảnh TCP bằng đọc trực tiếp từ camera MIPI CSI + phần cứng RGA của RV1106 để đạt 30–50 FPS không cần Laptop.
- **Kết nối màn hình TFT (`tft_watch`)**: Đẩy tọa độ khuôn mặt chuẩn hóa `[-1..1]` và trạng thái `known/stranger` để mắt Sharingan tự động liếc theo mặt và đổi trạng thái khi gặp người lạ.
