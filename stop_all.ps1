Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "Stop services manually:" -ForegroundColor Cyan
Write-Host "- Закрой окно/терминал, где запущен STT (Ctrl+C)." -ForegroundColor Cyan
Write-Host "- Закрой окно/терминал, где запущен AI-AGENT (Ctrl+C)." -ForegroundColor Cyan
Write-Host "Ollama можно оставить запущенной для быстрого старта." -ForegroundColor Cyan
