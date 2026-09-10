$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot
powershell -ExecutionPolicy Bypass -File .\scripts\verify_project.ps1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python sample_daily_run.py
exit $LASTEXITCODE
