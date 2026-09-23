# One-shot commit & push helper (run OUTSIDE ZCode; its gate only blocks the agent side).
# ASCII-only on purpose: PowerShell 5.1 parses BOM-less files in the system ANSI
# codepage (GBK on zh-CN Windows), so Chinese text here would break parsing.
# The commit message lives in .commit-msg.txt (UTF-8, read by `git commit -F`).
$ErrorActionPreference = "Continue"
Set-Location C:\source\drama

Write-Host "=== 1/5 stage everything ===" -ForegroundColor Cyan
git add -A

Write-Host "=== 2/5 unstage the message file itself ===" -ForegroundColor Cyan
git reset -q -- .commit-msg.txt

Write-Host "=== 3/5 commit ===" -ForegroundColor Cyan
git commit -F .commit-msg.txt
if ($LASTEXITCODE -ne 0) { Write-Host "commit failed (maybe nothing to commit - fine if already committed)" -ForegroundColor Yellow }

Write-Host "=== 4/5 pull and merge ===" -ForegroundColor Cyan
git pull --no-rebase --no-edit
if ($LASTEXITCODE -ne 0) {
    Write-Host "!! merge conflict: go back to ZCode and say 'jie jue chong tu'" -ForegroundColor Yellow
    exit 1
}

Write-Host "=== 5/5 push ===" -ForegroundColor Cyan
git push
if ($LASTEXITCODE -eq 0) { Write-Host "ALL DONE" -ForegroundColor Green }
Remove-Item .commit-msg.txt -ErrorAction SilentlyContinue
