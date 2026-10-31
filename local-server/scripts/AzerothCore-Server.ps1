[CmdletBinding()]
param(
    [ValidateSet('Start', 'Stop', 'Status', 'WorldConsole')]
    [string]$Action = 'Status',
    [ValidateRange(10, 3600)]
    [int]$StartupTimeoutSeconds = 600
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$ServerDirectory = Join-Path $Root 'server'
$WorldExe = Join-Path $ServerDirectory 'worldserver.exe'
$AuthExe = Join-Path $ServerDirectory 'authserver.exe'
$MySqlDirectory = Join-Path $Root 'tools\mysql-8.4.13-winx64\bin'
$MySqlExe = Join-Path $MySqlDirectory 'mysqld.exe'
$MySqlAdminExe = Join-Path $MySqlDirectory 'mysqladmin.exe'
$MySqlIni = Join-Path $Root 'mysql.ini'
$DatabaseCredentials = Join-Path $Root 'database-admin.cnf'
$ServerCredentials = Join-Path $Root 'server-admin.json'
$AuthConfig = Join-Path $ServerDirectory 'configs\authserver.conf'
$WorldConfig = Join-Path $ServerDirectory 'configs\worldserver.conf'

function Start-IndependentProcess([string]$Executable, [string]$Arguments, [string]$Directory) {
    Assert-Files @($Executable)
    # WMI creates the process outside the calling application's process tree.
    # BREAKAWAY also avoids the WMI provider's quota job; DETACHED avoids console ownership.
    $startup = New-CimInstance -ClassName Win32_ProcessStartup -Namespace root/cimv2 -ClientOnly -Property @{
        CreateFlags = [uint32]0x01000008
        ShowWindow = [uint16]0
    }
    $commandLine = '"' + $Executable + '" ' + $Arguments
    $created = Invoke-CimMethod -ClassName Win32_Process -Namespace root/cimv2 -MethodName Create -Arguments @{
        CommandLine = $commandLine
        CurrentDirectory = $Directory
        ProcessStartupInformation = $startup
    }
    if ($created.ReturnValue -ne 0 -or $created.ProcessId -le 0) {
        throw "Could not launch $([IO.Path]::GetFileName($Executable)) independently (Windows result $($created.ReturnValue)). No attached fallback was used."
    }
    $started = Get-CimInstance Win32_Process -Filter "ProcessId = $($created.ProcessId)"
    if (-not $started -or -not [string]::Equals($started.ExecutablePath, $Executable, [StringComparison]::OrdinalIgnoreCase)) {
        throw "The independent $([IO.Path]::GetFileName($Executable)) process did not remain running. Check its log."
    }
}

function Get-OwnedProcess([string]$Executable) {
    $name = [IO.Path]::GetFileNameWithoutExtension($Executable)
    $matches = @(foreach ($candidate in @(Get-Process -Name $name -ErrorAction SilentlyContinue)) {
        $processPath = $candidate.Path
        if ($processPath -and [string]::Equals(
            [IO.Path]::GetFullPath($processPath), $Executable,
            [StringComparison]::OrdinalIgnoreCase)) {
            [pscustomobject]@{ ProcessId = $candidate.Id; ExecutablePath = $processPath }
        }
    })
    if ($matches.Count -gt 1) {
        throw "More than one process uses $Executable. Close the duplicate manually before continuing."
    }
    if ($matches.Count -eq 1) { return $matches[0] }
    return $null
}

function Get-Listeners([int]$Port) {
    # netstat works without the WMI/CIM permissions required by Get-NetTCPConnection.
    $netstatExe = Join-Path $env:SystemRoot 'System32\netstat.exe'
    $lines = @(& $netstatExe '-ano' '-p' 'TCP')
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect local TCP listeners.' }
    foreach ($line in $lines) {
        if ($line -match '^\s*TCP\s+\S+:(?<port>\d+)\s+\S+\s+LISTENING\s+(?<owner>\d+)\s*$') {
            if ([int]$Matches.port -eq $Port) {
                [pscustomobject]@{ OwningProcess = [int]$Matches.owner }
            }
        }
    }
}

function Assert-PortOwnership([int]$Port, [string]$Executable) {
    $process = Get-OwnedProcess $Executable
    $listeners = @(Get-Listeners $Port)
    foreach ($listener in $listeners) {
        if (-not $process -or $listener.OwningProcess -ne $process.ProcessId) {
            throw "Port $Port is in use by another process (PID $($listener.OwningProcess)). No process was stopped."
        }
    }
}

function Test-OwnedListener([int]$Port, [string]$Executable) {
    $process = Get-OwnedProcess $Executable
    if (-not $process) { return $false }
    foreach ($listener in @(Get-Listeners $Port)) {
        if ($listener.OwningProcess -eq $process.ProcessId) { return $true }
    }
    return $false
}

function Assert-Files([string[]]$Paths) {
    foreach ($path in $Paths) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Required file is missing: $path"
        }
    }
}

