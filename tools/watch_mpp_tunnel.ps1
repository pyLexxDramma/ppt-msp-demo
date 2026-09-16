# Keep the Cloudflare quick tunnel alive; restart only after several failed health checks.
$Root = "D:\AI_codding\Analitics\ppt-msp-demo"
$UrlFile = Join-Path $Root "sample_data\windows_api_url.txt"
$Cloudflared = "C:\ProgramData\chocolatey\bin\cloudflared.exe"
$ApiPort = 8001
$Fails = 0

function Get-Url {
    if (-not (Test-Path $UrlFile)) { return $null }
    return (Get-Content -LiteralPath $UrlFile -Raw).Trim()
}

function Test-PublicOk([string]$Url) {
    if (-not $Url) { return $false }
    try {
        $r = Invoke-WebRequest -Uri ($Url + "/api/health") -UseBasicParsing -TimeoutSec 20
        return $r.Content -match '"ok":true'
    } catch {
        return $false
    }
}

function Restart-Tunnel {
    Get-Process -Name cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
    $runLog = Join-Path $env:TEMP ("ppt-msp-cf-" + [guid]::NewGuid().ToString("N").Substring(0, 8) + ".log")
    Start-Process -FilePath $Cloudflared -ArgumentList @(
        "tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:$ApiPort"
    ) -RedirectStandardError $runLog -WindowStyle Minimized
    $publicUrl = $null
    for ($i = 0; $i -lt 50; $i++) {
        Start-Sleep -Seconds 1
        if (-not (Test-Path $runLog)) { continue }
        $text = Get-Content -LiteralPath $runLog -Raw -ErrorAction SilentlyContinue
        if ($text -match "https://(?!logs-)[a-z0-9-]+\.trycloudflare\.com") {
            $publicUrl = $Matches[0]
            break
        }
    }
    if (-not $publicUrl) { return }
    Set-Content -LiteralPath $UrlFile -Value $publicUrl -Encoding ascii
    $desk = Join-Path ([Environment]::GetFolderPath("Desktop")) "ppt-msp-windows-api.txt"
    Set-Content -LiteralPath $desk -Value $publicUrl -Encoding ascii
    # wait for DNS before the next health loop
    Start-Sleep -Seconds 25
}

Start-Sleep -Seconds 45
while ($true) {
    $url = Get-Url
    if (Test-PublicOk $url) {
        $Fails = 0
    } else {
        $Fails++
        if ($Fails -ge 3) {
            $Fails = 0
            Restart-Tunnel
        }
    }
    Start-Sleep -Seconds 30
}
