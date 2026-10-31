[CmdletBinding()]
param(
    [ValidateSet(16384, 32768)]
    [int]$ContextSize = 32768,
    [ValidateRange(5, 900)]
    [int]$StartupTimeoutSeconds = 180
)
& (Join-Path $PSScriptRoot 'Qwen-Body.ps1') -Action Start -ContextSize $ContextSize -StartupTimeoutSeconds $StartupTimeoutSeconds
