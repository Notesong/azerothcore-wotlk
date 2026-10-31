$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
# Plan only defines functions and returns fixed launch metadata: no files,
# ports, processes, models or configuration are changed by these checks.
$plan = . (Join-Path $PSScriptRoot 'Qwen-Body.ps1') -Action Plan
if ($plan.BaseUrl -ne 'http://127.0.0.1:8082/v1' -or $plan.ContextSize -ne 32768) { throw 'Dedicated endpoint/context plan is incorrect.' }
if ($plan.Alias -ne 'qwen3.5-4b-action' -or $plan.Model -notlike '*Qwen3.5-4B-UD-MTP-Q4_K_XL.gguf') { throw 'The dedicated body plan does not select the reviewed 4B quant.' }
if ($plan.Arguments -contains '--spec-type' -or $plan.Arguments -contains '--mmproj') { throw 'Baseline unexpectedly enables MTP or a projector.' }
if ($plan.Arguments -notcontains '--no-mmproj' -or $plan.Arguments -notcontains '--no-warmup') { throw 'Baseline projector/warmup controls missing.' }
if ((ConvertTo-QwenWindowsArgument '{"enable_thinking":false}') -ne '"{\"enable_thinking\":false}"') { throw 'Windows JSON argument quoting failed.' }
if ((ConvertTo-QwenWindowsArgument 'C:\folder with spaces\') -ne '"C:\folder with spaces\\"') { throw 'Windows trailing slash quoting failed.' }
if ((ConvertTo-QwenWindowsArgument '') -ne '""') { throw 'Windows empty argument quoting failed.' }
$created = [datetime]'2026-10-31T16:00:00Z'
$fakeProcess = [pscustomobject]@{ ProcessId = 12345; ExecutablePath = $QwenExecutable; CommandLine = $QwenCommandLine; CreationDate = $created }
$fakeState = [pscustomobject]@{ schema = 'qwen-action-owner/v1'; pid = 12345; port = 8082; alias = $QwenAlias
    model_path = $QwenModelPath; executable_path = $QwenExecutable; created_at_utc = $created.ToUniversalTime().ToString('o')
    command_line_sha256 = $QwenExpectedCommandHash }
if (-not (Test-QwenOwnedProcess $fakeState $fakeProcess)) { throw 'Exact owned process was rejected.' }
$roundTrippedState = $fakeState | ConvertTo-Json | ConvertFrom-Json
if (-not (Test-QwenOwnedProcess $roundTrippedState $fakeProcess)) { throw 'Owned process was rejected after JSON date roundtrip.' }
$differentInstant = $fakeState | ConvertTo-Json | ConvertFrom-Json
$differentInstant.created_at_utc = $created.AddTicks(1).ToUniversalTime().ToString('o')
if (Test-QwenOwnedProcess $differentInstant $fakeProcess) { throw 'Creation time comparison accepted a different UTC tick.' }
foreach ($mutation in @('pid', 'created_at_utc', 'command_line_sha256', 'model_path', 'port', 'alias')) {
    $copy = $fakeState | ConvertTo-Json | ConvertFrom-Json
    if ($mutation -eq 'pid') { $copy.pid = 23456 }
    elseif ($mutation -eq 'port') { $copy.port = 8081 }
    else { $copy.$mutation = 'different' }
    if (Test-QwenOwnedProcess $copy $fakeProcess) { throw "Unsafe process accepted after $mutation change." }
}
$otherProcess = [pscustomobject]@{ ProcessId = 12345; ExecutablePath = $QwenExecutable; CommandLine = 'llama-server.exe --port 8081'; CreationDate = $created }
if (Test-QwenOwnedProcess $fakeState $otherProcess) { throw 'Gemma helper command line was accepted as Qwen.' }
if (Test-QwenOwnedProcess $null $fakeProcess) { throw 'Untracked process was accepted.' }
Write-Output 'Qwen launcher plan, quoting and ownership checks passed; no runtime was started.'
