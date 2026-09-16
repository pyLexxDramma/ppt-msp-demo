# Starts local API + Cloudflare tunnel so Cloud/Vercel can download .mpp from this PC.
$ErrorActionPreference = "Stop"
$Root = "D:\AI_codding\Analitics\ppt-msp-demo"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Sample = Join-Path $Root "sample_data\msp_0feb8a44-a0f4-11ef-af7f-0050560219d5.mpp"
$UrlFile = Join-Path $Root "sample_data\windows_api_url.txt"
$LogFile = Join-Path $env:TEMP "ppt-msp-cloudflared.log"
$ApiPort = 8001
$UiPort = 8503
$Cloudflared = "C:\ProgramData\chocolatey\bin\cloudflared.exe"

if (-not (Test-Path $Python)) { throw "Missing venv: $Python" }
if (-not (Test-Path $Sample)) { throw "Missing sample mpp: $Sample" }
if (-not (Test-Path $Cloudflared)) { throw "Missing cloudflared: $Cloudflared" }

$com = & $Python -c "from demo.mpp_writer import project_available; print('yes' if project_available() else 'no')"
if ($com -ne "yes") { throw "MS Project / pywin32 not available." }

function Test-PortOpen([int]$Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

if (-not (Test-PortOpen $ApiPort)) {
    Start-Process -FilePath $Python -WorkingDirectory $Root -ArgumentList @(
        "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "$ApiPort"
    )
}

if (-not (Test-PortOpen $UiPort)) {
    $env:PPT_MSP_LOCAL_MPP = "1"
    Start-Process -FilePath $Python -WorkingDirectory $Root -ArgumentList @(
        "-m", "streamlit", "run", "demo_app.py",
        "--server.port", "$UiPort",
        "--server.headless", "true"
    )
}

Get-Process -Name cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
if (Test-Path $LogFile) { Remove-Item $LogFile -Force }

Start-Process -FilePath $Cloudflared -ArgumentList @(
    "tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:$ApiPort"
) -RedirectStandardError $LogFile -WindowStyle Minimized

$publicUrl = $null
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 1
    if (-not (Test-Path $LogFile)) { continue }
    $text = Get-Content -LiteralPath $LogFile -Raw -ErrorAction SilentlyContinue
    if ($text -match "https://(?!logs-)[a-z0-9-]+\.trycloudflare\.com") {
        $publicUrl = $Matches[0]
        break
    }
}
if (-not $publicUrl) { throw "Cloudflare tunnel failed. Log: $LogFile" }

Set-Content -LiteralPath $UrlFile -Value $publicUrl -Encoding ascii
$desk = Join-Path ([Environment]::GetFolderPath("Desktop")) "ppt-msp-windows-api.txt"
Set-Content -LiteralPath $desk -Value $publicUrl -Encoding ascii
Set-Clipboard -Value $publicUrl

Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:$UiPort"

Write-Host ""
Write-Host "Local form:   http://127.0.0.1:$UiPort"
Write-Host "Windows API:  $publicUrl"
Write-Host "Cloud secret: PPT_MSP_MPP_API = $publicUrl"
Write-Host "PC must stay on while the customer downloads the mpp."
