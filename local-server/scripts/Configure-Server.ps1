$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$settings = Get-Content -LiteralPath (Join-Path $root 'local-settings.json') -Raw | ConvertFrom-Json
$configs = Join-Path $root 'server\configs'
New-Item -ItemType Directory -Path (Join-Path $configs 'modules'), (Join-Path $root 'server\temp') -Force | Out-Null

function Write-Configuration([string]$Source, [string]$Destination, [hashtable]$Values) {
    $content = Get-Content -LiteralPath (Join-Path $root $Source) -Raw
    foreach ($key in $Values.Keys) {
        $pattern = '(?m)^' + [regex]::Escape($key) + '\s*=.*$'
        if (-not [regex]::IsMatch($content, $pattern)) { throw "Configuration key missing: $key" }
        $replacement = $key + ' = ' + $Values[$key]
        $content = [regex]::Replace($content, $pattern, [System.Text.RegularExpressions.MatchEvaluator]{ param($match) $replacement }.GetNewClosure())
    }
    [IO.File]::WriteAllText((Join-Path $configs $Destination), $content.Replace("`r`n", "`n"), [Text.UTF8Encoding]::new($false))
}

$common = @{
    BindIP = '"127.0.0.1"'
    LoginDatabaseInfo = '"127.0.0.1;3307;acore;' + $settings.DatabasePassword + ';acore_auth"'
    SourceDirectory = '"C:/Games/AzerothCore/source"'
    MySQLExecutable = '"C:/Games/AzerothCore/tools/mysql-8.4.13-winx64/bin/mysql.exe"'
    LogsDir = '"C:/Games/AzerothCore/logs"'
    TempDir = '"C:/Games/AzerothCore/server/temp"'
}
Write-Configuration 'source\src\server\apps\authserver\authserver.conf.dist' 'authserver.conf' $common
$world = $common.Clone()
$world.WorldDatabaseInfo = '"127.0.0.1;3307;acore;' + $settings.DatabasePassword + ';acore_world"'
$world.CharacterDatabaseInfo = '"127.0.0.1;3307;acore;' + $settings.DatabasePassword + ';acore_characters"'
$world.DataDir = '"C:/Games/AzerothCore/server/data"'
$world['Ra.Enable'] = '1'
$world['Ra.IP'] = '"127.0.0.1"'
$world['Ra.Port'] = '3443'
$world['MapUpdate.Threads'] = '4'
$world['GM.LoginState'] = '0'
$world['GameType'] = '0'
Write-Configuration 'source\src\server\apps\worldserver\worldserver.conf.dist' 'worldserver.conf' $world
Write-Configuration 'source\modules\mod-playerbots\conf\playerbots.conf.dist' 'modules\playerbots.conf' @{
    PlayerbotsDatabaseInfo = '"127.0.0.1;3307;acore;' + $settings.DatabasePassword + ';acore_playerbots"'
    'Playerbots.MinRandomBots' = '50'
    'Playerbots.MaxRandomBots' = '50'
    'Playerbots.AddClassAccountPoolSize' = '5'
    'Playerbots.DisabledWithoutRealPlayer' = '1'
    'Playerbots.AllowAccountBots' = '1'
    'Playerbots.BotAutologin' = '0'
    'Playerbots.GroupInvitationPermission' = '2'
    'Playerbots.CommandServerPort' = '0'
    'Playerbots.RandomBotJoinBG' = '0'
    'Playerbots.RandomBotAutoJoinBG' = '0'
    'Playerbots.RandomBotArenaTeam2v2Count' = '0'
    'Playerbots.RandomBotArenaTeam3v3Count' = '0'
    'Playerbots.RandomBotArenaTeam5v5Count' = '0'
    'Playerbots.RpgStatusProbWeight.OutdoorPvp' = '0'
}
Write-Configuration 'source\modules\mod-autobalance\conf\AutoBalance.conf.dist' 'modules\AutoBalance.conf' @{
    'AutoBalance.Enable.Global' = '1'
    'AutoBalance.MinPlayers' = '1'
    'AutoBalance.MinPlayers.Heroic' = '1'
    'AutoBalance.MinPlayers.Raid' = '1'
    'AutoBalance.MinPlayers.RaidHeroic' = '1'
}
Write-Host 'Local server configuration written: Playerbots (50) and AutoBalance enabled.'
