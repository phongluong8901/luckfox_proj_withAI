# Cấu hình kết nối Luckfox Pico Zero
$LuckfoxIP = "192.168.1.9"
$User = "root"
$LocalFile = "voice_assistant.py"
$RemoteDir = "/root"
$RemoteFile = "$RemoteDir/$LocalFile"

# 1. Đọc biến IP_ADDR từ file .env trên Windows
$ServerAddr = "http://192.168.1.10:8000"
if (Test-Path ".env") {
    $EnvLine = Get-Content ".env" | Where-Object { $_ -match "^IP_ADDR=" } | Select-Object -First 1
    if ($EnvLine) {
        $ServerAddr = ($EnvLine -split "=", 2)[1].Trim(' "''')
    }
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  DEPLOYING $LocalFile -> $LuckfoxIP" -ForegroundColor Cyan
Write-Host "  AI Server: $ServerAddr" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 2. Chuyển CRLF (Windows) sang LF (Linux) trong RAM và bắn thẳng qua 1 phiên SSH duy nhất
$UnixContent = (Get-Content -Path $LocalFile -Raw) -replace "`r`n", "`n"

Write-Host "[*] Dang don tien trinh cu, nap code va khoi chay..." -ForegroundColor Yellow
$UnixContent | ssh -t "$User@$LuckfoxIP" "pkill -9 -f 'voice_assistant|arecord' 2>/dev/null || true; cat > $RemoteFile && IP_ADDR='$ServerAddr' python3 $RemoteFile"