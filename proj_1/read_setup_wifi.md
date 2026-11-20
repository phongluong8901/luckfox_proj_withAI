A. Cấu hình thủ công lần đầu (Chạy trực tiếp trên Terminal của mạch):

# 1. Ghi cấu hình Wi-Fi vào file hệ thống
cat << 'EOF' > /etc/wpa_supplicant.conf
ctrl_interface=/var/run/wpa_supplicant
ap_scan=1
update_config=1

network={
        ssid="Ten_WiFi_Nha_Ban"
        psk="Mat_Khau_WiFi"
        key_mgmt=WPA-PSK
}
EOF

# 2. Bật card mạng wlan0, kill tiến trình cũ và kết nối lại
killall wpa_supplicant 2>/dev/null
ifconfig wlan0 up
wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant.conf
udhcpc -i wlan0

# 3. Đồng bộ hóa dữ liệu xuống eMMC
sync

# ----------------------------
B. Tạo dịch vụ tự động bắt Wi-Fi khi khởi động (Đã bổ sung sync và ifconfig wlan0 up chuẩn xác):

cat << 'EOF' > /etc/init.d/S99wifi_auto
#!/bin/sh
case "$1" in
  start)
    echo "Starting Wi-Fi connection..."
    ifconfig wlan0 up
    wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant.conf
    udhcpc -i wlan0 &
    ;;
  stop)
    killall wpa_supplicant
    ;;
esac
EOF

# Phân quyền thực thi và đồng bộ ổ cứng
chmod +x /etc/init.d/S99wifi_auto
sync