$PSScriptAnalyzerSettings = @{ ExcludeRules = @('PSAvoidUsingUnapprovedVerbs') }
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Write-Step([string]$text) {
  Write-Host ("\n==> " + $text) -ForegroundColor Cyan
}

function Test-Ollama([string]$url) {
  try {
    Invoke-RestMethod -Uri ("$url/api/tags") -TimeoutSec 2 | Out-Null
    return $true
  } catch {
    return $false
  }
}

function Get-OllamaDevice([string]$baseUrl, [string]$modelName) {
  try {
    $ps = Invoke-RestMethod -Uri ("$baseUrl/api/ps") -TimeoutSec 5
    if ($ps -and $ps.models) {
      foreach ($m in $ps.models) {
        $name = $m.name
        if ($name -and $name -eq $modelName) {
          $sizeVram = 0
          if ($m.size_vram) { $sizeVram = [int64]$m.size_vram }
          if ($sizeVram -gt 0) { return "GPU" }
          return "CPU"
        }
      }
    }
  } catch {}
  return "unknown"
}

function Get-Config() {
  if (Test-Path -LiteralPath ".\config.json") {
    try { return (Get-Content -LiteralPath ".\config.json" -Raw | ConvertFrom-Json) } catch { return $null }
  }
  return $null
}

# Ensure config.json exists (do not overwrite)
if (!(Test-Path -LiteralPath ".\config.json")) {
  if (Test-Path -LiteralPath ".\config.example.json") {
    Write-Step "config.json not found; creating from config.example.json"
    Copy-Item -LiteralPath ".\config.example.json" -Destination ".\config.json"
  } else {
    Write-Host "config.example.json not found; skipping config.json creation" -ForegroundColor Yellow
  }
}

$config = Get-Config

$llmProvider = "ollama"
$llmBaseUrl  = "http://localhost:11434"
$llmModel    = "qwen2.5:7b-instruct"

if ($config -and $config.llm) {
  if ($config.llm.provider) { $llmProvider = [string]$config.llm.provider }
  if ($config.llm.base_url) { $llmBaseUrl = [string]$config.llm.base_url }
  if ($config.llm.model)    { $llmModel = [string]$config.llm.model }
}

if ($llmProvider -ne "ollama") {
  Write-Host "LLM provider in config.json is '$llmProvider'. This script currently auto-starts Docker only for 'ollama'." -ForegroundColor Yellow
}

# Wait for Ollama HTTP (local)
Write-Step "Waiting for local Ollama at $llmBaseUrl"
$deadline = (Get-Date).AddSeconds(60)
$ok = $false
while ((Get-Date) -lt $deadline) {
  if (Test-Ollama $llmBaseUrl) {
    $ok = $true
    break
  }
  # Fallback to 127.0.0.1 if localhost resolution is problematic
  if ($llmBaseUrl -like "http://localhost:*") {
    $alt = $llmBaseUrl -replace "http://localhost", "http://127.0.0.1"
    if (Test-Ollama $alt) {
      Write-Host "Ollama reachable via $alt (using it for this run)." -ForegroundColor Yellow
      $llmBaseUrl = $alt
      $ok = $true
      break
    }
  }
  Start-Sleep -Seconds 1
}

if (-not $ok) {
  Write-Host "Ollama не отвечает на $llmBaseUrl. Убедись, что Ollama запущена (иконка в трее) и порт 11434 доступен." -ForegroundColor Red
  throw
}

# Pull model if missing
Write-Step "Ensuring model '$llmModel' is present"
$tags = Invoke-RestMethod -Uri ("$llmBaseUrl/api/tags") -TimeoutSec 10
$tags | ConvertTo-Json -Depth 6 | Out-Host
$hasModel = $false
if ($tags -and $tags.models) {
  foreach ($m in $tags.models) {
    if ($m.name -eq $llmModel) { $hasModel = $true; break }
  }
}

if (-not $hasModel) {
  Write-Host "Model not found in Ollama; pulling... (first time may take a while)" -ForegroundColor Yellow
  & ollama pull $llmModel

  # Re-check
  Write-Step "Re-checking /api/tags"
  $tags2 = Invoke-RestMethod -Uri ("$llmBaseUrl/api/tags") -TimeoutSec 30
  $tags2 | ConvertTo-Json -Depth 6 | Out-Host

  $hasModel2 = $false
  if ($tags2 -and $tags2.models) {
    foreach ($m in $tags2.models) {
      if ($m.name -eq $llmModel) { $hasModel2 = $true; break }
    }
  }
  if (-not $hasModel2) {
    Write-Host "Model still not visible via /api/tags." -ForegroundColor Yellow
    Write-Host "Try these diagnostics:" -ForegroundColor Yellow
    Write-Host "  ollama list" -ForegroundColor Yellow
    Write-Host "  ollama pull $llmModel" -ForegroundColor Yellow
  }
}

Write-Step "Checking LLM device (GPU/CPU)"
$device = Get-OllamaDevice $llmBaseUrl $llmModel
if ($device -eq "unknown") {
  try {
    $warmup = @{ model = $llmModel; messages = @(@{ role = "user"; content = "ping" }); stream = $false } | ConvertTo-Json -Depth 6
    Invoke-RestMethod -Method Post -Uri ("$llmBaseUrl/api/chat") -ContentType "application/json" -Body $warmup -TimeoutSec 60 | Out-Null
  } catch {}
  $device = Get-OllamaDevice $llmBaseUrl $llmModel
}

