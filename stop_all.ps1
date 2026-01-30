Set-StrictMode -Version Latest
$ErrorActionPreference = "SilentlyContinue"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "`n==> Stopping SPEECH TRAINER services..." -ForegroundColor Cyan

# Stop Python processes from our venvs
$venvPaths = @(
    (Join-Path $root ".venv"),
    (Join-Path $root "LIPSYNC\.venv"),
    (Join-Path $root "VOICE_GENERATOR\.venv")
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

if ($stopped -gt 0) {
    Write-Host "`n$stopped Python process(es) stopped." -ForegroundColor Green
} else {
    Write-Host "`nNo SPEECH TRAINER Python processes found." -ForegroundColor Gray
}

Write-Host "`nNote: Ollama remains running for quick restart." -ForegroundColor Cyan
Write-Host "To stop Ollama: right-click tray icon -> Quit`n" -ForegroundColor Gray
