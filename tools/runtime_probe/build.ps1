<#
build.ps1 - build the runtime health-check probe, loader and self-tests with
the locally installed MSVC (no cmake/msbuild required).

Examples (run from repo root):
  pwsh -File tools\runtime_probe\build.ps1 -RunTests
  pwsh -File tools\runtime_probe\build.ps1 -UnityPath D:\StarRail_4.4.53\UnityPlayer.dll `
       -ExpectRva 0x1A36480 -RunTests
#>
param(
    [switch]$RunTests,
    [string]$UnityPath = "",
    [string]$ExpectRva = "",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$RuntimeProbe = Split-Path -Parent $MyInvocation.MyCommand.Path
$Repo = (Resolve-Path "$RuntimeProbe\..\..").Path
$BuildDir = Join-Path $RuntimeProbe "build"
$ProbeDir = Join-Path $RuntimeProbe "probe"
$LoaderDir = Join-Path $RuntimeProbe "loader"
$TestsDir = Join-Path $RuntimeProbe "tests"
$GenScript = Join-Path $RuntimeProbe "scripts\gen_locator_prior.py"

if ($Clean) {
    if (Test-Path $BuildDir) {
        Remove-Item -Recurse -Force $BuildDir
        Write-Host "removed $BuildDir"
    }
    exit 0
}

New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null

# --- locate cl / set MSVC environment (NO vswhere) ---------------------------
# 1. Prefer cl.exe already present in PATH.
$ClPath = Get-Command cl.exe -ErrorAction SilentlyContinue

# 2. Otherwise use the CONFIRMED Visual Studio installation and the installed
#    Windows SDK. Validate every path with Test-Path; never guess.
$VsRoot = "D:\VSCcommunity"
$VsDevCmd = Join-Path $VsRoot "Common7\Tools\VsDevCmd.bat"
$VcVars64 = Join-Path $VsRoot "VC\Auxiliary\Build\vcvars64.bat"
$MsvcTools = Join-Path $VsRoot "VC\Tools\MSVC"
$WindowsKits = "D:\Windows Kits\10"
Write-Host "VsDevCmd.bat exists: $(Test-Path $VsDevCmd)"
Write-Host "vcvars64.bat exists: $(Test-Path $VcVars64)"

if (-not $ClPath) {
    if (-not (Test-Path $VsDevCmd)) {
        throw "VsDevCmd.bat not found under $VsRoot; cannot build"
    }
    if (-not (Test-Path $VcVars64)) {
        throw "vcvars64.bat not found under $VsRoot; cannot build"
    }
    if (-not (Test-Path $MsvcTools)) {
        throw "MSVC tools directory not found: $MsvcTools"
    }
    $MsvcVer = Get-ChildItem $MsvcTools -Directory |
        Sort-Object Name -Descending |
        Select-Object -First 1 -ExpandProperty Name
    if (-not $MsvcVer) {
        throw "no MSVC toolset version found under $MsvcTools"
    }
    $MsvcDir = Join-Path $MsvcTools $MsvcVer
    $MsvcCl = Join-Path $MsvcDir "bin\Hostx64\x64\cl.exe"
    if (-not (Test-Path $MsvcCl)) {
        throw "cl.exe not found at expected path: $MsvcCl"
    }
    $SdkInclude = Join-Path $WindowsKits "Include"
    $SdkLib = Join-Path $WindowsKits "Lib"
    if (-not (Test-Path $SdkInclude) -or -not (Test-Path $SdkLib)) {
        throw "Windows SDK directories not found under $WindowsKits"
    }
    $SdkVer = Get-ChildItem $SdkInclude -Directory |
        Sort-Object Name -Descending |
        Select-Object -First 1 -ExpandProperty Name
    if (-not $SdkVer -or -not (Test-Path (Join-Path $SdkLib $SdkVer))) {
        throw "no matching Windows SDK Include/Lib version found under $WindowsKits"
    }
    $env:PATH = "$MsvcDir\bin\Hostx64\x64;$WindowsKits\bin\$SdkVer\x64;$WindowsKits\bin\$SdkVer\x86;" + $env:PATH
    $env:INCLUDE = "$MsvcDir\include;$SdkInclude\$SdkVer\ucrt;$SdkInclude\$SdkVer\shared;$SdkInclude\$SdkVer\um;$SdkInclude\$SdkVer\winrt;$SdkInclude\$SdkVer\cppwinrt"
    $env:LIB = "$MsvcDir\lib\x64;$SdkLib\$SdkVer\ucrt\x64;$SdkLib\$SdkVer\um\x64"
    $ClPath = Get-Command cl.exe -ErrorAction SilentlyContinue
    if (-not $ClPath) {
        throw "cl.exe still unavailable after setting MSVC/SDK environment"
    }
    Write-Host "MSVC env set manually: $MsvcDir (SDK $SdkVer)"
} else {
    Write-Host "cl.exe already available in PATH: $($ClPath.Source)"
}

# --- regenerate locator prior header from the canonical Python locator ------
Write-Host "regenerating locator prior from find_il2cpp_api_table.py"
$PriorPath = Join-Path $RuntimeProbe "gen\locator_prior.h"
cmd /c "python `"$GenScript`" --out `"$PriorPath`""
if ($LASTEXITCODE -ne 0) {
    throw "locator prior generation failed"
}