if ($device -eq "GPU") {
  Write-Host "LLM device: GPU" -ForegroundColor Green
} elseif ($device -eq "CPU") {
  Write-Host "LLM device: CPU" -ForegroundColor Yellow
} else {
  Write-Host "LLM device: unknown (check Ollama logs)" -ForegroundColor Yellow
}

# Start STT server
Write-Step "Starting STT server (python.py)"
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
$py = if (Test-Path -LiteralPath $venvPy) { $venvPy } else { "python" }

Write-Step "Starting AI-AGENT server"
try {
  Write-Step "Installing AI-AGENT dependencies"
  & $py -m pip install -r ".\AI-AGENT\requirements.txt" | Out-Host
  Start-Process -FilePath $py -ArgumentList ".\AI-AGENT\server.py" -WorkingDirectory $root -WindowStyle Minimized
} catch {
  Write-Host "Failed to start AI-AGENT server. Run manually: $py .\AI-AGENT\server.py" -ForegroundColor Yellow
}

Write-Step "Starting VOICE_GENERATOR server"
try {
  Write-Step "Installing VOICE_GENERATOR dependencies"
  $ttsVenv = Join-Path $root "VOICE_GENERATOR\.venv"
  $ttsPy = Join-Path $ttsVenv "Scripts\python.exe"
  if (!(Test-Path -LiteralPath $ttsPy)) {
    Write-Step "Creating VOICE_GENERATOR venv (Python 3.10)"
    & py -3.10 -m venv $ttsVenv
  }
  & $ttsPy -m pip install -r ".\VOICE_GENERATOR\requirements.txt" | Out-Host
  $condaCudnn = Join-Path $env:USERPROFILE "miniconda3\Library\bin"
  if (Test-Path -LiteralPath $condaCudnn) {
    $env:PATH = "$condaCudnn;$env:PATH"
  }
  Start-Process -FilePath $ttsPy -ArgumentList ".\VOICE_GENERATOR\app.py" -WorkingDirectory $root -WindowStyle Minimized
} catch {
  Write-Host "Failed to start VOICE_GENERATOR server. Run manually: $py .\VOICE_GENERATOR\app.py" -ForegroundColor Yellow
}

Write-Step "Starting LIPSYNC server"
try {
  Write-Step "Installing LIPSYNC dependencies"
  $lipVenv = Join-Path $root "LIPSYNC\.venv"
  $lipPy = Join-Path $lipVenv "Scripts\python.exe"
  if (!(Test-Path -LiteralPath $lipPy)) {
    Write-Step "Creating LIPSYNC venv (Python 3.10)"
    & py -3.10 -m venv $lipVenv
  }
  & $lipPy -m pip install -r ".\LIPSYNC\requirements.txt" | Out-Host
  
  # Start LIPSYNC server (original version)
  $lipLogDir = Join-Path $root "LIPSYNC"
  $lipOutLog = Join-Path $lipLogDir "server_out.log"
  $lipErrLog = Join-Path $lipLogDir "server_err.log"
  
  Write-Host "LIPSYNC logs: $lipOutLog, $lipErrLog" -ForegroundColor Gray
  Start-Process -FilePath $lipPy -ArgumentList "app.py" `
    -WorkingDirectory $lipLogDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $lipOutLog `
    -RedirectStandardError $lipErrLog
  
  Write-Host "LIPSYNC server started (original)" -ForegroundColor Green
} catch {
  Write-Host "Failed to start LIPSYNC server. Run manually: $lipPy .\LIPSYNC\app.py" -ForegroundColor Yellow
}

Write-Step "Waiting for AI-AGENT health"
$agentUrl = "http://127.0.0.1:7000/health"
$deadline2 = (Get-Date).AddSeconds(30)
while ($true) {
  try {
    $resp = Invoke-RestMethod -Uri $agentUrl -TimeoutSec 2
    if ($resp.status -eq "ok") { break }
  } catch {}
  if ((Get-Date) -gt $deadline2) {
    Write-Host "AI-AGENT did not respond at $agentUrl (continuing anyway)." -ForegroundColor Yellow
    break
  }
  Start-Sleep -Seconds 1
}

Write-Step "Waiting for LIPSYNC server health"
$lipUrl = "http://127.0.0.1:7002/health"
$deadline3 = (Get-Date).AddSeconds(60)  # LIPSYNC needs more time to load models
while ($true) {
  try {
    $resp = Invoke-RestMethod -Uri $lipUrl -TimeoutSec 2
    if ($resp.status -eq "ok") {
      Write-Host "LIPSYNC ready (models loaded)" -ForegroundColor Green
      break
    }
  } catch {}
  if ((Get-Date) -gt $deadline3) {
    Write-Host "LIPSYNC did not respond at $lipUrl (check server_out.log)" -ForegroundColor Yellow
    break
  }
  Start-Sleep -Seconds 2
}

Write-Step "Starting STT server (python.py)"
& $py ".\python.py"
