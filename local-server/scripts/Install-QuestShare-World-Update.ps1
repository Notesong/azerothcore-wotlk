[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$updateRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
. (Join-Path $PSScriptRoot 'AzerothCore-Server.ps1') -Action Status
$updateWorldExe = Join-Path $updateRoot 'build\bin\RelWithDebInfo\worldserver.exe'
$updateWorldPdb = Join-Path $updateRoot 'build\bin\RelWithDebInfo\worldserver.pdb'
Assert-Files @($updateWorldExe, $updateWorldPdb)
$updateBackup = Join-Path $updateRoot ('quest-share-integration\binary-backups\' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))
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
}
Copy-Item -LiteralPath $updateWorldExe -Destination $WorldExe -Force
Copy-Item -LiteralPath $updateWorldPdb -Destination (Join-Path $ServerDirectory 'worldserver.pdb') -Force
if ((Get-FileHash -LiteralPath $WorldExe).Hash -ne (Get-FileHash -LiteralPath $updateWorldExe).Hash) {
    throw 'Installed world binary hash mismatch.'
}
Start-IndependentProcess $WorldExe "-c `"$WorldConfig`"" $ServerDirectory
Wait-Listener 'World server' $WorldExe 8085 600
Wait-Listener 'World administration' $WorldExe 3443 60
Write-Host 'Quest-sharing update installed; login server and database stayed running.'
Write-Host "Previous binaries: $updateBackup"
Show-Status
