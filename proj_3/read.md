# --- luckfox pico zero - LCD tft 2inch

- ssh
ssh root@192.168.1.9
luckfox

2. Bật giao diện SPI0 trên Luckfox Pico Zero
ls /dev/spidev*


Kết quả ls: /dev/spidev*: No such file or directory cho thấy giao diện SPI0 hiện đang bị tắt mặc định trong Device Tree của Luckfox Pico Zero.

Bạn mở công cụ cấu hình phần cứng có sẵn trên mạch để bật SPI0 lên theo các bước sau:

Gõ lệnh sau vào terminal SSH:

Bash
luckfox-config



# --- setup pin

# --- deploy sang luckfox
- run lcd_test
.\deploy.ps1

- run sharingan
.\deploy2.ps1







