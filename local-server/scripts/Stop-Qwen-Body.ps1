[CmdletBinding()]
param()
& (Join-Path $PSScriptRoot 'Qwen-Body.ps1') -Action Stop
