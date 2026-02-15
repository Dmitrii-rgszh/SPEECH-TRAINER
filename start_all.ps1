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

function Test-OpenAICompat([string]$url) {
  try {
    $base = $url.TrimEnd("/")
    $resp = Invoke-WebRequest -Uri ("$base/v1/models") -Method Get -TimeoutSec 2 -ErrorAction Stop
    return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500)
  } catch {
    try {
      $base = $url.TrimEnd("/")
      $resp = Invoke-WebRequest -Uri ("$base/models") -Method Get -TimeoutSec 2 -ErrorAction Stop
      return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500)
    } catch {
      return $false
    }
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

$avatarPath = ""
if ($config -and $config.ui -and $config.ui.avatar_path) {
  $avatarPath = [string]$config.ui.avatar_path
}

$talkingUrl = "http://127.0.0.1:7011"
if ($config -and $config.lip_sync -and $config.lip_sync.url) {
  $talkingUrl = [string]$config.lip_sync.url
}
if ($talkingUrl.EndsWith("/")) { $talkingUrl = $talkingUrl.TrimEnd("/") }
if ($talkingUrl -match "^(https?://[^/]+)") {
  $talkingHealth = "$($Matches[1])/health"
} else {
  $talkingHealth = "http://127.0.0.1:7011/health"
}

$legacyLipUrl = "http://127.0.0.1:7002"
if ($config -and $config.lip_sync_legacy -and $config.lip_sync_legacy.url) {
  $legacyLipUrl = [string]$config.lip_sync_legacy.url
}
if ($legacyLipUrl.EndsWith("/")) { $legacyLipUrl = $legacyLipUrl.TrimEnd("/") }
if ($legacyLipUrl -match "^(https?://[^/]+)") {
  $legacyLipHealth = "$($Matches[1])/health"
} else {
  $legacyLipHealth = "http://127.0.0.1:7002/health"
}

$ttsHealth = "http://127.0.0.1:7001/health"
if ($config -and $config.voice_generator -and $config.voice_generator.url) {
  $voiceUrl = [string]$config.voice_generator.url
  if ($voiceUrl.EndsWith("/")) { $voiceUrl = $voiceUrl.TrimEnd("/") }
  if ($voiceUrl -match "^(https?://[^/]+)") {
    $ttsHealth = "$($Matches[1])/health"
  }
}

function Wait-Health([string]$name, [string]$url, [int]$timeoutSec = 60, [int]$sleepSec = 1) {
  Write-Step "Waiting for $name health"
  $deadline = (Get-Date).AddSeconds($timeoutSec)
  while ($true) {
    try {
      $resp = Invoke-RestMethod -Uri $url -TimeoutSec 2
      if ($resp.status -eq "ok") {
        Write-Host "$name ready" -ForegroundColor Green
        return $true
      }
    } catch {}
    if ((Get-Date) -gt $deadline) {
      Write-Host "$name did not respond at $url" -ForegroundColor Yellow
      return $false
    }
    Start-Sleep -Seconds $sleepSec
  }
}

Write-Step "Stopping stale local service processes (ports 5000/7000/7001/7002/7010/7011)"
$servicePorts = @(5000, 7000, 7001, 7002, 7010, 7011)
foreach ($port in $servicePorts) {
  $listeners = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
  foreach ($conn in $listeners) {
    try {
      Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
      Write-Host "Stopped process on port $port (PID $($conn.OwningProcess))" -ForegroundColor Yellow
    } catch {}
  }
}

if ($llmProvider -eq "ollama") {
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
} elseif ($llmProvider -eq "openai_compat") {
  Write-Step "Waiting for OpenAI-compatible LLM at $llmBaseUrl"
  $deadline = (Get-Date).AddSeconds(60)
  $ok = $false
  while ((Get-Date) -lt $deadline) {
    if (Test-OpenAICompat $llmBaseUrl) {
      $ok = $true
      break
    }
    Start-Sleep -Seconds 1
  }
  if (-not $ok) {
    Write-Host "OpenAI-compatible LLM не отвечает на $llmBaseUrl (ожидался LM Studio Local Server)." -ForegroundColor Red
    throw
  }
  Write-Host "OpenAI-compatible LLM is reachable." -ForegroundColor Green
} else {
  Write-Host "Unknown LLM provider '$llmProvider'. Supported: ollama, openai_compat." -ForegroundColor Red
  throw
}

# Resolve Python runtime for all services
Write-Step "Resolving Python runtime"
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

