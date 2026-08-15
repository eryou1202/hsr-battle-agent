# resolve_python.ps1
#
# Deterministic Python interpreter resolution for HSR project scripts.
#
# CONFIRMED on the current Windows DSH workstation:
#   - bare `python` resolves to Python 3.14.3 first, which fails with
#     0xc0000142 in this environment -> NOT USED;
#   - C:\WINDOWS\py.exe also fails with 0xc0000142 -> NOT USED;
#   - the local Python 3.11.9 installation has been verified working.
#
# Resolution order (no probing of unknown interpreters):
#   1. caller-provided -PythonExe (Test-Path only);
#   2. environment variable HSR_PYTHON_EXE (Test-Path only);
#   3. verified local workstation fallback:
#      <LOCALAPPDATA>\Programs\Python\Python311\python.exe (Test-Path only);
#   4. otherwise FAIL with an explicit message telling the caller to pass
#      -PythonExe or set HSR_PYTHON_EXE.
#
# This script never modifies system/user PATH and never auto-launches an
# unknown Python executable to "try it out".
#
# Usage (dot-source from another script):
#   . (Join-Path $PSScriptRoot "scripts\python\resolve_python.ps1")
#   $Py = Resolve-PythonInterpreter            # or -PythonExe <path>
#   & $Py.Exe $ScriptPath <args>
#
# Standalone diagnostic:
#   powershell -NoProfile -File scripts\python\resolve_python.ps1 -Resolve

[CmdletBinding()]
param(
    [string]$PythonExe = "",
    [switch]$Resolve
)

Set-StrictMode -Version 2.0

function Resolve-PythonInterpreter {
    [CmdletBinding()]
    param(
        [string]$PythonExe = ""
    )

    $origin = ""

    # 1. Explicit caller-provided interpreter.
    if (-not $PythonExe) {
        # 2. Project-specific environment variable.
        $PythonExe = $env:HSR_PYTHON_EXE
        if ($PythonExe) {
            $origin = "environment variable HSR_PYTHON_EXE"
        }
    } else {
        $origin = "explicit -PythonExe"
    }

    # 3. Verified local workstation fallback (current machine only).
    if (-not $PythonExe) {
        $fallback = Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"
        if (Test-Path -LiteralPath $fallback -PathType Leaf) {
            $PythonExe = $fallback
            $origin = "verified local fallback (Python 3.11 on this workstation)"
        }
    }

    if (-not $PythonExe) {
        throw ("No Python interpreter available. " +
            "Pass -PythonExe <path> or set HSR_PYTHON_EXE to a verified python.exe.")
    }

    if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
        throw "Python interpreter path does not exist: $PythonExe"
    }

    return [pscustomobject]@{
        Exe = (Resolve-Path -LiteralPath $PythonExe).Path
        BaseArgs = @()
        Origin = $origin
    }
}

if ($Resolve) {
    $result = Resolve-PythonInterpreter -PythonExe $PythonExe
    Write-Output ("exe=" + $result.Exe)
    Write-Output ("base_args=" + ($result.BaseArgs -join " "))
    Write-Output ("origin=" + $result.Origin)
}
