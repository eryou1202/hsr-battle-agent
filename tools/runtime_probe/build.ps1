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

# --- locate MSVC -----------------------------------------------------------
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $vswhere)) {
    throw "vswhere.exe not found; MSVC toolchain unavailable"
}
$installPath = & $vswhere -latest -products * `
    -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
    -property installationPath
if ($LASTEXITCODE -ne 0 -or -not $installPath) {
    throw "vswhere could not find an MSVC installation with VC x64 tools"
}
$vcvars = Join-Path $installPath "VC\Auxiliary\Build\vcvars64.bat"
if (-not (Test-Path $vcvars)) {
    throw "vcvars64.bat not found under $installPath"
}
Write-Host "MSVC: $installPath"

# --- regenerate locator prior header from the canonical Python locator ------
Write-Host "regenerating locator prior from find_il2cpp_api_table.py"
& python $GenScript --out (Join-Path $RuntimeProbe "gen\locator_prior.h")
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
    $cmd = "call `"$vcvars`" >nul 2>&1 && $arguments"
    cmd /c $cmd
    if ($LASTEXITCODE -ne 0) {
        throw "cl failed with exit code $LASTEXITCODE`ncommand: $cmd"
    }
}

Push-Location $BuildDir
try {
    Write-Host "building hsr_runtime_health_probe.dll"
    $probeSources = @($coreSources + @("..\probe\dll_main.cpp")) -join " "
    Invoke-Cl "cl $commonFlags /LD $probeSources /link /OUT:hsr_runtime_health_probe.dll"

    Write-Host "building load_probe.exe"
    Invoke-Cl "cl $commonFlags ..\loader\load_probe.cpp /Fe:load_probe.exe"

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