# --- copy probe config next to the DLL --------------------------------------
Copy-Item (Join-Path $RuntimeProbe "probe_config.ini") `
    (Join-Path $BuildDir "probe_config.ini") -Force

$commonFlags = "/nologo /std:c++17 /O2 /MT /EHsc /W4 /permissive- /DUNICODE /D_UNICODE"

$coreSources = @(
    "..\probe\common.cpp",
    "..\probe\pe_model.cpp",
    "..\probe\pointer_validation.cpp",
    "..\probe\api_locator.cpp",
    "..\probe\json.cpp",
    "..\probe\log_sink.cpp",
    "..\probe\health_check.cpp"
)

function Invoke-Cl([string]$arguments) {
    cmd /c $arguments
    if ($LASTEXITCODE -ne 0) {
        throw "cl failed with exit code $LASTEXITCODE`ncommand: $arguments"
    }
}

Push-Location $BuildDir
try {
    Write-Host "building hsr_runtime_health_probe.dll"
    $probeSources = @($coreSources + @("..\probe\dll_main.cpp")) -join " "
    Invoke-Cl "cl $commonFlags /LD $probeSources /link /OUT:hsr_runtime_health_probe.dll"

    Write-Host "building load_probe.exe"
    Invoke-Cl "cl $commonFlags ..\loader\load_probe.cpp ..\probe\common.cpp ..\probe\pe_model.cpp ..\probe\api_locator.cpp /Fe:load_probe.exe"

    Write-Host "building probe_self_tests.exe"
    $testSources = @($coreSources + @("..\tests\probe_self_tests.cpp")) -join " "
    Invoke-Cl "cl $commonFlags $testSources /Fe:probe_self_tests.exe"

    Write-Host "building read_cstring_mini.exe"
    Invoke-Cl "cl $commonFlags ..\tests\read_cstring_mini.cpp ..\probe\pointer_validation.cpp ..\probe\pe_model.cpp /Fe:read_cstring_mini.exe"
}
finally {
    Pop-Location
}

Write-Host "build outputs:"
Get-ChildItem $BuildDir -File | ForEach-Object { Write-Host "  $($_.FullName)" }

if ($RunTests) {
    Write-Host "running read_cstring_mini.exe"
    & (Join-Path $BuildDir "read_cstring_mini.exe")
    if ($LASTEXITCODE -ne 0) {
        throw "read_cstring mini test failed with exit code $LASTEXITCODE"
    }

    $testArgs = @()
    if ($UnityPath) {
        $testArgs += "--unity-path"
        $testArgs += (Resolve-Path $UnityPath).Path
    }
    if ($ExpectRva) {
        $testArgs += "--expect-rva"
        $testArgs += $ExpectRva
    }
    Write-Host "running probe_self_tests.exe $($testArgs -join ' ')"
    & (Join-Path $BuildDir "probe_self_tests.exe") @testArgs
    if ($LASTEXITCODE -ne 0) {
        throw "probe self-tests failed with exit code $LASTEXITCODE"
    }
    Write-Host "probe self-tests passed"
}