Write-Step "Starting TALKING_AVATAR server"
try {
  $taDir = Join-Path $root "TALKING_AVATAR"
  $taVenv = Join-Path $taDir ".venv"
  $taPy = Join-Path $taVenv "Scripts\python.exe"
  $useLipVenv = $false
  $env:TALKING_AVATAR_USE_LIPSYNC_VENV = "1"
  if ($env:TALKING_AVATAR_USE_LIPSYNC_VENV -eq "1") { $useLipVenv = $true }
  if (!(Test-Path -LiteralPath $taPy)) { $useLipVenv = $true }
  if ($useLipVenv) {
    $taPy = Join-Path $root "LIPSYNC\\.venv\\Scripts\\python.exe"
    Write-Host "Using LIPSYNC venv for TALKING_AVATAR" -ForegroundColor Yellow
  } else {
    Write-Step "Installing TALKING_AVATAR dependencies"
    & $taPy -m pip install -r ".\TALKING_AVATAR\requirements.txt" | Out-Host
    & $taPy -m pip install -r ".\TALKING_AVATAR\models\liveportrait\requirements.txt" | Out-Host
    & $taPy -m pip install -r ".\TALKING_AVATAR\models\wav2lip\requirements.txt" | Out-Host
  }

  $taOutLog = Join-Path $taDir "server_out.log"
  $taErrLog = Join-Path $taDir "server_err.log"
  Write-Host "TALKING_AVATAR logs: $taOutLog, $taErrLog" -ForegroundColor Gray
  if ($avatarPath) {
    $env:LIVEPORTRAIT_PREWARM = "1"
    $env:LIVEPORTRAIT_PREWARM_IMAGE = $avatarPath
    $env:LIVEPORTRAIT_PREWARM_SECONDS = "12"
  }
  if ($talkingUrl -match ":(\\d+)$") {
    $env:APP_PORT = $Matches[1]
  }
  Start-Process -FilePath $taPy -ArgumentList "app.py" `
    -WorkingDirectory $taDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $taOutLog `
    -RedirectStandardError $taErrLog
  Write-Host "TALKING_AVATAR server started" -ForegroundColor Green
} catch {
  Write-Host "Failed to start TALKING_AVATAR server. Run manually: $taPy .\TALKING_AVATAR\app.py" -ForegroundColor Yellow
}

Write-Step "Starting LIPSYNC server (legacy)"
try {
  Write-Step "Installing LIPSYNC dependencies"
  $lipVenv = Join-Path $root "LIPSYNC\.venv"
  $lipPy = Join-Path $lipVenv "Scripts\python.exe"
  if (!(Test-Path -LiteralPath $lipPy)) {
    Write-Step "Creating LIPSYNC venv (Python 3.10)"
    & py -3.10 -m venv $lipVenv
  }
  & $lipPy -m pip install -r ".\LIPSYNC\requirements.txt" | Out-Host
  $lipLogDir = Join-Path $root "LIPSYNC"
  $lipOutLog = Join-Path $lipLogDir "server_out.log"
  $lipErrLog = Join-Path $lipLogDir "server_err.log"
  Write-Host "LIPSYNC logs: $lipOutLog, $lipErrLog" -ForegroundColor Gray
  Start-Process -FilePath $lipPy -ArgumentList "app.py" `
    -WorkingDirectory $lipLogDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $lipOutLog `
    -RedirectStandardError $lipErrLog
  Write-Host "LIPSYNC server started (legacy)" -ForegroundColor Green
} catch {
  Write-Host "Failed to start LIPSYNC server. Run manually: $lipPy .\LIPSYNC\app.py" -ForegroundColor Yellow
}

$agentUrl = "http://127.0.0.1:7000/health"
[void](Wait-Health -name "AI-AGENT" -url $agentUrl -timeoutSec 45 -sleepSec 1)

# Warm up AI-AGENT / LLM so /health responds quickly later
try {
  $warm = @{ text = "ping" } | ConvertTo-Json -Depth 2
  Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:7000/chat" -ContentType "application/json" -Body $warm -TimeoutSec 60 | Out-Null
  Write-Host "AI-AGENT warmed up" -ForegroundColor Green
} catch {
  Write-Host "AI-AGENT warmup failed (continuing)" -ForegroundColor Yellow
}

[void](Wait-Health -name "VOICE_GENERATOR" -url $ttsHealth -timeoutSec 60 -sleepSec 1)
[void](Wait-Health -name "TALKING_AVATAR" -url $talkingHealth -timeoutSec 90 -sleepSec 2)
[void](Wait-Health -name "LIPSYNC (legacy)" -url $legacyLipHealth -timeoutSec 60 -sleepSec 1)

Write-Step "Starting STT server (python.py, backend + frontend)"
$sttOutLog = Join-Path $root "STT\server_out.log"
$sttErrLog = Join-Path $root "STT\server_err.log"
Write-Host "STT logs: $sttOutLog, $sttErrLog" -ForegroundColor Gray
Start-Process -FilePath $py -ArgumentList ".\python.py" `
  -WorkingDirectory $root `
  -WindowStyle Hidden `
  -RedirectStandardOutput $sttOutLog `
  -RedirectStandardError $sttErrLog

$sttUrl = "http://127.0.0.1:5000/health"
[void](Wait-Health -name "STT (backend + frontend)" -url $sttUrl -timeoutSec 60 -sleepSec 1)

Write-Host "`nAll services started." -ForegroundColor Green
Write-Host "Frontend/UI: http://127.0.0.1:5000" -ForegroundColor Cyan
Write-Host "Trainer:     http://127.0.0.1:5000/trainer" -ForegroundColor Cyan
