[CmdletBinding()]
param(
    [ValidateSet('Start', 'Stop', 'Status', 'Plan')]
    [string]$Action = 'Status',
    [ValidateSet(16384, 32768)]
    [int]$ContextSize = 32768,
    [ValidateRange(5, 900)]
    [int]$StartupTimeoutSeconds = 180
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$QwenTaskRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$QwenPrivateDirectory = Join-Path $QwenTaskRoot 'local-qwen-private'
$QwenStatePath = Join-Path $QwenPrivateDirectory 'owner-state.json'
$QwenLogPath = Join-Path $QwenPrivateDirectory 'server.log'
$QwenExecutable = 'C:\Users\aurenne\AppData\Local\Microsoft\WinGet\Packages\ggml.llamacpp_Microsoft.Winget.Source_8wekyb3d8bbwe\llama-server.exe'
$QwenModelPath = 'E:\unsloth\Qwen3.5-4B-MTP-GGUF\Qwen3.5-4B-UD-MTP-Q4_K_XL.gguf'
$QwenPort = 8082
$QwenAlias = 'qwen3.5-4b-action'
$QwenBaseUrl = 'http://127.0.0.1:8082/v1'

function Get-QwenTextHash([string]$Text) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($Text)
        return ([BitConverter]::ToString($algorithm.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    } finally { $algorithm.Dispose() }
}

function ConvertTo-QwenWindowsArgument([string]$Value) {
    # Windows CRT quoting, with no intervening cmd.exe or PowerShell command string.
    $result = New-Object Text.StringBuilder
    [void]$result.Append('"')
    $slashes = 0
    foreach ($character in $Value.ToCharArray()) {
        if ($character -eq '\') { $slashes++; continue }
        if ($character -eq '"') {
            [void]$result.Append(('\' * (2 * $slashes + 1)))
            [void]$result.Append('"')
        } else {
            [void]$result.Append(('\' * $slashes))
            [void]$result.Append($character)
        }
        $slashes = 0
    }
    [void]$result.Append(('\' * (2 * $slashes)))
    [void]$result.Append('"')
    return $result.ToString()
}

$QwenArguments = @(
    '-m', $QwenModelPath, '--host', '127.0.0.1', '--port', [string]$QwenPort,
    '--alias', $QwenAlias, '--ctx-size', [string]$ContextSize,
    '--parallel', '1', '--threads', '8', '--threads-batch', '8',
    '--gpu-layers', 'all', '--cache-ram', '0', '--no-warmup', '--no-mmproj',
    '--reasoning', 'off', '--reasoning-budget', '0',
    '--chat-template-kwargs', '{"enable_thinking":false}',
    '--log-file', $QwenLogPath, '--log-timestamps'
)
# 32k leaves room for the observed >11k dynamic context plus stable persona and
# the action schema. MTP and a vision projector remain disabled for this baseline.
$QwenCommandLine = (@($QwenExecutable) + $QwenArguments | ForEach-Object { ConvertTo-QwenWindowsArgument $_ }) -join ' '
$QwenExpectedCommandHash = Get-QwenTextHash $QwenCommandLine

function Assert-QwenPrivatePath {
    $resolved = [IO.Path]::GetFullPath($QwenPrivateDirectory)
    if (-not $resolved.StartsWith($QwenTaskRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'The Qwen private directory is outside this AzerothCore workspace.'
    }
    if (Test-Path -LiteralPath $QwenPrivateDirectory) {
        $item = Get-Item -LiteralPath $QwenPrivateDirectory -Force
        if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'The Qwen private directory must be an ordinary local folder.'
        }
    }
}

function Initialize-QwenPrivateDirectory {
    Assert-QwenPrivatePath
    if (-not (Test-Path -LiteralPath $QwenPrivateDirectory)) {
        [void](New-Item -ItemType Directory -Path $QwenPrivateDirectory)
    }
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true, $false)
    $acl.SetOwner($identity.User)
    $inherit = [Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit'
    foreach ($sid in @($identity.User, (New-Object Security.Principal.SecurityIdentifier('S-1-5-18')))) {
        $rule = New-Object Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', $inherit, 'None', 'Allow')
        [void]$acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $QwenPrivateDirectory -AclObject $acl
}

function Get-QwenState {
    Assert-QwenPrivatePath
    if (-not (Test-Path -LiteralPath $QwenStatePath -PathType Leaf)) { return $null }
    $item = Get-Item -LiteralPath $QwenStatePath -Force
    if ($item.Length -gt 8192 -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'The Qwen ownership record is not a small ordinary file.'
    }
    try { return Get-Content -LiteralPath $QwenStatePath -Raw | ConvertFrom-Json }
    catch { throw 'The Qwen ownership record is invalid; no process was stopped.' }
}

function Get-QwenProcess([int]$ProcessId) {
    return Get-CimInstance -ClassName Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction Stop
}

function Test-QwenOwnedProcess($State, $Process) {
    if (-not $State -or -not $Process) { return $false }
    try {
        if ($State.schema -ne 'qwen-action-owner/v1' -or [int]$State.pid -le 0 -or
            [int]$State.pid -ne [int]$Process.ProcessId -or [int]$State.port -ne $QwenPort -or
            $State.alias -ne $QwenAlias -or $State.model_path -ne $QwenModelPath -or
            -not [string]::Equals([string]$State.executable_path, $QwenExecutable, [StringComparison]::OrdinalIgnoreCase) -or
            -not [string]::Equals([string]$Process.ExecutablePath, $QwenExecutable, [StringComparison]::OrdinalIgnoreCase)) { return $false }
        # PowerShell 7 parses JSON ISO dates as DateTime; Windows PowerShell 5
        # preserves strings. Compare the exact UTC instant in both hosts.
        $createdTicks = ([datetime]$Process.CreationDate).ToUniversalTime().Ticks
        $recordedTicks = ([datetime]$State.created_at_utc).ToUniversalTime().Ticks
        return $recordedTicks -eq $createdTicks -and
            $State.command_line_sha256 -eq (Get-QwenTextHash ([string]$Process.CommandLine))
    } catch { return $false }
}

function Get-QwenListeners {
    $netstat = Join-Path $env:SystemRoot 'System32\netstat.exe'
    foreach ($line in @(& $netstat '-ano' '-p' 'TCP')) {
        if ($line -match '^\s*TCP\s+(?<endpoint>\S+):(?<port>\d+)\s+\S+\s+LISTENING\s+(?<owner>\d+)\s*$' -and
            [int]$Matches.port -eq $QwenPort) {
            [pscustomobject]@{ Address = $Matches.endpoint; ProcessId = [int]$Matches.owner }
        }
    }
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect the Qwen listener.' }
}

function Assert-QwenListenerOwnership($State, $Process) {
    foreach ($listener in @(Get-QwenListeners)) {
        if ($listener.Address -ne '127.0.0.1' -or -not (Test-QwenOwnedProcess $State $Process) -or
            $listener.ProcessId -ne [int]$State.pid) {
            throw 'Port 8082 is occupied by an unverified or non-loopback process. No process was stopped.'
        }
    }
}

function Test-QwenReady {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8082/health' -TimeoutSec 2
        if ($health.status -ne 'ok') { return $false }
        $models = Invoke-RestMethod -Uri 'http://127.0.0.1:8082/v1/models' -TimeoutSec 2
        return @($models.data | Where-Object { $_.id -eq $QwenAlias }).Count -gt 0
    } catch { return $false }
}

function Save-QwenState($State) {
    $temporary = Join-Path $QwenPrivateDirectory ('owner-state-' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        $json = $State | ConvertTo-Json -Depth 4
        [IO.File]::WriteAllText($temporary, $json, (New-Object Text.UTF8Encoding($false)))
        Move-Item -LiteralPath $temporary -Destination $QwenStatePath -Force
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
    }
}

function Show-QwenStatus {
    $state = Get-QwenState
    $process = if ($state) { Get-QwenProcess ([int]$state.pid) } else { $null }
    Assert-QwenListenerOwnership $state $process
    if ($process -and -not (Test-QwenOwnedProcess $state $process)) {
        throw 'The saved PID belongs to another process. No process was stopped.'
    }
    [pscustomobject]@{ Model = $QwenAlias; BaseUrl = $QwenBaseUrl
        State = if (-not $process) { 'stopped' } elseif (Test-QwenReady) { 'ready' } else { 'starting' }
        ProcessId = if ($process) { [int]$process.ProcessId } else { 0 }
    }
}

function Start-QwenBody {
    foreach ($path in @($QwenExecutable, $QwenModelPath)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required Qwen runtime file is missing: $path" }
    }
    $state = Get-QwenState
    $process = if ($state) { Get-QwenProcess ([int]$state.pid) } else { $null }
    Assert-QwenListenerOwnership $state $process
    if ($process) {
        if (-not (Test-QwenOwnedProcess $state $process)) { throw 'The saved PID is not this Qwen process; nothing was changed.' }
        if ($state.command_line_sha256 -ne $QwenExpectedCommandHash) { throw 'Qwen is already running with different settings. Stop its owned runtime before changing context size.' }
        Show-QwenStatus
        return
    }
    Initialize-QwenPrivateDirectory
    if (Test-Path -LiteralPath $QwenStatePath) {
        $archive = Join-Path $QwenPrivateDirectory 'history'
        if (-not (Test-Path -LiteralPath $archive)) { [void](New-Item -ItemType Directory -Path $archive) }
        $stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-ffff')
        Copy-Item -LiteralPath $QwenStatePath -Destination (Join-Path $archive ($stamp + '-owner-state.json'))
        if (Test-Path -LiteralPath $QwenLogPath -PathType Leaf) {
            Copy-Item -LiteralPath $QwenLogPath -Destination (Join-Path $archive ($stamp + '-server.log'))
        }
    }
    # Detached + breakaway WMI process survives the launching app's job/console.
    # ShowWindow=0 is the explicit hidden-window policy for this native helper.
    $startup = New-CimInstance -ClassName Win32_ProcessStartup -Namespace root/cimv2 -ClientOnly -Property @{
        CreateFlags = [uint32]0x01000008; ShowWindow = [uint16]0
    }
    $created = Invoke-CimMethod -ClassName Win32_Process -Namespace root/cimv2 -MethodName Create -Arguments @{
        CommandLine = $QwenCommandLine; CurrentDirectory = $QwenPrivateDirectory; ProcessStartupInformation = $startup
    }
    if ($created.ReturnValue -ne 0 -or $created.ProcessId -le 0) { throw 'Windows could not start the dedicated Qwen action runtime.' }
    $process = Get-QwenProcess ([int]$created.ProcessId)
    if (-not $process) { throw 'The dedicated Qwen runtime exited immediately. Check its private server.log.' }
    $state = [pscustomobject]@{
        schema = 'qwen-action-owner/v1'; pid = [int]$process.ProcessId; port = $QwenPort; alias = $QwenAlias
        executable_path = $QwenExecutable; model_path = $QwenModelPath
        created_at_utc = ([datetime]$process.CreationDate).ToUniversalTime().ToString('o')
        command_line_sha256 = $QwenExpectedCommandHash; context_size = $ContextSize
    }
    if (-not (Test-QwenOwnedProcess $state $process)) { throw 'The newly created process did not match the fixed Qwen command; no unrelated process was stopped.' }
    Save-QwenState $state
    $deadline = [DateTime]::UtcNow.AddSeconds($StartupTimeoutSeconds)
    do {
        $process = Get-QwenProcess ([int]$state.pid)
        if (-not $process) { throw 'Qwen exited during model loading. Check local-qwen-private/server.log.' }
        Assert-QwenListenerOwnership $state $process
        if (Test-QwenReady) { Show-QwenStatus; return }
        Start-Sleep -Seconds 2
    } while ([DateTime]::UtcNow -lt $deadline)
    throw 'Qwen is still loading after the startup deadline. It was left running; inspect Status and its private log.'
}

function Stop-QwenBody {
    $state = Get-QwenState
    $process = if ($state) { Get-QwenProcess ([int]$state.pid) } else { $null }
    Assert-QwenListenerOwnership $state $process
    if (-not $process) { Show-QwenStatus; return }
    if (-not (Test-QwenOwnedProcess $state $process)) { throw 'The saved PID is not the owned Qwen runtime. No process was stopped.' }
    Stop-Process -Id ([int]$state.pid) -ErrorAction Stop
    for ($attempt = 0; $attempt -lt 25; $attempt++) {
        $candidate = Get-QwenProcess ([int]$state.pid)
        if (-not $candidate -or -not (Test-QwenOwnedProcess $state $candidate)) { Show-QwenStatus; return }
        Start-Sleep -Milliseconds 200
    }
    throw 'The dedicated Qwen process has not exited yet. No other process was stopped.'
}

switch ($Action) {
    'Plan' { [pscustomobject]@{ Executable = $QwenExecutable; Model = $QwenModelPath; Alias = $QwenAlias
        BaseUrl = $QwenBaseUrl; ContextSize = $ContextSize; Arguments = $QwenArguments
        CommandLineSha256 = $QwenExpectedCommandHash; PrivateLog = $QwenLogPath } }
    'Start' { Start-QwenBody }
    'Stop' { Stop-QwenBody }
    'Status' { Show-QwenStatus }
}
