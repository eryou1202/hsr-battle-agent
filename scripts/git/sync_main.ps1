[CmdletBinding()]
param(
    [string]$ProjectRoot = "D:\HSR_Battle_Agent\hsr-battle-agent"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot ".git"))) {
    throw "Not a Git repository: $ProjectRoot"
}
Set-Location -LiteralPath $ProjectRoot

$dirty = git status --porcelain
if ($dirty) {
    git status --short
    throw "Working tree is not clean. Commit or stash changes before syncing main."
}

Invoke-Git fetch origin --prune
Invoke-Git switch main
Invoke-Git pull --ff-only origin main
Invoke-Git push origin main

Write-Host "main is synchronized with origin/main." -ForegroundColor Green
