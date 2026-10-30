[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$controllerRoot = 'C:\Files\Programs\Codex\Presence\working'
$controllerExe = Join-Path $controllerRoot 'backend\.venv\Scripts\python.exe'
$controllerControl = Join-Path $controllerRoot 'backend\data\runtime-game-player-control.json'
$controllerPause = Get-Content -LiteralPath $controllerControl -Raw | ConvertFrom-Json
if ($controllerPause.paused -ne $true -or $controllerPause.stop -eq $true) {
    throw 'Expected the explicit saved pause before stopping these verified controller copies.'
}
$controllerPids = @(27044, 17052)
foreach ($controllerPid in $controllerPids) {
    $controllerProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $controllerPid"
    if (-not $controllerProcess) { continue }
    if ($controllerProcess.ExecutablePath -ne $controllerExe -or
        $controllerProcess.CommandLine -notmatch '[\\/]tools[\\/]game_player\.py' -or
        $controllerProcess.CommandLine -notlike '*Presence\working\local\game_player.config.json*') {
        throw "PID $controllerPid no longer matches the verified Vesper controller; nothing stopped."
    }
}
$controllerArchive = Join-Path 'C:\Games\AzerothCore\model-context-integration' ('before-controller-cleanup\' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))
New-Item -ItemType Directory -Path $controllerArchive -ErrorAction Stop | Out-Null
foreach ($controllerName in @('state', 'status', 'control')) {
    $controllerSource = Join-Path $controllerRoot "backend\data\runtime-game-player-$controllerName.json"
    Copy-Item -LiteralPath $controllerSource -Destination $controllerArchive
}
foreach ($controllerPid in $controllerPids) {
    $controllerProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $controllerPid"
    if (-not $controllerProcess) { continue }
    if ($controllerProcess.ExecutablePath -ne $controllerExe -or
        $controllerProcess.CommandLine -notmatch '[\\/]tools[\\/]game_player\.py' -or
        $controllerProcess.CommandLine -notlike '*Presence\working\local\game_player.config.json*') {
        throw "PID $controllerPid changed identity; no further process was stopped."
    }
    & "$env:SystemRoot\System32\taskkill.exe" /PID $controllerPid /T /F
    if ($LASTEXITCODE -ne 0) { throw "Could not stop verified controller tree $controllerPid." }
}
Start-Sleep -Milliseconds 500
foreach ($controllerPid in @(27044, 7992, 17052, 23404)) {
    if (Get-Process -Id $controllerPid -ErrorAction SilentlyContinue) {
        throw "Known controller process $controllerPid is still present; do not launch a replacement."
    }
}
Write-Host 'Both verified paused controller trees stopped. Vesper remains attached to the world server.'
