Set-StrictMode -Version Latest
$ErrorActionPreference = "SilentlyContinue"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "`n==> Stopping SPEECH TRAINER services..." -ForegroundColor Cyan

# Stop listeners by known service ports first (covers system python + venv python)
$servicePorts = @(5000, 7000, 7001, 7002, 7010, 7011)
$stoppedByPort = 0
foreach ($port in $servicePorts) {
    $listeners = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($conn in $listeners) {
        try {
            Write-Host "  Stopping port $port (PID $($conn.OwningProcess))" -ForegroundColor Yellow
            Stop-Process -Id $conn.OwningProcess -Force
            $stoppedByPort++
        } catch {}
    }
}

# Stop Python processes from our venvs
$venvPaths = @(
    (Join-Path $root ".venv"),
    (Join-Path $root "LIPSYNC\.venv"),
    (Join-Path $root "VOICE_GENERATOR\.venv"),
    (Join-Path $root "TALKING_AVATAR\.venv")
)

$stopped = 0
Get-Process python* -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        $procPath = $_.Path
        foreach ($venv in $venvPaths) {
            if ($procPath -and $procPath.StartsWith($venv)) {
                Write-Host "  Stopping: $($_.ProcessName) (PID $($_.Id))" -ForegroundColor Yellow
                Stop-Process -Id $_.Id -Force
                $stopped++
                break
            }
        }
    } catch {}
}

# Extra cleanup: kill python processes started from this workspace by command line.
$stoppedByCmd = 0
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        $cmd = [string]$_.CommandLine
        if ($cmd -and $cmd.ToLower().Contains($root.ToLower())) {
            $pid = [int]$_.ProcessId
            if ($pid -gt 0) {
                Write-Host "  Stopping by cmdline: python.exe (PID $pid)" -ForegroundColor Yellow
                Stop-Process -Id $pid -Force
                $stoppedByCmd++
            }
        }
    } catch {}
}

if (($stopped + $stoppedByPort + $stoppedByCmd) -gt 0) {
    Write-Host "`nStopped processes: by port=$stoppedByPort, by venv path=$stopped, by cmdline=$stoppedByCmd" -ForegroundColor Green
} else {
    Write-Host "`nNo SPEECH TRAINER Python processes found." -ForegroundColor Gray
}

Write-Host "`nNote: Ollama remains running for quick restart." -ForegroundColor Cyan
Write-Host "To stop Ollama: right-click tray icon -> Quit`n" -ForegroundColor Gray
