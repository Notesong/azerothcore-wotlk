$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class AzerothProcessJobInspection
{
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr OpenProcess(uint access, bool inherit, uint processId);
    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsProcessInJob(IntPtr process, IntPtr job,
        [MarshalAs(UnmanagedType.Bool)] out bool result);
    [DllImport("kernel32.dll")]
    private static extern bool CloseHandle(IntPtr handle);
    public static bool InAnyJob(uint processId)
    {
        IntPtr handle = OpenProcess(0x1000, false, processId);
        if (handle == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
        try
        {
            bool result;
            if (!IsProcessInJob(handle, IntPtr.Zero, out result))
                throw new Win32Exception(Marshal.GetLastWin32Error());
            return result;
        }
        finally { CloseHandle(handle); }
    }
}
'@
$inspectionRoot = 'C:\Games\AzerothCore'
$inspectionPaths = @(
    (Join-Path $inspectionRoot 'server\worldserver.exe'),
    (Join-Path $inspectionRoot 'server\authserver.exe'),
    (Join-Path $inspectionRoot 'tools\mysql-8.4.13-winx64\bin\mysqld.exe')
)
$inspectionRecords = @(foreach ($inspectionPath in $inspectionPaths) {
    $inspectionName = [IO.Path]::GetFileName($inspectionPath)
    $inspectionFound = @(Get-CimInstance Win32_Process -Filter "Name='$inspectionName'" |
        Where-Object { $_.ExecutablePath -eq $inspectionPath })
    if ($inspectionFound.Count -ne 1) { throw "Expected exactly one $inspectionName." }
    $inspectionProcess = $inspectionFound[0]
    $inspectionParent = Get-CimInstance Win32_Process -Filter "ProcessId = $($inspectionProcess.ParentProcessId)"
    $inspectionInJob = [AzerothProcessJobInspection]::InAnyJob([uint32]$inspectionProcess.ProcessId)
    if ($inspectionInJob) { throw "$inspectionName is unexpectedly in a Windows job." }
    $inspectionParentState = 'exited_or_unavailable'
    if ($inspectionParent -and $inspectionParent.CreationDate -le $inspectionProcess.CreationDate) {
        if ($inspectionParent.Name -ne 'WmiPrvSE.exe') {
            throw "$inspectionName has an unexpected live parent."
        }
        $inspectionParentState = $inspectionParent.Name
    } elseif ($inspectionParent) {
        $inspectionParentState = 'parent_pid_reused'
    }
    # The broker may exit normally. Job membership, not parent liveness, is the
    # guarantee that closing ChatGPT cannot terminate this process with its job.
    [ordered]@{name=$inspectionName;pid=$inspectionProcess.ProcessId;
        parent_pid=$inspectionProcess.ParentProcessId;parent=$inspectionParentState;in_windows_job=$inspectionInJob}
})
$inspectionReport = [ordered]@{checked_at=[DateTime]::UtcNow.ToString('o');processes=$inspectionRecords}
$inspectionJson = $inspectionReport | ConvertTo-Json -Depth 5
[IO.File]::WriteAllText((Join-Path $inspectionRoot 'launcher-integration\independent-processes.json'),
    $inspectionJson, (New-Object Text.UTF8Encoding($false)))
Write-Output $inspectionJson
