# Cấu hình kết nối Luckfox Pico Zero
$LuckfoxIP = "192.168.1.9"
$User = "root"
$LocalFile = "sharingan_tft.py"
$RemoteFile = "/root/$LocalFile"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  DEPLOYING $LocalFile -> $LuckfoxIP" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Chuyển đổi định dạng xuống dòng CRLF sang LF
$UnixContent = (Get-Content -Path $LocalFile -Raw) -replace "`r`n", "`n"
[System.IO.File]::WriteAllText("$PWD\$LocalFile", $UnixContent)

Write-Host "[1/2] Đang copy file giao diện mới sang Luckfox..." -ForegroundColor Yellow
scp "$LocalFile" "${User}@${LuckfoxIP}:${RemoteFile}"

if ($LASTEXITCODE -eq 0) {
    Write-Host "[2/2] Đang khởi chạy Sharingan trên màn hình..." -ForegroundColor Green
    ssh -t "$User@$LuckfoxIP" "python3 -u $RemoteFile"
} else {
    Write-Host "[X] Lỗi nạp file! Vui lòng kiểm tra kết nối mạng hoặc mật khẩu." -ForegroundColor Red
}