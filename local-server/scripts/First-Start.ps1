$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$settings = Get-Content -LiteralPath (Join-Path $root 'local-settings.json') -Raw | ConvertFrom-Json
$admin = Get-Content -LiteralPath (Join-Path $root 'server-admin.json') -Raw | ConvertFrom-Json
$startInfo = New-Object Diagnostics.ProcessStartInfo
$startInfo.FileName = Join-Path $root 'server\worldserver.exe'
$startInfo.Arguments = '-c "' + (Join-Path $root 'server\configs\worldserver.conf') + '"'
$startInfo.WorkingDirectory = Join-Path $root 'server'
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$startInfo.RedirectStandardInput = $true
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $true
$world = New-Object Diagnostics.Process
$world.StartInfo = $startInfo
[void]$world.Start()
$stdoutTask = $world.StandardOutput.ReadToEndAsync()
$stderrTask = $world.StandardError.ReadToEndAsync()
Write-Host ('World initialization started (PID {0}).' -f $world.Id)
$ready = $false
$deadline = [DateTime]::UtcNow.AddMinutes(20)
while ([DateTime]::UtcNow -lt $deadline -and -not $world.HasExited) {
    $client = New-Object Net.Sockets.TcpClient
    try {
        $connect = $client.ConnectAsync('127.0.0.1', 8085)
        if ($connect.Wait(1000) -and $client.Connected) { $ready = $true; break }
    } catch { } finally { $client.Dispose() }
    Start-Sleep -Seconds 2
}
if ($ready) {
    $mysql = Join-Path $root 'tools\mysql-8.4.13-winx64\bin\mysql.exe'
    foreach ($account in @(
        @{ Username = $settings.GameUsername; Password = $settings.GamePassword },
        @{ Username = $admin.Username; Password = $admin.Password }
    )) {
        $username = [string]$account.Username
        if ($username -notmatch '^[A-Za-z0-9_]{1,16}$') { throw 'Invalid initial account name.' }
        $world.StandardInput.WriteLine('account create ' + $username + ' ' + $account.Password)
        $world.StandardInput.Flush()
        # Account creation queues an asynchronous database write. Wait for it before assigning access.
        $accountExists = $false
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            $accountId = & $mysql "--defaults-extra-file=$(Join-Path $root 'database-admin.cnf')" `
                --batch --skip-column-names --execute="SELECT id FROM acore_auth.account WHERE username='$username';"
            if ($LASTEXITCODE -eq 0 -and $accountId -match '^\d+$') { $accountExists = $true; break }
            Start-Sleep -Milliseconds 300
        }
        if (-not $accountExists) { throw 'Initial account creation did not complete.' }
        $world.StandardInput.WriteLine('account set gmlevel ' + $username + ' 3 -1')
        $world.StandardInput.WriteLine('account set addon ' + $username + ' 2')
        $world.StandardInput.Flush()
    }
    Write-Host 'World listener ready; initial game and local administration accounts requested.'
} elseif (-not $world.HasExited) {
    Write-Host 'World initialization is taking longer than expected; check logs\Server.log.'
}
$world.WaitForExit()
$stdout = $stdoutTask.GetAwaiter().GetResult()
$stderr = $stderrTask.GetAwaiter().GetResult()
foreach ($secret in @($settings.GamePassword, $settings.DatabasePassword, $admin.Password)) {
    $stdout = $stdout.Replace($secret, '[redacted]')
    $stderr = $stderr.Replace($secret, '[redacted]')
}
[IO.File]::WriteAllText((Join-Path $root 'logs\first-world-console.log'), $stdout)
[IO.File]::WriteAllText((Join-Path $root 'logs\first-world-errors.log'), $stderr)
Write-Host ('World initialization process exited with code {0}.' -f $world.ExitCode)
exit $world.ExitCode
