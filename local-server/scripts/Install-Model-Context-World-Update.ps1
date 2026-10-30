[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$updateRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
. (Join-Path $PSScriptRoot 'AzerothCore-Server.ps1') -Action Status
$updateWorldExe = Join-Path $updateRoot 'build\bin\RelWithDebInfo\worldserver.exe'
$updateWorldPdb = Join-Path $updateRoot 'build\bin\RelWithDebInfo\worldserver.pdb'
Assert-Files @($updateWorldExe, $updateWorldPdb)
$updateBackup = Join-Path $updateRoot ('model-context-integration\binary-backups\' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))
New-Item -ItemType Directory -Path $updateBackup -ErrorAction Stop | Out-Null
if (Get-OwnedProcess $WorldExe) {
    Write-Host 'Saving characters and restarting only the world server...'
    Request-WorldShutdown
    if (-not (Wait-ProcessExit $WorldExe 180)) {
        throw 'The world server did not finish saving and shutting down; nothing was replaced.'
    }
}
foreach ($updateName in @('worldserver.exe', 'worldserver.pdb')) {
    $updateInstalled = Join-Path $ServerDirectory $updateName
    if (Test-Path -LiteralPath $updateInstalled) {
        Copy-Item -LiteralPath $updateInstalled -Destination (Join-Path $updateBackup $updateName)
    }
    Copy-Item -LiteralPath (Join-Path (Split-Path -Parent $updateWorldExe) $updateName) -Destination $updateInstalled -Force
    if ((Get-FileHash -LiteralPath $updateInstalled).Hash -ne (Get-FileHash -LiteralPath (Join-Path (Split-Path -Parent $updateWorldExe) $updateName)).Hash) {
        throw "Installed $updateName hash mismatch."
    }
}
Start-IndependentProcess $WorldExe "-c `"$WorldConfig`"" $ServerDirectory
Wait-Listener 'World server' $WorldExe 8085 600
Wait-Listener 'World administration' $WorldExe 3443 60
Write-Host 'Moon protection and model context update installed; login server and database stayed running.'
Write-Host "Previous binaries: $updateBackup"
Show-Status
