#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateRange(10, 3600)]
    [int]$UpdateStartupTimeoutSeconds = 900
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Import the same exact-path ownership checks, graceful shutdown, and detached
# WMI launcher used by the desktop shortcuts. Status is read-only.
. (Join-Path $PSScriptRoot 'AzerothCore-Server.ps1') -Action Status

$updateRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot)).TrimEnd('\')
$updateBuild = Join-Path $updateRoot 'build\bin\RelWithDebInfo'
$updateDatabase = Join-Path $updateRoot 'database'
$updateConfigs = Join-Path $ServerDirectory 'configs'
$updatePlayerbotsConfig = Join-Path $updateConfigs 'modules\playerbots.conf'
$updatePresenceConfig = Join-Path $updateConfigs 'modules\presence_bridge.conf'
$updateIntegration = Join-Path $updateRoot 'update-integration'
$updatePins = Join-Path $updateIntegration 'source-pins.json'
$updateApprovedCoreUpstream = '93333d6a9eb00fdf0179adde30da3c17618207d6'
$updateApprovedCoreMerge = '25a0dd69555eb5d0f0e671c251979eae7f25d414'
$updateApprovedBotsUpstream = '05a1f6fceb8a32aa879b13f5f48934c6e46a774c'
$updateBinaryNames = @('authserver.exe', 'authserver.pdb', 'worldserver.exe', 'worldserver.pdb')
$updateMutex = $null
$updateLockHeld = $false
$updateBackup = $null
$updateStatePath = $null
$updateStage = 'preflight'
$updateState = [ordered]@{
    protocol = 1
    started_at = [DateTime]::UtcNow.ToString('o')
    status = 'preparing'
    stage = $updateStage
    root = $updateRoot
    was_running = $null
    backup_paths = $null
    source_pins = $null
    build_files = @()
    old_binaries = @()
    private_files = @()
    protection_files = @()
    database_backup = $null
    config_backup = $null
    config_changes = @()
    installed_files = @()
    offline_backup_verified = $false
    startup_attempted = $false
    migrations_may_have_run = $false
    automatic_rollback = $false
    rollback_requirement = 'Restore the offline database, binaries, and configs together; binary-only rollback does not undo startup data migrations.'
}

function Assert-UpdateWorkspacePath([string]$Path) {
    $resolved = [IO.Path]::GetFullPath($Path)
    if (-not ($resolved.Equals($updateRoot, [StringComparison]::OrdinalIgnoreCase) -or
        $resolved.StartsWith($updateRoot + '\', [StringComparison]::OrdinalIgnoreCase))) {
        throw 'A required update path is outside this installation workspace.'
    }
    # Reject redirects in any existing component, including the workspace root.
    $cursor = $resolved
    while ($cursor.Length -ge $updateRoot.Length) {
        if (Test-Path -LiteralPath $cursor) {
            $entry = Get-Item -LiteralPath $cursor -Force
            if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Update paths must not contain a junction or symbolic link: $cursor"
            }
        }
        if ($cursor.Equals($updateRoot, [StringComparison]::OrdinalIgnoreCase)) { break }
        $cursor = Split-Path -Parent $cursor
    }
    return $resolved
}

function New-UpdateDirectory([string]$Path) {
    [void](Assert-UpdateWorkspacePath $Path)
    [void][IO.Directory]::CreateDirectory($Path)
}

function Set-UpdatePrivateDirectory([string]$Path) {
    # Backups contain local database and administration credentials. Disable
    # inherited access before writing any such files, retaining only this user
    # and SYSTEM. Descendants inherit these private permissions.
    $ownerSid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $systemSid = New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetOwner($ownerSid)
    $acl.SetAccessRuleProtection($true, $false)
    $inheritance = [Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
    foreach ($sid in @($ownerSid, $systemSid)) {
        $rule = New-Object Security.AccessControl.FileSystemAccessRule(
            $sid, [Security.AccessControl.FileSystemRights]::FullControl,
            $inheritance, [Security.AccessControl.PropagationFlags]::None,
            [Security.AccessControl.AccessControlType]::Allow)
        [void]$acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
    $confirmed = Get-Acl -LiteralPath $Path
    if (-not $confirmed.AreAccessRulesProtected) {
        throw 'Could not protect the private update backup directory.'
    }
}

function Write-UpdateState {
    if (-not $updateStatePath) { return }
    $updateState.stage = $updateStage
    $updateState['updated_at'] = [DateTime]::UtcNow.ToString('o')
    $json = $updateState | ConvertTo-Json -Depth 12
    $temporary = Join-Path $updateBackup ('.state-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    try {
        [IO.File]::WriteAllText($temporary, $json + "`r`n", (New-Object Text.UTF8Encoding($false)))
        if (Test-Path -LiteralPath $updateStatePath -PathType Leaf) {
            [IO.File]::Replace($temporary, $updateStatePath, [System.Management.Automation.Language.NullString]::Value)
        } else {
            [IO.File]::Move($temporary, $updateStatePath)
        }
    } finally {
        if (Test-Path -LiteralPath $temporary -PathType Leaf) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

function Set-UpdateStage([string]$Stage) {
    $script:updateStage = $Stage
    Write-UpdateState
    Write-Host "Update stage: $Stage"
}

function Get-UpdateFileRecord([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.PSIsContainer) { throw "A required file is invalid: $Path" }
    [pscustomobject]@{
        path = $item.FullName
        bytes = [long]$item.Length
        sha256 = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
        last_write_utc = $item.LastWriteTimeUtc.ToString('o')
    }
}

function Get-UpdateGitHead([string]$Repository) {
    [void](Assert-UpdateWorkspacePath $Repository)
    $git = (Get-Command -Name git.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $lines = @(& $git '--no-optional-locks' '-C' $Repository 'rev-parse' '--verify' 'HEAD' 2>$null)
    if ($LASTEXITCODE -ne 0 -or $lines.Count -ne 1 -or $lines[0] -notmatch '^[0-9a-fA-F]{40}$') {
        throw "Could not validate the source repository HEAD: $Repository"
    }
    & $git '--no-optional-locks' '-C' $Repository 'diff' '--quiet' '--exit-code' '--ignore-submodules=untracked' '--' 2>$null
    if ($LASTEXITCODE -ne 0) { throw "The source repository has tracked worktree changes or could not be checked: $Repository" }
    & $git '--no-optional-locks' '-C' $Repository 'diff' '--cached' '--quiet' '--exit-code' '--ignore-submodules=untracked' '--' 2>$null
    if ($LASTEXITCODE -ne 0) { throw "The source repository has staged changes or could not be checked: $Repository" }
    return ([string]$lines[0]).ToLowerInvariant()
}

function Assert-UpdateSourcePins {
    $pins = Get-Content -LiteralPath $updatePins -Raw | ConvertFrom-Json
    if ($pins.core_upstream -ne $updateApprovedCoreUpstream -or
        $pins.core_custom_merge -ne $updateApprovedCoreMerge -or
        $pins.bots_upstream -ne $updateApprovedBotsUpstream) {
        throw 'The source-pin record does not match this explicitly approved core and Playerbots update.'
    }
    $coreHead = Get-UpdateGitHead (Join-Path $updateRoot 'source')
    $botsHead = Get-UpdateGitHead (Join-Path $updateRoot 'source\modules\mod-playerbots')
    if ($coreHead -ne $pins.core_custom_merge -or $botsHead -ne $pins.bots_upstream) {
        throw 'The core or Playerbots repository HEAD differs from its approved source pin.'
    }
    [pscustomobject]@{
        core_upstream = $updateApprovedCoreUpstream
        core_custom_merge = $updateApprovedCoreMerge
        bots_upstream = $updateApprovedBotsUpstream
        verified_core_head = $coreHead
        verified_bots_head = $botsHead
        record_sha256 = (Get-FileHash -LiteralPath $updatePins -Algorithm SHA256).Hash
    }
}

function Get-UpdateTreeInventory([string]$Directory, [switch]$HashFiles) {
    $base = (Assert-UpdateWorkspacePath $Directory).TrimEnd('\')
    if (-not (Test-Path -LiteralPath $base -PathType Container)) {
        throw "Required directory is missing: $base"
    }
    foreach ($entry in @(Get-ChildItem -LiteralPath $base -Force -Recurse -ErrorAction Stop)) {
        if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "The backup source contains a junction or symbolic link: $($entry.FullName)"
        }
        if (-not $entry.PSIsContainer) {
            $record = [ordered]@{
                relative_path = $entry.FullName.Substring($base.Length + 1)
                bytes = [long]$entry.Length
            }
            if ($HashFiles) { $record['sha256'] = (Get-FileHash -LiteralPath $entry.FullName -Algorithm SHA256).Hash }
            [pscustomobject]$record
        }
    }
}

function Assert-UpdateServicesOffline {
    foreach ($exe in @($WorldExe, $AuthExe, $MySqlExe)) {
        if (Get-OwnedProcess $exe) { throw 'An installation process is still running; offline copying is prohibited.' }
    }
    Assert-PortOwnership 3307 $MySqlExe
    Assert-PortOwnership 3724 $AuthExe
    Assert-PortOwnership 8085 $WorldExe
    Assert-PortOwnership 3443 $WorldExe
}

function Copy-UpdateTree([string]$Source, [string]$Destination, [string]$Label, [switch]$HashFiles) {
    Assert-UpdateServicesOffline
    $before = @(Get-UpdateTreeInventory $Source -HashFiles:$HashFiles | Sort-Object relative_path)
    if ($before.Count -eq 0) { throw "$Label source directory contains no files." }
    New-UpdateDirectory $Destination
    $log = Join-Path $updateBackup ($Label + '.robocopy.log')
    $robocopy = Join-Path $env:SystemRoot 'System32\robocopy.exe'
    & $robocopy $Source $Destination '/E' '/COPY:DAT' '/DCOPY:DAT' '/R:2' '/W:1' '/XJ' `
        '/NP' '/NFL' '/NDL' '/NJH' '/NJS' "/LOG:$log" | Out-Null
    $copyExitCode = $LASTEXITCODE
    if ($copyExitCode -ge 8) { throw "$Label copy failed (robocopy result $copyExitCode); see its private backup log." }
    Assert-UpdateServicesOffline
    $after = @(Get-UpdateTreeInventory $Source -HashFiles:$HashFiles | Sort-Object relative_path)
    $copied = @(Get-UpdateTreeInventory $Destination -HashFiles:$HashFiles | Sort-Object relative_path)
    if ($before.Count -ne $after.Count -or $after.Count -ne $copied.Count) {
        throw "$Label file counts changed or the backup is incomplete."
    }
    $sourceBytes = [long]0
    $copiedBytes = [long]0
    for ($i = 0; $i -lt $before.Count; $i++) {
        if ($before[$i].relative_path -cne $after[$i].relative_path -or
            $after[$i].relative_path -cne $copied[$i].relative_path -or
            $before[$i].bytes -ne $after[$i].bytes -or $after[$i].bytes -ne $copied[$i].bytes) {
            throw "$Label relative paths or file sizes do not match the offline source."
        }
        if ($HashFiles -and ($before[$i].sha256 -ne $after[$i].sha256 -or $after[$i].sha256 -ne $copied[$i].sha256)) {
            throw "$Label file hashes do not match the offline source."
        }
        $sourceBytes += $after[$i].bytes
        $copiedBytes += $copied[$i].bytes
    }
    if ($sourceBytes -ne $copiedBytes) { throw "$Label byte totals do not match." }
    $inventoryPath = Join-Path $updateBackup ($Label + '.inventory.json')
    [IO.File]::WriteAllText($inventoryPath, (ConvertTo-Json -InputObject $copied -Depth 4), (New-Object Text.UTF8Encoding($false)))
    [pscustomobject]@{
        source = $Source
        backup = $Destination
        files = $copied.Count
        source_bytes = $sourceBytes
        copied_bytes = $copiedBytes
        inventory = $inventoryPath
        inventory_sha256 = (Get-FileHash -LiteralPath $inventoryPath -Algorithm SHA256).Hash
        robocopy_exit_code = $copyExitCode
        verified = $true
    }
}

function Copy-UpdateVerifiedFile([string]$Source, [string]$Destination) {
    [void](Assert-UpdateWorkspacePath $Source)
    [void](Assert-UpdateWorkspacePath $Destination)
    $sourceRecord = Get-UpdateFileRecord $Source
    New-UpdateDirectory (Split-Path -Parent $Destination)
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
    $copied = Get-UpdateFileRecord $Destination
    $sourceAfter = Get-UpdateFileRecord $Source
    if ($sourceRecord.bytes -ne $copied.bytes -or $sourceRecord.sha256 -ne $copied.sha256 -or
        $sourceAfter.sha256 -ne $sourceRecord.sha256) {
        throw "File copy verification failed: $([IO.Path]::GetFileName($Source))"
    }
    [pscustomobject]@{ source = $Source; backup = $Destination; bytes = $copied.bytes; sha256 = $copied.sha256 }
}

function Get-UpdateEncodedText([string]$Path) {
    $bytes = [IO.File]::ReadAllBytes($Path)
    $bomLength = 0
    $encoding = New-Object Text.UTF8Encoding($false, $true)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 239 -and $bytes[1] -eq 187 -and $bytes[2] -eq 191) {
        $encoding = New-Object Text.UTF8Encoding($true, $true)
        $bomLength = 3
    } elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 255 -and $bytes[1] -eq 254) {
        $encoding = New-Object Text.UnicodeEncoding($false, $true, $true)
        $bomLength = 2
    } elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 254 -and $bytes[1] -eq 255) {
        $encoding = New-Object Text.UnicodeEncoding($true, $true, $true)
        $bomLength = 2
    }
    [pscustomobject]@{ text = $encoding.GetString($bytes, $bomLength, $bytes.Length - $bomLength); encoding = $encoding }
}

function Get-UpdateConfigPlan {
    $world = Get-UpdateEncodedText $WorldConfig
    $keys = [regex]::Matches($world.text, '(?m)^[ \t]*DisconnectToleranceInterval[ \t]*=[^\r\n]*')
    $zero = [regex]::Matches($world.text, '(?m)^(?<prefix>[ \t]*DisconnectToleranceInterval[ \t]*=[ \t]*)0(?<suffix>[ \t]*(?:#[^\r\n]*)?)(?<cr>\r?)$')
    if ($keys.Count -ne 1 -or $zero.Count -ne 1) {
        throw 'Expected exactly one active DisconnectToleranceInterval key with the existing value 0; no config was changed.'
    }
    $match = $zero[0]
    $worldNew = $world.text.Substring(0, $match.Index) + $match.Groups['prefix'].Value + '60' +
        $match.Groups['suffix'].Value + $match.Groups['cr'].Value + $world.text.Substring($match.Index + $match.Length)
    $bots = Get-UpdateEncodedText $updatePlayerbotsConfig
    $botsNew = $bots.text
    $newline = "`n"
    if ($botsNew.Contains("`r`n")) { $newline = "`r`n" }
    $changes = @('DisconnectToleranceInterval: 0 -> 60')
    foreach ($setting in @(
        @{ key = 'Playerbots.AutoPickTalentsForPlayerControlledBots'; value = '0' },
        @{ key = 'Playerbots.RpgTargetSearchDistance'; value = '150.0' },
        @{ key = 'Playerbots.CollectDetailedQuestStats'; value = '0' },
        @{ key = 'Playerbots.ProbTeleToQuestGivers'; value = '0' }
    )) {
        $pattern = '(?m)^[ \t]*' + [regex]::Escape($setting.key) + '[ \t]*='
        $existing = [regex]::Matches($bots.text, $pattern)
        if ($existing.Count -gt 1) { throw "Duplicate active Playerbots configuration key: $($setting.key)" }
        if ($existing.Count -eq 0) {
            if ($botsNew.Length -gt 0 -and -not $botsNew.EndsWith("`n")) { $botsNew += $newline }
            $botsNew += $setting.key + ' = ' + $setting.value + $newline
            $changes += $setting.key + ': added default ' + $setting.value
        }
    }
    [pscustomobject]@{ world = $world; world_new = $worldNew; bots = $bots; bots_new = $botsNew; changes = $changes }
}

function Set-UpdateTextFile([string]$Path, [string]$Text, [Text.Encoding]$Encoding) {
    $temporary = Join-Path (Split-Path -Parent $Path) ('.update-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    try {
        [IO.File]::WriteAllText($temporary, $Text, $Encoding)
        [IO.File]::Replace($temporary, $Path, [System.Management.Automation.Language.NullString]::Value)
        if ((Get-UpdateEncodedText $Path).text -cne $Text) { throw 'Saved configuration verification failed.' }
    } finally {
        if (Test-Path -LiteralPath $temporary -PathType Leaf) { Remove-Item -LiteralPath $temporary -Force }
    }
}

function Wait-UpdateDatabaseReady {
    Wait-Listener 'Database' $MySqlExe 3307 90
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    do {
        & $MySqlAdminExe "--defaults-extra-file=$DatabaseCredentials" '--connect-timeout=3' 'ping' *> $null
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Seconds 2
    } while ([DateTime]::UtcNow -lt $deadline)
    throw 'The restarted database did not become ready.'
}

try {
    # Hold the desktop launcher's lock throughout the offline backup and update.
    # A double-click of Start cannot bring MySQL up in the middle of the copy.
    $hashAlgorithm = [Security.Cryptography.SHA256]::Create()
    try { $digest = $hashAlgorithm.ComputeHash([Text.Encoding]::UTF8.GetBytes($Root.ToLowerInvariant())) }
    finally { $hashAlgorithm.Dispose() }
    $lockName = 'Local\AzerothCore-' + ([BitConverter]::ToString($digest) -replace '-', '')
    $updateMutex = New-Object Threading.Mutex($false, $lockName)
    try { $updateLockHeld = $updateMutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $updateLockHeld = $true }
    if (-not $updateLockHeld) { throw 'Another server start, stop, or update operation is in progress.' }

    foreach ($path in @($updateBuild, $updateDatabase, $updateConfigs, $updateIntegration)) {
        [void](Assert-UpdateWorkspacePath $path)
    }
    Assert-Files @($WorldExe, $AuthExe, (Join-Path $ServerDirectory 'authserver.pdb'),
        (Join-Path $ServerDirectory 'worldserver.pdb'), $MySqlExe, $MySqlAdminExe,
        $MySqlIni, $DatabaseCredentials, $ServerCredentials, $AuthConfig, $WorldConfig,
        $updatePlayerbotsConfig, $updatePresenceConfig, (Join-Path $updateRoot 'installation.json'), $updatePins)
    $updateState.source_pins = Assert-UpdateSourcePins
    # The approved pin record predates the coordinated build. Reject a stale
    # auth/world executable or PDB left behind by an unfinished or failed build.
    $pinsTime = (Get-Item -LiteralPath $updatePins).LastWriteTimeUtc
    foreach ($name in $updateBinaryNames) {
        $built = Join-Path $updateBuild $name
        Assert-Files @($built)
        [void](Assert-UpdateWorkspacePath $built)
        $record = Get-UpdateFileRecord $built
        if ($record.bytes -le 0) { throw "The built $name is empty." }
        if ((Get-Item -LiteralPath $built).LastWriteTimeUtc -lt $pinsTime) {
            throw "The built $name predates the approved source pins. Finish the coordinated build before installing."
        }
        $updateState.build_files += $record
    }
    # Confirm that mysqld will actually use the directory we are backing up.
    $inServerSection = $false
    $configuredDataDirectories = @()
    foreach ($line in [IO.File]::ReadAllLines($MySqlIni)) {
        if ($line -match '^\s*\[([^\]]+)\]\s*$') { $inServerSection = $Matches[1] -eq 'mysqld'; continue }
        if ($inServerSection -and $line -match '^\s*datadir\s*=\s*(.*?)\s*$') {
            $configuredDataDirectories += $Matches[1].Trim('"', "'")
        }
    }
    if ($configuredDataDirectories.Count -ne 1 -or
        -not [IO.Path]::IsPathRooted($configuredDataDirectories[0]) -or
        -not [IO.Path]::GetFullPath($configuredDataDirectories[0]).TrimEnd('\').Equals($updateDatabase, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'mysql.ini must contain exactly one mysqld datadir pointing to this workspace database directory.'
    }
    [void](Assert-UpdateWorkspacePath $updateDatabase)
    foreach ($schema in @('acore_auth', 'acore_characters', 'acore_world', 'acore_playerbots')) {
        $schemaDirectory = Join-Path $updateDatabase $schema
        [void](Assert-UpdateWorkspacePath $schemaDirectory)
        if (-not (Test-Path -LiteralPath $schemaDirectory -PathType Container)) {
            throw "Required database schema directory is missing: $schema"
        }
    }
    $configPlan = Get-UpdateConfigPlan
    $protectionPaths = @((Join-Path $ServerDirectory 'presence-bridge-protection.jsonl'))
    $presenceText = (Get-UpdateEncodedText $updatePresenceConfig).text
    $protectionKeys = [regex]::Matches($presenceText, '(?m)^[ \t]*PresenceBridge\.ProtectionFile[ \t]*=[ \t]*(?<value>[^\r\n]*)')
    if ($protectionKeys.Count -gt 1) { throw 'Duplicate active PresenceBridge.ProtectionFile configuration keys.' }
    if ($protectionKeys.Count -eq 1) {
        $protectionValue = $protectionKeys[0].Groups['value'].Value
        $parsedProtection = [regex]::Match($protectionValue, '^[ \t]*(?:"(?<quoted>[^"]*)"|(?<unquoted>[^#]*?))[ \t]*(?:#.*)?$')
        if (-not $parsedProtection.Success) { throw 'Could not parse PresenceBridge.ProtectionFile safely.' }
        $configuredProtection = $parsedProtection.Groups['quoted'].Value
        if (-not $parsedProtection.Groups['quoted'].Success) { $configuredProtection = $parsedProtection.Groups['unquoted'].Value.Trim() }
        if (-not [string]::IsNullOrWhiteSpace($configuredProtection)) {
            if (-not [IO.Path]::IsPathRooted($configuredProtection)) { $configuredProtection = Join-Path $ServerDirectory $configuredProtection }
            $protectionPaths += Assert-UpdateWorkspacePath $configuredProtection
        }
    }
    foreach ($portAndExe in @(@{port=3307; exe=$MySqlExe}, @{port=3724; exe=$AuthExe}, @{port=8085; exe=$WorldExe}, @{port=3443; exe=$WorldExe})) {
        Assert-PortOwnership $portAndExe.port $portAndExe.exe
    }
    $updateState.was_running = [ordered]@{
        world = [bool](Get-OwnedProcess $WorldExe)
        auth = [bool](Get-OwnedProcess $AuthExe)
        mysql = [bool](Get-OwnedProcess $MySqlExe)
    }
    if (($updateState.was_running.world -or $updateState.was_running.auth) -and -not $updateState.was_running.mysql) {
        throw 'The initial server process state is inconsistent: auth/world is running without its database.'
    }
    $updateBackup = Join-Path $updateIntegration ('backups\' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8))
    [void](Assert-UpdateWorkspacePath $updateBackup)
    [void](New-Item -ItemType Directory -Path $updateBackup -ErrorAction Stop)
    Set-UpdatePrivateDirectory $updateBackup
    $updateStatePath = Join-Path $updateBackup 'update-state.json'
    $updateState.backup_paths = [ordered]@{
        root = $updateBackup
        database = Join-Path $updateBackup 'database'
        configs = Join-Path $updateBackup 'configs'
        binaries = Join-Path $updateBackup 'binaries'
        private_files = Join-Path $updateBackup 'private'
        protection = Join-Path $updateBackup 'protection'
        candidates = Join-Path $updateBackup 'candidates'
    }
    $updateState.status = 'in_progress'
    Write-UpdateState

    Set-UpdateStage 'graceful_shutdown'
    Stop-Server
    Assert-UpdateServicesOffline

    Set-UpdateStage 'offline_backup_capacity_check'
    $requiredBytes = [long]0
    foreach ($directory in @($updateDatabase, $updateConfigs)) {
        foreach ($file in @(Get-UpdateTreeInventory $directory)) { $requiredBytes += $file.bytes }
    }
    foreach ($name in $updateBinaryNames) {
        $requiredBytes += (Get-Item -LiteralPath (Join-Path $ServerDirectory $name)).Length
        $requiredBytes += (Get-Item -LiteralPath (Join-Path $updateBuild $name)).Length
    }
    # Allow room for private files, state/log writes, and filesystem growth.
    $reserveBytes = [long][Math]::Max(1GB, [Math]::Ceiling($requiredBytes * 0.05))
    $backupDrive = New-Object IO.DriveInfo([IO.Path]::GetPathRoot($updateBackup))
    $updateState['backup_capacity'] = [ordered]@{
        required_bytes = $requiredBytes
        reserve_bytes = $reserveBytes
        available_bytes = $backupDrive.AvailableFreeSpace
    }
    Write-UpdateState
    if ($backupDrive.AvailableFreeSpace -lt ($requiredBytes + $reserveBytes)) {
        throw 'Insufficient free space for the complete offline backup and staged binaries with a safety reserve.'
    }

    Set-UpdateStage 'offline_database_backup'
    $updateState.database_backup = Copy-UpdateTree $updateDatabase $updateState.backup_paths.database 'database' -HashFiles
    Write-UpdateState
    Set-UpdateStage 'offline_configuration_backup'
    $updateState.config_backup = Copy-UpdateTree $updateConfigs $updateState.backup_paths.configs 'configs' -HashFiles
    foreach ($name in $updateBinaryNames) {
        $updateState.old_binaries += Copy-UpdateVerifiedFile (Join-Path $ServerDirectory $name) (Join-Path $updateState.backup_paths.binaries $name)
    }
    foreach ($name in @('installation.json', 'mysql.ini', 'database-admin.cnf', 'server-admin.json', 'agent-login.json', 'local-settings.json', 'Login Details.txt')) {
        $path = Join-Path $updateRoot $name
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            $updateState.private_files += Copy-UpdateVerifiedFile $path (Join-Path $updateState.backup_paths.private_files $name)
        }
    }
    $updateState.private_files += Copy-UpdateVerifiedFile $updatePins (Join-Path $updateState.backup_paths.private_files 'source-pins.json')
    foreach ($path in @($protectionPaths | Sort-Object -Unique)) {
        [void](Assert-UpdateWorkspacePath $path)
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            $relative = $path.Substring($updateRoot.Length + 1)
            $updateState.protection_files += Copy-UpdateVerifiedFile $path (Join-Path $updateState.backup_paths.protection $relative)
        }
    }
    Assert-UpdateServicesOffline
    $updateState.offline_backup_verified = $true
    Write-UpdateState

    Set-UpdateStage 'stage_new_binaries'
    foreach ($record in $updateState.build_files) {
        $name = [IO.Path]::GetFileName($record.path)
        $candidate = Copy-UpdateVerifiedFile $record.path (Join-Path $updateState.backup_paths.candidates $name)
        if ($candidate.sha256 -ne $record.sha256 -or $candidate.bytes -ne $record.bytes) {
            throw "The build output changed during the update: $name"
        }
    }

    Set-UpdateStage 'update_explicit_configuration'
    Assert-UpdateServicesOffline
    # Detect edits outside the launcher lock instead of changing a file whose
    # newest contents are absent from the rollback set.
    foreach ($relative in @('worldserver.conf', 'modules\playerbots.conf')) {
        if ((Get-FileHash -LiteralPath (Join-Path $updateConfigs $relative) -Algorithm SHA256).Hash -ne
            (Get-FileHash -LiteralPath (Join-Path $updateState.backup_paths.configs $relative) -Algorithm SHA256).Hash) {
            throw 'A live configuration changed after its offline backup. Nothing further was installed.'
        }
    }
    $configPlan = Get-UpdateConfigPlan
    Set-UpdateTextFile $WorldConfig $configPlan.world_new $configPlan.world.encoding
    if ($configPlan.bots_new -cne $configPlan.bots.text) {
        Set-UpdateTextFile $updatePlayerbotsConfig $configPlan.bots_new $configPlan.bots.encoding
    }
    $updateState.config_changes = $configPlan.changes
    Write-UpdateState

    Set-UpdateStage 'install_auth_and_world_binaries'
    foreach ($name in $updateBinaryNames) {
        Assert-UpdateServicesOffline
        $candidatePath = Join-Path $updateState.backup_paths.candidates $name
        $installed = Copy-UpdateVerifiedFile $candidatePath (Join-Path $ServerDirectory $name)
        $expected = @($updateState.build_files | Where-Object { [IO.Path]::GetFileName($_.path) -eq $name })[0]
        if ($installed.sha256 -ne $expected.sha256) { throw "Installed binary hash does not match the approved candidate: $name" }
        $updateState.installed_files += [pscustomobject]@{ path = $installed.backup; bytes = $installed.bytes; sha256 = $installed.sha256 }
        Write-UpdateState
    }

    Set-UpdateStage 'restore_prior_running_services'
    Assert-UpdateServicesOffline
    # Startup migration files are loaded from these repositories. Recheck after
    # the backup/copy interval before allowing either new server to start.
    [void](Assert-UpdateSourcePins)
    if ($updateState.was_running.world -and $updateState.was_running.auth) {
        $updateState.startup_attempted = $true
        $updateState.migrations_may_have_run = $true
        Write-UpdateState
        $StartupTimeoutSeconds = $UpdateStartupTimeoutSeconds
        Start-Server
    } else {
        if ($updateState.was_running.mysql) {
            $updateState.startup_attempted = $true
            Write-UpdateState
            Start-IndependentProcess $MySqlExe "--defaults-file=`"$MySqlIni`" --no-monitor" $Root
            Wait-UpdateDatabaseReady
        }
        if ($updateState.was_running.auth) {
            $updateState.migrations_may_have_run = $true
            Write-UpdateState
            Start-IndependentProcess $AuthExe "-c `"$AuthConfig`"" $ServerDirectory
            Wait-Listener 'Login server' $AuthExe 3724 $UpdateStartupTimeoutSeconds
        }
        if ($updateState.was_running.world) {
            # Preserve the unusual but valid prior world-without-auth state.
            $updateState.migrations_may_have_run = $true
            Write-UpdateState
            Start-IndependentProcess $WorldExe "-c `"$WorldConfig`"" $ServerDirectory
            Wait-Listener 'World server' $WorldExe 8085 $UpdateStartupTimeoutSeconds
            Wait-Listener 'World administration' $WorldExe 3443 60
        }
        Show-Status
    }
    $updateState.status = 'complete'
    $updateState['completed_at'] = [DateTime]::UtcNow.ToString('o')
    Set-UpdateStage 'complete'
    Write-Host "`nUpstream binaries installed and verified. Offline backup: $updateBackup"
    Write-Host 'Presence settings, providers, models, and controller state were not changed.'
    Write-Host 'Rollback requires the matching offline database, binaries, and configs together.'
} catch {
    $failedStage = $updateStage
    $updateState.status = 'failed'
    $updateState['failure_stage'] = $failedStage
    $updateState['failed_at'] = [DateTime]::UtcNow.ToString('o')
    # Exception messages/IDs can quote malformed credential file contents.
    # Record only structured diagnostic fields, never those raw strings.
    $updateState['failure_diagnostic'] = [ordered]@{
        exception_type = $_.Exception.GetType().FullName
        category = [string]$_.CategoryInfo.Category
        script_line = $_.InvocationInfo.ScriptLineNumber
    }
    try { Write-UpdateState } catch { }
    $backupDescription = 'No backup directory was created.'
    if ($updateBackup) { $backupDescription = "Evidence and any completed backups: $updateBackup" }
    Write-Host "`nUpdate failed at stage: $failedStage" -ForegroundColor Red
    Write-Host $backupDescription
    Write-Host 'No automatic database or binary rollback was attempted. Leave the saved evidence intact.'
    throw "Upstream update failed during '$failedStage'. $backupDescription Inspect the private state/logs before restarting or restoring the matching database, binaries, and configs."
} finally {
    if ($updateLockHeld) { $updateMutex.ReleaseMutex() }
    if ($updateMutex) { $updateMutex.Dispose() }
}
