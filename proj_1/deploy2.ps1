<#
.SYNOPSIS
    Script tu dong Deploy cam_test.py len Luckfox Pico Zero va mo stream camera.
#>

$TargetIP   = "192.168.1.9"
$TargetUser = "root"
$RemoteDir  = "/root"
$LocalFile  = "cam_test.py"
$RtspUrl    = "rtsp://${TargetIP}/live/0"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  LUCKFOX - DEPLOY & VIEW CAMERA                  " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# Buoc 1: Kiem tra file local co ton tai khong
if (!(Test-Path $LocalFile)) {
    Write-Host "[X] LOI: Khong tim thay file '$LocalFile'!" -ForegroundColor Red
    exit 1
}

# Buoc 2: Day file qua mang Wi-Fi (SCP)
Write-Host "[1/2] Dang day file $LocalFile sang mach ($TargetIP)..." -ForegroundColor Yellow
$remoteTarget = "${TargetUser}@${TargetIP}:${RemoteDir}/"
scp $LocalFile $remoteTarget

if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] LOI: Khong the truyen file qua SCP!" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Truyen file hoan tat." -ForegroundColor Green

# Buoc 3: Chay cam_test.py tren mach (khong kill rkipc nua)
Write-Host "[2/2] Dang kiem tra camera va bat RTSP stream tren mach..." -ForegroundColor Yellow
$sshTarget  = "${TargetUser}@${TargetIP}"
$sshCommand = "python3 ${RemoteDir}/${LocalFile}"
ssh $sshTarget $sshCommand

if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] LOI: Kiem tra camera tren mach gap su co." -ForegroundColor Red
    exit 1
}

# Buoc 4: Tu dong mo VLC hoac ffplay neu co san tren Windows
$ffplay = Get-Command ffplay -ErrorAction SilentlyContinue
$vlcPaths = @(
    "C:\Program Files\VideoLAN\VLC\vlc.exe",
    "C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"
)
$vlc = $vlcPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($vlc) {
    Write-Host "[OK] Dang mo VLC de xem camera: $RtspUrl" -ForegroundColor Green
    Start-Process $vlc -ArgumentList $RtspUrl
} elseif ($ffplay) {
    Write-Host "[OK] Dang mo ffplay de xem camera: $RtspUrl" -ForegroundColor Green
    Start-Process $ffplay.Source -ArgumentList "-fflags", "nobuffer", $RtspUrl
} else {
    Write-Host "[i] Hay mo VLC (Media -> Open Network Stream) va dan link sau:" -ForegroundColor Cyan
    Write-Host "    $RtspUrl" -ForegroundColor White
}
