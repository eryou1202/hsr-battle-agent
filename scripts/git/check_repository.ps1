[CmdletBinding()]
param(
    [string]$ProjectRoot = "D:\HSR_Battle_Agent\hsr-battle-agent",
    [int]$LargeFileLimitMiB = 20
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not installed or is not available in PATH."
}
if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot ".git"))) {
    throw "Not a Git repository: $ProjectRoot"
}

Set-Location -LiteralPath $ProjectRoot

Write-Host "== Status =="
git status --short --branch

Write-Host "`n== Remotes =="
git remote -v

Write-Host "`n== Recent commits =="
git log --oneline --decorate -5

Write-Host "`n== Whitespace check =="
git diff --check
if ($LASTEXITCODE -ne 0) {
    throw "git diff --check failed."
}

Write-Host "`n== Repository integrity =="
git fsck --full
if ($LASTEXITCODE -ne 0) {
    throw "git fsck failed."
}

Write-Host "`n== Tracked large files =="
$limit = $LargeFileLimitMiB * 1MB
$largeTracked = @()
$trackedFiles = git ls-files
foreach ($relativePath in $trackedFiles) {
    if (Test-Path -LiteralPath $relativePath -PathType Leaf) {
        $item = Get-Item -LiteralPath $relativePath
        if ($item.Length -gt $limit) {
            $largeTracked += $item
        }
    }
}
if ($largeTracked.Count -eq 0) {
    Write-Host "No tracked files exceed $LargeFileLimitMiB MiB."
} else {
    $largeTracked |
        Sort-Object Length -Descending |
        ForEach-Object {
            Write-Host ("  {0:N1} MiB  {1}" -f ($_.Length / 1MB), $_.FullName)
        }
    throw "Large tracked files detected."
}

Write-Host "`nRepository checks passed." -ForegroundColor Green
