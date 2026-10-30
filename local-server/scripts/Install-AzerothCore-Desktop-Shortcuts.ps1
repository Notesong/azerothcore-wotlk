[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$installationRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot)).TrimEnd('\')
$iconDirectory = Join-Path $installationRoot 'launcher-integration\icons'
$desktopDirectory = [Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory)
if ([string]::IsNullOrWhiteSpace($desktopDirectory) -or
    -not (Test-Path -LiteralPath $desktopDirectory -PathType Container)) {
    throw 'The current user Desktop directory could not be resolved. No shortcuts were installed.'
}
$desktopDirectory = [IO.Path]::GetFullPath($desktopDirectory)

$shortcutDefinitions = @(
    [pscustomobject]@{
        Name = 'Start AzerothCore.lnk'
        Target = Join-Path $installationRoot 'Start Server.cmd'
        Icon = Join-Path $iconDirectory 'azerothcore-start.ico'
        Glyph = 'Play'
        Description = 'Start the local AzerothCore server. The server runs independently of ChatGPT.'
    },
    [pscustomobject]@{
        Name = 'Stop AzerothCore.lnk'
        Target = Join-Path $installationRoot 'Stop Server.cmd'
        Icon = Join-Path $iconDirectory 'azerothcore-stop.ico'
        Glyph = 'Stop'
        Description = 'Clean shutdown: save characters, stop the world and login servers, then shut down the database.'
    }
)

function Get-NormalizedPath([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return '' }
    [IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($Path)).TrimEnd('\')
}

function Test-SamePath([string]$Left, [string]$Right) {
    [string]::Equals((Get-NormalizedPath $Left), (Get-NormalizedPath $Right),
        [StringComparison]::OrdinalIgnoreCase)
}

function Assert-OwnedShortcut([string]$Path, $Shell) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "The shortcut name is occupied by a directory: $Path. It was left unchanged."
    }
    $existing = $Shell.CreateShortcut($Path)
    try {
        $target = Get-NormalizedPath ([string]$existing.TargetPath)
        $belongsToInstallation = $target -and (
            [string]::Equals($target, $installationRoot, [StringComparison]::OrdinalIgnoreCase) -or
            $target.StartsWith($installationRoot + '\', [StringComparison]::OrdinalIgnoreCase))
        if (-not $belongsToInstallation) {
            throw "An existing shortcut does not point inside this AzerothCore installation: $Path. It was left unchanged."
        }
    } finally {
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($existing)
    }
}

function Set-AtomicFile([string]$TemporaryPath, [string]$DestinationPath) {
    if (Test-Path -LiteralPath $DestinationPath -PathType Leaf) {
        [IO.File]::Replace($TemporaryPath, $DestinationPath, [System.Management.Automation.Language.NullString]::Value)
    } else {
        # File.Move refuses an unexpected destination created after preflight.
        [IO.File]::Move($TemporaryPath, $DestinationPath)
    }
}

function Assert-Icon([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $reader = [IO.BinaryReader]::new($stream)
    try {
        if ($reader.ReadUInt16() -ne 0 -or $reader.ReadUInt16() -ne 1) {
            throw "The generated icon has an invalid ICO header: $Path"
        }
        $count = $reader.ReadUInt16()
        if ($count -ne 6) { throw "The generated icon does not contain all six image sizes: $Path" }
        for ($index = 0; $index -lt $count; $index++) {
            [void]$reader.ReadBytes(8)
            $length = $reader.ReadUInt32()
            $offset = $reader.ReadUInt32()
            if ($length -lt 8 -or $offset -lt 6 + 16 * $count -or $offset + $length -gt $stream.Length) {
                throw "The generated icon contains an invalid image entry: $Path"
            }
            $nextEntry = $stream.Position
            $stream.Position = $offset
            $signature = $reader.ReadBytes(8)
            if ([BitConverter]::ToString($signature) -ne '89-50-4E-47-0D-0A-1A-0A') {
                throw "The generated icon contains an invalid PNG image: $Path"
            }
            $stream.Position = $nextEntry
        }
    } finally {
        $reader.Dispose()
        $stream.Dispose()
    }
}

function New-LauncherIcon([string]$Path, [ValidateSet('Play', 'Stop')][string]$Glyph) {
    $images = @()
    foreach ($size in @(16, 32, 48, 64, 128, 256)) {
        $bitmap = [Drawing.Bitmap]::new($size, $size, [Drawing.Imaging.PixelFormat]::Format32bppArgb)
        $graphics = [Drawing.Graphics]::FromImage($bitmap)
        $memory = [IO.MemoryStream]::new()
        $fill = $null
        $border = $null
        $symbol = $null
        try {
            $graphics.Clear([Drawing.Color]::Transparent)
            $graphics.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::AntiAlias
            $graphics.PixelOffsetMode = [Drawing.Drawing2D.PixelOffsetMode]::HighQuality
            $graphics.CompositingQuality = [Drawing.Drawing2D.CompositingQuality]::HighQuality
            $fillColor = if ($Glyph -eq 'Play') {
                [Drawing.Color]::FromArgb(255, 22, 137, 78)
            } else {
                [Drawing.Color]::FromArgb(255, 203, 45, 49)
            }
            $borderColor = if ($Glyph -eq 'Play') {
                [Drawing.Color]::FromArgb(255, 9, 92, 52)
            } else {
                [Drawing.Color]::FromArgb(255, 139, 25, 30)
            }
            $fill = [Drawing.SolidBrush]::new($fillColor)
            $border = [Drawing.Pen]::new($borderColor, [single][Math]::Max(1, $size * 0.025))
            $symbol = [Drawing.SolidBrush]::new([Drawing.Color]::White)
            $graphics.FillEllipse($fill, [single]($size * 0.07), [single]($size * 0.07),
                [single]($size * 0.86), [single]($size * 0.86))
            $graphics.DrawEllipse($border, [single]($size * 0.07), [single]($size * 0.07),
                [single]($size * 0.86), [single]($size * 0.86))
            if ($Glyph -eq 'Play') {
                $points = [Drawing.PointF[]]@(
                    [Drawing.PointF]::new([single]($size * 0.39), [single]($size * 0.27)),
                    [Drawing.PointF]::new([single]($size * 0.39), [single]($size * 0.73)),
                    [Drawing.PointF]::new([single]($size * 0.73), [single]($size * 0.50))
                )
                $graphics.FillPolygon($symbol, $points)
            } else {
                $graphics.FillRectangle($symbol, [single]($size * 0.32), [single]($size * 0.32),
                    [single]($size * 0.36), [single]($size * 0.36))
            }
            $bitmap.Save($memory, [Drawing.Imaging.ImageFormat]::Png)
            $images += [pscustomobject]@{ Size = $size; Bytes = $memory.ToArray() }
        } finally {
            if ($symbol) { $symbol.Dispose() }
            if ($border) { $border.Dispose() }
            if ($fill) { $fill.Dispose() }
            $memory.Dispose()
            $graphics.Dispose()
            $bitmap.Dispose()
        }
    }

    $temporaryPath = Join-Path $iconDirectory ('.azerothcore-icon-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    try {
        $stream = [IO.File]::Open($temporaryPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
        $writer = [IO.BinaryWriter]::new($stream)
        try {
            $writer.Write([uint16]0)
            $writer.Write([uint16]1)
            $writer.Write([uint16]$images.Count)
            $offset = 6 + 16 * $images.Count
            foreach ($entry in $images) {
                $dimension = if ($entry.Size -eq 256) { 0 } else { $entry.Size }
                $writer.Write([byte]$dimension)
                $writer.Write([byte]$dimension)
                $writer.Write([byte]0)
                $writer.Write([byte]0)
                $writer.Write([uint16]1)
                $writer.Write([uint16]32)
                $writer.Write([uint32]$entry.Bytes.Length)
                $writer.Write([uint32]$offset)
                $offset += $entry.Bytes.Length
            }
            foreach ($entry in $images) { $writer.Write([byte[]]$entry.Bytes) }
        } finally {
            $writer.Dispose()
            $stream.Dispose()
        }
        Assert-Icon $temporaryPath
        Set-AtomicFile $temporaryPath $Path
        Assert-Icon $Path
    } finally {
        if (Test-Path -LiteralPath $temporaryPath -PathType Leaf) {
            Remove-Item -LiteralPath $temporaryPath -ErrorAction SilentlyContinue
        }
    }
}

function Assert-ShortcutProperties([string]$Path, $Definition, $Shell) {
    $shortcut = $Shell.CreateShortcut($Path)
    try {
        if (-not (Test-SamePath ([string]$shortcut.TargetPath) $Definition.Target) -or
            -not (Test-SamePath ([string]$shortcut.WorkingDirectory) $installationRoot) -or
            [string]$shortcut.Arguments -ne '' -or
            [string]$shortcut.Description -ne $Definition.Description -or
            [string]$shortcut.IconLocation -ne ($Definition.Icon + ',0') -or
            [int]$shortcut.WindowStyle -ne 1) {
            throw "Shortcut verification failed: $Path"
        }
    } finally {
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($shortcut)
    }
}

foreach ($definition in $shortcutDefinitions) {
    if (-not (Test-Path -LiteralPath $definition.Target -PathType Leaf)) {
        throw "Launcher target is missing: $($definition.Target). No shortcuts were installed."
    }
}

$shell = New-Object -ComObject WScript.Shell
try {
    # Check both names before touching Desktop. An unrelated existing shortcut is
    # never overwritten, even if only the second name conflicts.
    foreach ($definition in $shortcutDefinitions) {
        Assert-OwnedShortcut (Join-Path $desktopDirectory $definition.Name) $shell
    }

    Add-Type -AssemblyName System.Drawing
    [void][IO.Directory]::CreateDirectory($iconDirectory)
    foreach ($definition in $shortcutDefinitions) {
        New-LauncherIcon $definition.Icon $definition.Glyph
    }

    foreach ($definition in $shortcutDefinitions) {
        $destination = Join-Path $desktopDirectory $definition.Name
        $temporary = Join-Path $desktopDirectory ('.azerothcore-shortcut-' + [Guid]::NewGuid().ToString('N') + '.lnk')
        try {
            $shortcut = $shell.CreateShortcut($temporary)
            try {
                $shortcut.TargetPath = $definition.Target
                $shortcut.WorkingDirectory = $installationRoot
                $shortcut.Arguments = ''
                $shortcut.IconLocation = $definition.Icon + ',0'
                $shortcut.WindowStyle = 1
                $shortcut.Description = $definition.Description
                $shortcut.Save()
            } finally {
                [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($shortcut)
            }
            Assert-ShortcutProperties $temporary $definition $shell
            # Recheck after building the temporary file, then atomically publish it.
            Assert-OwnedShortcut $destination $shell
            Set-AtomicFile $temporary $destination
            Assert-ShortcutProperties $destination $definition $shell
            [pscustomobject]@{
                Shortcut = $destination
                Target = $definition.Target
                WorkingDirectory = $installationRoot
                Icon = $definition.Icon
                Verified = $true
            }
        } finally {
            if (Test-Path -LiteralPath $temporary -PathType Leaf) {
                Remove-Item -LiteralPath $temporary -ErrorAction SilentlyContinue
            }
        }
    }
} finally {
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($shell)
}
