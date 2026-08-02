[CmdletBinding()]
param(
    [string]$ProjectRoot = "D:\HSR_Battle_Agent\hsr-battle-agent",
    [string]$RemoteUrl = "https://github.com/eryou1202/hsr-battle-agent.git",
    [switch]$ReplaceOrigin,
    [switch]$CommitAndPush
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

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not installed or is not available in PATH."
}

if (-not (Test-Path -LiteralPath $ProjectRoot)) {
    throw "Project directory does not exist: $ProjectRoot"
}

Set-Location -LiteralPath $ProjectRoot

if (-not (Test-Path -LiteralPath ".git")) {
    & git init -b main
    if ($LASTEXITCODE -ne 0) {
        Invoke-Git init
        Invoke-Git branch -M main
    }
} else {
    Write-Host "Existing Git repository detected."
}

$currentBranch = (& git branch --show-current).Trim()
if (-not $currentBranch) {
    Invoke-Git switch -c main
} elseif ($currentBranch -ne "main") {
    Invoke-Git branch -M main
}

$origin = (& git remote get-url origin 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $origin) {
    Invoke-Git remote add origin $RemoteUrl
} elseif ($origin.Trim() -ne $RemoteUrl) {
    if ($ReplaceOrigin) {
        Invoke-Git remote set-url origin $RemoteUrl
    } else {
        throw "origin currently points to '$($origin.Trim())'. Re-run with -ReplaceOrigin to replace it."
    }
}

$placeholderDirectories = @(
    "data/sources",
    "data/extracted",
    "data/normalized",
    "data/diffs",
    "data/traces",
    "data/episodes",
    "data/datasets",
    "data/model_artifacts"
)
foreach ($directory in $placeholderDirectories) {
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    $gitkeep = Join-Path $directory ".gitkeep"
    if (-not (Test-Path -LiteralPath $gitkeep)) {
        New-Item -ItemType File -Path $gitkeep | Out-Null
    }
}

$dangerousFiles = Get-ChildItem -Recurse -Force -File |
    Where-Object {
        $_.FullName -notmatch "\\\.git\\" -and (
            $_.Name -eq ".env" -or
            $_.Extension -in @(".pem", ".pfx", ".p12", ".key") -or
            $_.Name -match "^id_rsa"
        )
    }

if ($dangerousFiles) {
    Write-Host "Potential secret files were found:" -ForegroundColor Red
    $dangerousFiles.FullName | ForEach-Object { Write-Host "  $_" }
    throw "Remove or ignore secret files before the first commit."
}

$largeFiles = Get-ChildItem -Recurse -Force -File |
    Where-Object {
        $_.FullName -notmatch "\\\.git\\" -and $_.Length -gt 50MB
    } |
    Sort-Object Length -Descending

if ($largeFiles) {
    Write-Host "Files larger than 50 MiB were found. Confirm they are ignored:" -ForegroundColor Yellow
    $largeFiles | ForEach-Object {
        Write-Host ("  {0:N1} MiB  {1}" -f ($_.Length / 1MB), $_.FullName)
    }
}

Write-Host ""
Write-Host "Repository configured:"
Invoke-Git status --short --branch
Invoke-Git remote -v

if (-not $CommitAndPush) {
    Write-Host ""
    Write-Host "Configuration completed without committing."
    Write-Host "Review the files, then run again with -CommitAndPush."
    exit 0
}

$userName = (& git config user.name).Trim()
$userEmail = (& git config user.email).Trim()
if (-not $userName -or -not $userEmail) {
    throw @"
Git author identity is missing. Configure it first:
  git config --global user.name "Your Name"
  git config --global user.email "you@example.com"
"@
}

Invoke-Git add .
& git diff --cached --check
if ($LASTEXITCODE -ne 0) {
    throw "Whitespace errors detected in staged changes."
}

& git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "Nothing to commit."
} else {
    Invoke-Git commit -m "chore(repo): initialize project skeleton"
}

Invoke-Git push -u origin main
Write-Host "Initial repository push completed." -ForegroundColor Green
