Trang chủ Wiki Luckfox Pico Zero: Luckfox Pico Zero Wiki — Tổng hợp toàn bộ thông số phần cứng (RV1106G3, 256MB DDR3L, 8GB eMMC, module Wi-Fi W8800DCS2), sơ đồ chân 40-pin GPIO và vị trí các cổng giao tiếp.

Hướng dẫn kết nối Camera CSI (22-pin): Luckfox Pico Zero CSI Camera Guide — Hướng dẫn chi tiết chiều cắm cáp 22-pin cho dòng IMX415-98 và ISG1321, kèm lệnh kiểm tra nhận diện cảm biến.   

Thông số chi tiết Camera IMX415-98 IR-CUT:   Luckfox IMX415 Camera Wiki — Thông số cảm biến Sony IMX415 (8MP, pixel size 1.45µm, kích thước 1/2.8 inch) và phân biệt bản 98° (22-pin) với bản (A) (20-pin).   

Waveshare IMX415-98 IR-CUT Wiki — Tài liệu chi tiết cách điều khiển bộ lọc hồng ngoại IR-CUT và thông số ống kính.

Kho Datasheet & Sơ đồ nguyên lý (Schematic): Luckfox-Pico-docs (GitHub) — Chứa file PDF datasheet chip RV1106, sơ đồ nguyên lý (Schematic), bản vẽ kích thước cơ khí 2D/3D để bạn thiết kế vỏ hoặc mạch mở rộng.   

2. Tài liệu Phần mềm (Software, SDK & AI NPU)Kho tải Firmware, Image Buildroot & Công cụ nạp (SocToolKit): Luckfox Pico Downloads — Nơi tải các bản image hệ điều hành Buildroot / Ubuntu mới nhất, công cụ nạp firmware qua USB (SocToolKit) và driver USB Rockchip (DriverAssistant).   

Mã nguồn SDK Linux đầy đủ (Kernel 5.10 + Buildroot): Luckfox-Pico SDK (GitHub) — Mã nguồn gốc để biên dịch lại nhân Linux, chỉnh sửa Device Tree (.dts) hoặc đóng gói thêm thư viện vào hệ điều hành.   

Tài liệu cấu hình Device Tree cho Pico Zero: Luckfox Pico Zero Device Tree — Hướng dẫn bật/tắt các ngoại vi phần cứng (UART, SPI, I2C, PWM, CSI) ở tầng nhân Linux.

Code mẫu Camera C/C++ (RKMPI, MPP, RTSP): Luckfox RKMPI Examples (GitHub) — Bộ mã nguồn chuẩn của Rockchip dùng để lấy khung hình trực tiếp từ cảm biến IMX415/SC3336, nén phần cứng H.264/H.265 và phát luồng RTSP.

Bộ công cụ & Code mẫu chạy AI trên NPU (1 TOPS RKNN): RKNN-Toolkit2 & Model Zoo (GitHub) — Công cụ trên PC dùng để convert các model AI (YOLOv5/v8, MobileNet, Face Recognition từ ONNX/PyTorch) sang định dạng .rknn để chạy trực tiếp trên nhân NPU của Luckfox Pico Zero.   