function Wait-Listener([string]$Name, [string]$Executable, [int]$Port, [int]$TimeoutSeconds) {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        Assert-PortOwnership $Port $Executable
        if (Test-OwnedListener $Port $Executable) { return }
        if (-not (Get-OwnedProcess $Executable)) {
            throw "$Name exited before it was ready. Check its console and log files."
        }
        Start-Sleep -Seconds 2
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "$Name is still starting after $TimeoutSeconds seconds. Check Server Status.cmd and its logs before trying again."
}

function Wait-ProcessExit([string]$Executable, [int]$TimeoutSeconds) {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        if (-not (Get-OwnedProcess $Executable)) { return $true }
        Start-Sleep -Seconds 1
    } while ([DateTime]::UtcNow -lt $deadline)
    return $false
}

function Show-Status {
    foreach ($service in @(
        @{ Name = 'Database'; Exe = $MySqlExe; Port = 3307 },
        @{ Name = 'Login server'; Exe = $AuthExe; Port = 3724 },
        @{ Name = 'World server'; Exe = $WorldExe; Port = 8085 }
    )) {
        $process = Get-OwnedProcess $service.Exe
        if (-not $process) {
            $description = 'stopped'
            if (@(Get-Listeners $service.Port).Count -gt 0) {
                $description += " (port $($service.Port) is occupied by another process)"
            }
        } elseif (Test-OwnedListener $service.Port $service.Exe) {
            $description = "ready (PID $($process.ProcessId), port $($service.Port))"
        } else {
            $description = "running, port not ready (PID $($process.ProcessId))"
        }
        Write-Host ('{0,-14} {1}' -f $service.Name, $description)
    }
    Write-Host "`nClient realm address: 127.0.0.1"
}

function Ensure-VesperOnline {
    $loginScript = Join-Path $Root 'scripts\Ensure-Vesper-Online.py'
    $pythonExe = 'C:\Files\Programs\Codex\Presence\working\backend\.venv\Scripts\python.exe'
    Assert-Files @($loginScript, $pythonExe, $ServerCredentials)
    Write-Host "Checking Vesper's character login..."
    & $pythonExe '-B' $loginScript
    if ($LASTEXITCODE -ne 0) {
        throw ('The game services are ready, but Vesper could not log in. ' +
            'Check the login error above, then retry Start AzerothCore. Presence model controls were not changed.')
    }
}

