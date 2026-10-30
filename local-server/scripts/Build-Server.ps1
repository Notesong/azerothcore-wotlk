[CmdletBinding()]
param([ValidateRange(1, 8)][int]$ParallelProjects = 2)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
if (Get-Process -Name worldserver,authserver -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$root\server\*" }) {
    throw 'Stop this AzerothCore server before rebuilding its installed binaries.'
}
$cmake = Join-Path $root 'tools\cmake-3.31.12-windows-x86_64\bin\cmake.exe'
& $cmake -S source -B build -G 'Visual Studio 17 2022' -A x64 `
    '-DCMAKE_INSTALL_PREFIX=C:/Games/AzerothCore/server' '-DTOOLS_BUILD=all' '-DSCRIPTS=static' '-DMODULES=static' `
    '-DBOOST_ROOT=C:/Games/AzerothCore/tools/boost_1_81_0' `
    '-DBOOST_LIBRARYDIR=C:/Games/AzerothCore/tools/boost_1_81_0/lib64-msvc-14.3' '-DBoost_NO_BOOST_CMAKE=ON' `
    '-DOPENSSL_ROOT_DIR=C:/Games/AzerothCore/tools/OpenSSL-Win64' `
    '-DMYSQL_ROOT_DIR=C:/Games/AzerothCore/tools/mysql-8.4.13-winx64'
if ($LASTEXITCODE) { throw 'CMake configuration failed.' }
$env:_CL_ = '/MP8'
$env:MSBUILDDISABLENODEREUSE = '1'
& $cmake --build build --config RelWithDebInfo --parallel $ParallelProjects -- /nologo /nodeReuse:false /verbosity:minimal
if ($LASTEXITCODE) { throw 'Compilation failed.' }
& $cmake --install build --config RelWithDebInfo
if ($LASTEXITCODE) { throw 'Binary installation failed.' }
Copy-Item -LiteralPath (Join-Path $root 'tools\mysql-8.4.13-winx64\lib\libmysql.dll') -Destination server -Force
foreach ($dll in @('legacy.dll', 'libcrypto-3-x64.dll', 'libssl-3-x64.dll')) {
    Copy-Item -LiteralPath (Join-Path $root "tools\OpenSSL-Win64\bin\$dll") -Destination server -Force
}
foreach ($symbols in @('authserver.pdb', 'worldserver.pdb')) {
    Copy-Item -LiteralPath (Join-Path $root "build\bin\RelWithDebInfo\$symbols") -Destination server -Force
}
Write-Host 'Build installed. Existing live server settings and databases were preserved.'
