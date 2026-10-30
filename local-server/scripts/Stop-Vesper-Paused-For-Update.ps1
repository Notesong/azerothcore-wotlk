[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$maintenanceRoot = 'C:\Files\Programs\Codex\Presence\working'
$maintenanceData = Join-Path $maintenanceRoot 'backend\data'
$maintenanceControl = Join-Path $maintenanceData 'runtime-game-player-control.json'
$maintenanceState = Get-Content -LiteralPath (Join-Path $maintenanceData 'runtime-game-player-state.json') -Raw | ConvertFrom-Json
$maintenancePause = Get-Content -LiteralPath $maintenanceControl -Raw | ConvertFrom-Json
if ($maintenancePause.paused -ne $true -or $maintenancePause.stop -eq $true) {
    throw 'Expected the already paused Vesper controller; no process was stopped.'
}
$maintenancePid = [int]$maintenanceState.pid
$maintenanceExe = Join-Path $maintenanceRoot 'backend\.venv\Scripts\python.exe'
function Assert-MaintenanceController($Candidate) {
    if ($Candidate.ExecutablePath -ne $maintenanceExe -or
        $Candidate.CommandLine -notmatch '[\\/]tools[\\/]game_player\.py' -or
        $Candidate.CommandLine -notlike '*Presence\working\local\game_player.config.json*') {
        throw 'The recorded process is not the expected Vesper controller; no replacement is allowed.'
    }
}
function Set-MaintenanceControl([bool]$StopRequested) {
    $maintenanceTemp = Join-Path $maintenanceData ('.commerce-control-' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        $maintenanceJson = @{paused=$true; stop=$StopRequested} | ConvertTo-Json -Compress
        [IO.File]::WriteAllText($maintenanceTemp, $maintenanceJson, (New-Object Text.UTF8Encoding($false)))
        [IO.File]::Replace($maintenanceTemp, $maintenanceControl, [System.Management.Automation.Language.NullString]::Value)
    } finally {
        if (Test-Path -LiteralPath $maintenanceTemp) { Remove-Item -LiteralPath $maintenanceTemp }
    }
}
if ($maintenancePid -gt 0) {
    $maintenanceProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $maintenancePid"
    if ($maintenanceProcess) {
        Assert-MaintenanceController $maintenanceProcess
        Set-MaintenanceControl $true
        $maintenanceDeadline = [DateTime]::UtcNow.AddSeconds(8)
        do {
            Start-Sleep -Milliseconds 250
            $maintenanceProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $maintenancePid"
        } while ($maintenanceProcess -and [DateTime]::UtcNow -lt $maintenanceDeadline)
        if ($maintenanceProcess) {
            Assert-MaintenanceController $maintenanceProcess
            & "$env:SystemRoot\System32\taskkill.exe" /PID $maintenancePid /T /F
            if ($LASTEXITCODE -ne 0) { throw 'The verified controller could not be stopped.' }
        }
        if (Get-CimInstance Win32_Process -Filter "ProcessId = $maintenancePid") {
            throw 'The old controller is still present; do not launch a replacement.'
        }
    }
}
Set-MaintenanceControl $false
Write-Host 'The verified controller is stopped; its saved pause remains set.'