function Start-Server {
    Assert-Files @($WorldExe, $AuthExe, $MySqlExe, $MySqlAdminExe,
        $MySqlIni, $DatabaseCredentials, $AuthConfig, $WorldConfig)
    Assert-PortOwnership 3307 $MySqlExe
    Assert-PortOwnership 3724 $AuthExe
    Assert-PortOwnership 8085 $WorldExe
    Assert-PortOwnership 3443 $WorldExe

    if (-not (Get-OwnedProcess $MySqlExe)) {
        Write-Host 'Starting the database...'
        Start-IndependentProcess $MySqlExe "--defaults-file=`"$MySqlIni`" --no-monitor" $Root
        Start-Sleep -Seconds 1
    }
    Wait-Listener 'Database' $MySqlExe 3307 90
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    $databaseReady = $false
    do {
        & $MySqlAdminExe "--defaults-extra-file=$DatabaseCredentials" '--connect-timeout=3' 'ping' *> $null
        if ($LASTEXITCODE -eq 0) { $databaseReady = $true; break }
        Start-Sleep -Seconds 2
    } while ([DateTime]::UtcNow -lt $deadline)
    if (-not $databaseReady) { throw 'The database is listening but did not become ready. Check its error log.' }

    if (-not (Get-OwnedProcess $AuthExe)) {
        Write-Host 'Starting the login server...'
        Start-IndependentProcess $AuthExe "-c `"$AuthConfig`"" $ServerDirectory
        Start-Sleep -Seconds 1
    }
    Wait-Listener 'Login server' $AuthExe 3724 $StartupTimeoutSeconds

    if (-not (Get-OwnedProcess $WorldExe)) {
        Write-Host 'Starting the world server in the background...'
        Start-IndependentProcess $WorldExe "-c `"$WorldConfig`"" $ServerDirectory
    }
    Write-Host 'Waiting for the world server to accept players. First startup may take several minutes...'
    Wait-Listener 'World server' $WorldExe 8085 $StartupTimeoutSeconds
    Wait-Listener 'World administration' $WorldExe 3443 60
    Ensure-VesperOnline
    Write-Host "`nAzerothCore is ready. You can close this window and ChatGPT; the server runs independently."
    Write-Host 'Use the Stop AzerothCore desktop shortcut when you finish; it saves characters and closes the database safely.'
    Write-Host ''
    Show-Status
}

function Read-RaPrompt([System.Net.Sockets.NetworkStream]$Stream, [string[]]$Markers) {
    $buffer = New-Object byte[] 4096
    $received = New-Object Text.StringBuilder
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    do {
        $count = $Stream.Read($buffer, 0, $buffer.Length)
        if ($count -eq 0) { throw 'The world server closed its administration connection.' }
        [void]$received.Append([Text.Encoding]::ASCII.GetString($buffer, 0, $count))
        $value = $received.ToString()
        foreach ($marker in $Markers) {
            if ($value.Contains($marker)) { return $value }
        }
        if ($received.Length -gt 65536) { throw 'Unexpected world server administration response.' }
    } while ([DateTime]::UtcNow -lt $deadline)
    throw 'Timed out waiting for the world server administration prompt.'
}

function Write-RaLine([System.Net.Sockets.NetworkStream]$Stream, [string]$Line) {
    if ($Line.Contains("`r") -or $Line.Contains("`n")) { throw 'Invalid administration credential format.' }
    $bytes = [Text.Encoding]::ASCII.GetBytes($Line + "`r`n")
    $Stream.Write($bytes, 0, $bytes.Length)
    $Stream.Flush()
}

function Request-WorldShutdown {
    Assert-Files @($ServerCredentials)
    Assert-PortOwnership 3443 $WorldExe
    if (-not (Test-OwnedListener 3443 $WorldExe)) {
        throw 'World administration is not ready. The database was left running. Wait for startup to finish, then retry Stop AzerothCore. See logs\Server.log if startup failed.'
    }
    $credentials = Get-Content -LiteralPath $ServerCredentials -Raw | ConvertFrom-Json
    if (-not $credentials.Username -or -not $credentials.Password) {
        throw 'The local server administration credentials file is incomplete.'
    }
    $client = New-Object Net.Sockets.TcpClient
    try {
        $connection = $client.ConnectAsync('127.0.0.1', 3443)
        if (-not $connection.Wait(5000)) { throw 'Could not connect to the world administration port.' }
        [void]$connection.GetAwaiter().GetResult()
        $stream = $client.GetStream()
        $stream.ReadTimeout = 15000
        $stream.WriteTimeout = 5000
        [void](Read-RaPrompt $stream @('Username: '))
        Write-RaLine $stream ([string]$credentials.Username)
        [void](Read-RaPrompt $stream @('Password: '))
        Write-RaLine $stream ([string]$credentials.Password)
        $response = Read-RaPrompt $stream @('AC>', 'Authentication failed')
        if ($response.Contains('Authentication failed')) {
            throw 'The local server administration login failed. No process was stopped.'
        }
        Write-RaLine $stream 'server shutdown 1'
        # The world may close this socket while completing a successful shutdown.
        try { [void](Read-RaPrompt $stream @('AC>')) } catch {
            if (Get-OwnedProcess $WorldExe) { Start-Sleep -Seconds 2 }
        }
    } finally {
        $client.Dispose()
        $credentials = $null
    }
}

function Stop-Server {
    if (Get-OwnedProcess $WorldExe) {
        Write-Host 'Saving characters and shutting down the world server...'
        Request-WorldShutdown
        if (-not (Wait-ProcessExit $WorldExe 180)) {
            throw 'The world server is still saving or shutting down. The login server and database were left running. Check logs\Server.log, then retry Stop AzerothCore.'
        }
    }
    $authProcess = Get-OwnedProcess $AuthExe
    if ($authProcess) {
        Write-Host 'Stopping the login server...'
        # Revalidate the executable path immediately before stopping this exact PID.
        $confirmed = Get-OwnedProcess $AuthExe
        if ($confirmed -and $confirmed.ProcessId -eq $authProcess.ProcessId) {
            Stop-Process -Id $confirmed.ProcessId -ErrorAction Stop
        }
        if (-not (Wait-ProcessExit $AuthExe 15)) {
            throw 'The login server did not stop. The database was left running.'
        }
    }
    if (Get-OwnedProcess $MySqlExe) {
        Assert-Files @($MySqlAdminExe, $DatabaseCredentials)
        Assert-PortOwnership 3307 $MySqlExe
        if (-not (Test-OwnedListener 3307 $MySqlExe)) {
            throw 'The database is running but its local port is not ready. Check its error log; no forced stop was attempted.'
        }
        Write-Host 'Shutting down the database...'
        & $MySqlAdminExe "--defaults-extra-file=$DatabaseCredentials" '--connect-timeout=5' '--shutdown-timeout=90' 'shutdown' *> $null
        if ($LASTEXITCODE -ne 0) { throw 'The database shutdown request failed. Check its error log; no forced stop was attempted.' }
        if (-not (Wait-ProcessExit $MySqlExe 90)) {
            throw 'The database is still finishing shutdown. Check its error log; no forced stop was attempted.'
        }
    }
    Write-Host "`nAzerothCore has stopped."
    Show-Status
}

$mutex = $null
$lockHeld = $false
try {
    if ($Action -ne 'Status') {
        $hashAlgorithm = [Security.Cryptography.SHA256]::Create()
        try {
            $digest = $hashAlgorithm.ComputeHash([Text.Encoding]::UTF8.GetBytes($Root.ToLowerInvariant()))
        } finally { $hashAlgorithm.Dispose() }
        $lockName = 'Local\AzerothCore-' + ([BitConverter]::ToString($digest) -replace '-', '')
        $mutex = New-Object Threading.Mutex($false, $lockName)
        try { $lockHeld = $mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $lockHeld = $true }
        if (-not $lockHeld) { throw 'Another start or stop operation is in progress. Wait for it to finish.' }
    }
    switch ($Action) {
        'Start' { Start-Server }
        'WorldConsole' { Start-Server }
        'Stop' { Stop-Server }
        'Status' { Show-Status }
    }
} catch {
    Write-Host ("`nERROR: " + $_.Exception.Message) -ForegroundColor Red
    exit 1
} finally {
    if ($lockHeld) { $mutex.ReleaseMutex() }
    if ($mutex) { $mutex.Dispose() }
}
