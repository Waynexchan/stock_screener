$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot
powershell -ExecutionPolicy Bypass -File .\scripts\verify_project.ps1
if ($LASTEXITCODE -ne 0) {
    Set-Content -LiteralPath .\data_failure_report.txt -Value "FAILED: project verification did not pass. Normal watchlist and email were not generated. See logs\verify_project.log."
    exit $LASTEXITCODE
}
$env:SCREENER_VERIFIED = "1"
$productionLog = Join-Path $projectRoot "logs\production.log"
Set-Content -LiteralPath $productionLog -Value "Production started: $(Get-Date -Format o)"
$previousErrorPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
python run_screener.py 2>&1 | Tee-Object -FilePath $productionLog -Append
$productionExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorPreference
Add-Content -LiteralPath $productionLog -Value "Production exit code: $productionExitCode"
exit $productionExitCode
