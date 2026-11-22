$LuckfoxIP = "192.168.1.9"
$User = "root"
$RemoteDir = "/root/tft_watch"
$Files = @("tft_driver.py", "robot_engine.py", "face_uchiha.py", "face_senju.py", "face_extra.py", "wifi_manager.py", "web_server.py", "main.py")

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  DEPLOYING TFT WATCH -> $LuckfoxIP" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Chuyen tat ca file sang LF (Linux)
foreach ($f in $Files) {
    $content = (Get-Content -Path $f -Raw) -replace "`r`n", "`n"
    [System.IO.File]::WriteAllText("$PWD\$f", $content)
}

Write-Host "[1/2] Dang tao thu muc va copy 6 file sang Luckfox..." -ForegroundColor Yellow
ssh "$User@$LuckfoxIP" "mkdir -p $RemoteDir"
scp $Files "${User}@${LuckfoxIP}:${RemoteDir}/"

if ($LASTEXITCODE -eq 0) {
    Write-Host "[2/2] Dang khoi chay main.py..." -ForegroundColor Green
    ssh -t "$User@$LuckfoxIP" "python3 -u $RemoteDir/main.py"
}