# Cau hinh ket noi Luckfox Pico Zero
$LuckfoxIP = "192.168.1.9"
$User = "root"
$LocalFile = "lcd_test.py"
$RemoteFile = "/root/$LocalFile"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  DEPLOYING $LocalFile -> $LuckfoxIP" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Chuyen CRLF (Windows) sang LF (Linux) ngay tai file local
$UnixContent = (Get-Content -Path $LocalFile -Raw) -replace "`r`n", "`n"
[System.IO.File]::WriteAllText("$PWD\$LocalFile", $UnixContent)

Write-Host "[1/2] Dang copy file sang Luckfox..." -ForegroundColor Yellow
scp "$LocalFile" "${User}@${LuckfoxIP}:${RemoteFile}"

if ($LASTEXITCODE -eq 0) {
    Write-Host "[2/2] Dang chay $LocalFile tren Luckfox..." -ForegroundColor Green
    ssh -t "$User@$LuckfoxIP" "python3 -u $RemoteFile"
}