# Tự động nhận đường dẫn Go trên Windows dù Terminal chưa cập nhật PATH
if ($env:Path -notlike "*C:\Program Files\Go\bin*") {
    $env:Path += ";C:\Program Files\Go\bin"
}

$env:CGO_ENABLED="0"
$env:GOOS="linux"
$env:GOARCH="arm"
$env:GOARM="7"

Write-Host "1. Dang build code cho Luckfox ARMv7..." -ForegroundColor Cyan
go build -ldflags="-s -w" -o app_luckfox main.go
if ($LASTEXITCODE -ne 0) {
    Write-Host "Loi build code! Dung qua trinh nap." -ForegroundColor Red
    exit 1
}

Write-Host "2. Dang nap sang mach qua Wi-Fi (192.168.1.9)..." -ForegroundColor Yellow
scp ./app_luckfox root@192.168.1.9:/root/

Write-Host "3. Dang chay thu tren mach..." -ForegroundColor Green
ssh root@192.168.1.9 "chmod +x /root/app_luckfox && /root/app_luckfox"