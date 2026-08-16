# unpack_version.ps1
#
# HSR unpack/reverse pipeline v1 entry point.
#
# Usage:
#   .\scripts\unpack_version.ps1 -GameRoot "D:\path\to\StarRail_client"
#
# Optional:
#   -PythonExe <path>        explicit verified python.exe
#   -RuntimeSnapshot <json>  read-only generated-registry snapshot (optional)
#   -ReferenceNormalized <dir>  baseline normalized dir for full version diff
#   -LegacyReference <dir>      archived raw evidence dir for partial diff
#   -OutputRoot/-NormalizedRoot/-DiffRoot override pipeline roots
#
# Python is resolved only through scripts/python/resolve_python.ps1.
# No PATH-based launcher probing is performed by this script.

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string]$GameRoot,

    [string]$PythonExe = "",

    [string]$RuntimeSnapshot = "",

    [string]$ReferenceNormalized = "",

    [string]$LegacyReference = "",

    [string]$OutputRoot = "",

    [string]$NormalizedRoot = "",

    [string]$DiffRoot = ""
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path -LiteralPath $GameRoot -PathType Container)) {
    throw "GameRoot does not exist: $GameRoot"
}

. (Join-Path $PSScriptRoot "python\resolve_python.ps1")
$Python = Resolve-PythonInterpreter -PythonExe $PythonExe

$Pipeline = Join-Path $RepoRoot "tools\unpack_pipeline\run_pipeline.py"
if (-not (Test-Path -LiteralPath $Pipeline -PathType Leaf)) {
    throw "Pipeline entry point missing: $Pipeline"
}

$PythonArgs = @("-m", "tools.unpack_pipeline.run_pipeline", "--game-root", $GameRoot)

if (-not $OutputRoot) {
    $OutputRoot = Join-Path $RepoRoot "data\parsed"
}
$PythonArgs += @("--output-root", $OutputRoot)

if (-not $NormalizedRoot) {
    $NormalizedRoot = Join-Path $RepoRoot "data\normalized"
}
$PythonArgs += @("--normalized-root", $NormalizedRoot)

if (-not $DiffRoot) {
    $DiffRoot = Join-Path $RepoRoot "data\diff"
}
$PythonArgs += @("--diff-root", $DiffRoot)

if ($RuntimeSnapshot) {
    $PythonArgs += @("--runtime-snapshot", $RuntimeSnapshot)
}
if ($ReferenceNormalized) {
    $PythonArgs += @("--reference-normalized", $ReferenceNormalized)
}
if ($LegacyReference) {
    $PythonArgs += @("--legacy-reference", $LegacyReference)
}

Write-Host ("[unpack_version] python=" + $Python.Exe + " origin=" + $Python.Origin)
Write-Host ("[unpack_version] game_root=" + (Resolve-Path -LiteralPath $GameRoot).Path)

Push-Location $RepoRoot
try {
    & $Python.Exe @PythonArgs
    $ExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}
exit $ExitCode
