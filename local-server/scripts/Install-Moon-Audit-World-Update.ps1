[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$auditRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
. (Join-Path $PSScriptRoot 'AzerothCore-Server.ps1') -Action Status
$auditBuildDirectory = Join-Path $auditRoot 'build\bin\RelWithDebInfo'
Assert-Files @((Join-Path $auditBuildDirectory 'worldserver.exe'), (Join-Path $auditBuildDirectory 'worldserver.pdb'))
$auditWasRunning = [bool](Get-OwnedProcess $WorldExe)
$auditBackup = Join-Path $auditRoot ('moon-audit-integration\binary-backups\' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))
New-Item -ItemType Directory -Path $auditBackup -ErrorAction Stop | Out-Null
if ($auditWasRunning) {
    Write-Host 'Saving characters and stopping only the world server for the audit update...'
    Request-WorldShutdown
    if (-not (Wait-ProcessExit $WorldExe 180)) {
        throw 'The world server did not finish saving; nothing was replaced.'
    }
}
foreach ($auditName in @('worldserver.exe', 'worldserver.pdb')) {
    $auditInstalled = Join-Path $ServerDirectory $auditName
    $auditBuilt = Join-Path $auditBuildDirectory $auditName
    if (Test-Path -LiteralPath $auditInstalled) {
        Copy-Item -LiteralPath $auditInstalled -Destination (Join-Path $auditBackup $auditName)
    }
    Copy-Item -LiteralPath $auditBuilt -Destination $auditInstalled -Force
    if ((Get-FileHash -LiteralPath $auditInstalled).Hash -ne (Get-FileHash -LiteralPath $auditBuilt).Hash) {
        throw "Installed $auditName hash mismatch."
    }
}
if ($auditWasRunning) {
    Start-IndependentProcess $WorldExe "-c `"$WorldConfig`"" $ServerDirectory
    Wait-Listener 'World server' $WorldExe 8085 600
    Wait-Listener 'World administration' $WorldExe 3443 60
    Write-Host 'World server restarted with Moon audit telemetry.'
} else {
    Write-Host 'World binary updated. The game server remains stopped.'
}
Write-Host "Previous binaries: $auditBackup"
