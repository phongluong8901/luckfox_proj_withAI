# Luckfox Pico Zero - Thông số đầy đủ + Ý tưởng dự án

**Board phát triển Linux mini chuyên vision + AI edge**  
Chip: Rockchip RV1106G3 | Kích thước nhỏ gọn (~65 x 30 mm)

---

## 1. Thông số kỹ thuật chi tiết

### Chip & Hiệu năng
| Thông số | Chi tiết |
|----------|----------|
| **SoC** | Rockchip RV1106G3 |
| **CPU** | Single-core ARM Cortex-A7 @ tối đa **1.2 GHz** (có NEON + FPU) |
| **NPU** | **1 TOPS** (hỗ trợ INT4 / INT8 / INT16 mixed precision) |
| **ISP** | Hardware ISP3.2, hỗ trợ HDR, 3A, LSC, 3DNR, 2DNR, sharpening, dehaze, gamma... |
| **Video Encode** | H.264 / H.265 lên tới **5MP @ 30fps**, JPEG snapshot cao hơn |
| **RAM** | **256 MB DDR3L** (tích hợp SiP) |
| **Lưu trữ** | **8 GB eMMC** + khe **microSD** (mở rộng) |

### Kết nối & Ngoại vi
| Thông số | Chi tiết |
|----------|----------|
| **Wi-Fi** | 2.4 GHz **Wi-Fi 6** (802.11ax) – module AIC8800DC |
| **Bluetooth** | **Bluetooth 5.2 / BLE** |
| **Camera** | **MIPI CSI 4-lane** (hỗ trợ camera 5MP@30fps, một số module lên 8MP@15fps) |
| **USB** | USB 2.0 Host/Device (Type-C – dùng nguồn + nạp firmware) |
| **GPIO** | Header **40-pin** (~28 GPIO), tương thích một số HAT Raspberry Pi |
| **Giao tiếp** | UART, SPI, I2C (qua GPIO) |
| **Audio** | Microphone onboard + cổng loa **MX1.25 mm** (hỗ trợ loa 8Ω 1W) |
| **Khác** | Nút Reset + Boot, User LED, cổng RTC battery, antenna (có thể chuyển giữa antenna ngoài và antenna dán trên board) |

### Hệ điều hành & Phần mềm
- Hệ thống chính: **Buildroot** (có SDK đầy đủ)
- Hỗ trợ một số image Ubuntu
- Login mặc định:
  - User: `root`
  - Password: `luckfox`
  - IP USB static: `172.32.0.93`
- Hỗ trợ ADB, SSH, serial console

---

## 2. Ưu điểm nổi bật

- **NPU 1 TOPS** + ISP mạnh → rất phù hợp AI camera / edge vision
- Có **Wi-Fi 6 + Bluetooth** sẵn → dễ làm IoT, camera không dây
- Nhỏ gọn, giá rẻ, tiêu thụ điện thấp
- Có eMMC 8GB sẵn → không bắt buộc dùng thẻ nhớ
- Cộng đồng Luckfox + Rockchip khá hỗ trợ (wiki tiếng Anh + tiếng Trung tốt)

---

## 3. Các dự án có thể làm được

### 1. AI Camera / Giám sát thông minh (phù hợp nhất)
- Camera phát hiện người / vật thể (YOLO)
- Camera an ninh gửi cảnh báo qua Telegram / MQTT khi có người
- Đếm người / đếm xe
- Camera nhận diện khuôn mặt / PPE (mũ bảo hộ, khẩu trang...)
- Smart doorbell (chuông cửa thông minh)

### 2. IoT & Giám sát từ xa
- Camera giám sát nông trại / chuồng nuôi (phát hiện động vật, đếm)
- Camera theo dõi cửa hàng / kệ hàng (out-of-stock detection)
- Hệ thống giám sát nhà thông minh (kết hợp cảm biến GPIO)

### 3. Robot & Thiết bị di động
- Camera AI cho robot di động (object tracking, obstacle detection)
- FPV / camera cho drone nhỏ (nhẹ, tiêu thụ điện thấp)
- Robot theo dõi người / vật thể

### 4. Audio + Vision
- Camera có micro + loa → intercom / camera gọi video đơn giản
- Thiết bị hỗ trợ người khiếm thị (mô tả cảnh vật bằng giọng nói – cần model nhỏ)

### 5. Ứng dụng công nghiệp / thực tế
- Máy đọc mã vạch / OCR công nghiệp
- Giám sát dây chuyền sản xuất (đếm sản phẩm, phát hiện lỗi)
- Camera đo lường / kiểm tra chất lượng

### 6. Dự án học tập / thử nghiệm
- Chạy YOLOv5 / YOLOv8 / YOLOv11 quantized trên NPU (RKNN)
- Stream RTSP / RTMP camera
- Làm Web dashboard điều khiển camera
- Kết hợp GPIO điều khiển servo / relay / cảm biến

---

## 4. Gợi ý bắt đầu nhanh

1. Nạp image Buildroot mới nhất từ wiki Luckfox
2. Kết nối camera MIPI CSI (IMX415 hoặc camera tương thích)
3. Test stream RTSP: `rtsp://IP/live/0`
4. Cài RKNN toolkit để chạy model AI
5. Kết nối Wi-Fi và thử gửi ảnh/cảnh báo

---

## 5. Link hữu ích

- Wiki chính thức: [https://wiki.luckfox.com/Luckfox-Pico-Zero/](https://wiki.luckfox.com/Luckfox-Pico-Zero/)
- Hướng dẫn camera CSI
- Hướng dẫn Wi-Fi / Bluetooth
- GitHub cộng đồng (YOLO trên Luckfox, SmartCamera RV1106...)

---

**File này dùng để lưu trữ thông số + ý tưởng dự án.**  
Muốn mình bổ sung phần nào (pinout chi tiết, hướng dẫn nạp firmware, ví dụ code YOLO...) thì bảo nhé!
