# ---
proj_3/
├── tft_driver.py     # Driver Pure SPI, GPIO, vẽ hình & font chữ 5x7
├── face_uchiha.py    # Giao diện 1: Mắt Uchiha (Sharingan/Rinnegan) + Giờ
├── face_senju.py     # Giao diện 2: Mặt đồng hồ Senju (Xanh Mộc Độn)
├── wifi_manager.py   # Tự động kết nối Wi-Fi (Gosu) & lấy IP
├── web_server.py     # Web UI (port 8080) đổi mặt đồng hồ thời gian thực
├── main.py           # File chạy chính điều phối màn hình & Web
└── deploy.ps1        # Script đẩy toàn bộ file sang Luckfox

# --- cd app_web
.\deploy.ps1