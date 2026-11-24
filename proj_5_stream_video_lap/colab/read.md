Đúng hoàn toàn ý bạn hiểu: bạn không tự train AI từ đầu, mà lấy 2 model đã train sẵn (pre-trained .onnx), dùng Google Colab để chuyển sang .rknn (INT8 cho NPU RV1106) và biên dịch chéo (cross-compile) chương trình C++ để chạy chúng trên Luckfox, rồi tải về thư mục colab/.

Trong face recog luckfox (2).ipynb, các file được tạo ra theo 5 bước tuần tự sau:

Bước 1 — Tải & convert Model 1: Phát hiện khuôn mặt (RetinaFace.rknn)
Cài rknn-toolkit2 trong môi trường Python 3.11 (/opt/rknn_env).
Clone kho chính thức rknn_model_zoo của Rockchip và tải sẵn file RetinaFace_mobile320.onnx.
Chạy convert.py ... rv1106 để tối ưu đồ thị và lượng tử hóa FP32 → INT8 → ra RetinaFace.rknn (~1.7 MB).
Tác dụng: Tìm khung khuôn mặt (box) và 5 điểm mốc mắt/mũi/miệng (lm).
Bước 2 — Tải toolchain Luckfox & build thử bản demo gốc (rknn_retinaface_demo)
Tải trình biên dịch chéo arm-rockchip830-linux-uclibcgnueabihf (dùng để biên dịch code C++ trên máy Linux x86_64 của Colab nhưng chạy được trên chip ARM + uClibc của Luckfox).
Chạy ./build-linux.sh -t rv1106 -a armhf -d RetinaFace → ra rknn_retinaface_demo (~1.2 MB).
Ghi chú: Đây là bản demo chạy 1 ảnh rồi thoát (mỗi ảnh phải nạp lại model từ đầu nên chậm), giờ không còn dùng nữa.
Bước 3 — Build daemon 1 model (rknn_retinaface_daemon)
Viết file retinaface_daemon.cc dùng Zero-Copy API (rknn_create_mem, rknn_set_io_mem, stb_image.h) để nạp RetinaFace.rknn 1 lần duy nhất rồi giữ tiến trình chạy nền xử lý liên tục.
Biên dịch bằng toolchain uClibc → ra rknn_retinaface_daemon (~139 KB).
Ghi chú: Bản này chỉ phát hiện mặt (chưa phân biệt người quen/người lạ), giờ chỉ còn đóng vai trò dự phòng.
Bước 4 — Convert Model 2: Nhận diện danh tính (MobileFaceNet.rknn)
Dùng file pre-trained mobilefacenet.onnx (đầu vào 112×112, chuẩn hóa mean=127.5, std=127.5) cùng 10 ảnh mẫu trong dataset.txt để calibrate lượng tử hóa asymmetric_quantized-8 cho rv1106.
Xuất ra MobileFaceNet.rknn (~3.6 MB).
Tác dụng: Từ ảnh mặt đã cắt thẳng 112×112, rút ra một vector số ("dấu vân tay" khuôn mặt) để so khớp xem là ai.
Bước 5 — Build daemon 2 model nối tiếp (rknn_face_daemon) & tải về
Viết face_daemon.cc gộp cả 2 model vào chung 1 tiến trình Zero-Copy:
Chạy RetinaFace.rknn tìm khuôn mặt + 5 điểm mắt/mũi/miệng.
Gọi align_face_112() xoay và cắt khuôn mặt thẳng về 112×112.
Chạy MobileFaceNet.rknn lấy vector đặc trưng emb đã chuẩn hóa L2 và in ra JSON.
Biên dịch ra rknn_face_daemon (~145 KB) rồi tải cùng MobileFaceNet.rknn về laptop.