# --- cach stup khi moi mua
cam vao laptop, mo network connection, tim connect DSN -> aan vao protocol v4

Bấm tổ hợp phím Win + R, gõ ncpa.cpl rồi nhấn Enter (nó sẽ mở cửa sổ Network Connections).

Tìm card mạng có dòng chữ Remote NDIS based Internet Sharing Device

Chuột phải vào nó -> chọn Properties -> nháy đúp vào Internet Protocol Version 4 (TCP/IPv4).

Tích vào Use the following IP address và điền:

IP address: 172.32.0.100

Subnet mask: 255.255.0.0

(Các ô còn lại để trống) -> Bấm OK hai lần để lưu.

- 
Mở PowerShell hoặc CMD trên Laptop lên, gõ lệnh:

PowerShell
ssh root@172.32.0.93

- 
Khi nó hỏi Are you sure you want to continue connecting (yes/no)?, gõ yes rồi Enter.
Nhập password mặc định: luckfox (lưu ý khi gõ password trên terminal nó sẽ không hiện ký tự nào, cứ gõ luckfox rồi nhấn Enter).



# --- pc (bo qua nhap mk)
if (!(Test-Path "$HOME\.ssh\id_ed25519.pub")) { ssh-keygen -t ed25519 -N '""' -f "$HOME\.ssh\id_ed25519" }
type $HOME\.ssh\id_ed25519.pub | ssh root@192.168.1.9 "mkdir -p /root/.ssh && cat >> /root/.ssh/authorized_keys && chmod 700 /root/.ssh && chmod 600 /root/.ssh/authorized_keys && sync"

# --- deploay thang vao luckfox
- check test
./deploy.ps1

- camera
./deploy2.ps1


# --- connnect
ssh root@192.168.1.9

# --- ping 
ping 192.168.1.9












