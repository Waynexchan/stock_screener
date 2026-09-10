param([switch]$SkipTooling)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$logDir = Join-Path $projectRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir "verify_project.log"
Set-Content -LiteralPath $logPath -Value "Verification started: $(Get-Date -Format o)"

function Invoke-Stage {
    param([string]$Name, [scriptblock]$Command)
    Write-Host "[$Name]"
    Add-Content -LiteralPath $logPath -Value "`n[$Name]"
    try {
        $previousErrorPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $Command 2>&1 | Tee-Object -FilePath $logPath -Append
        $stageExitCode = $LASTEXITCODE
        $ErrorActionPreference = $previousErrorPreference
        if ($stageExitCode -ne 0) { throw "exit code $stageExitCode" }
        Write-Host "PASS: $Name"
    } catch {
        $message = "FAILED: $Name - $($_.Exception.Message)"
        Write-Error $message
        Add-Content -LiteralPath $logPath -Value $message
        exit 1
    }
}

Set-Location $projectRoot
Invoke-Stage "Python syntax" { python -m compileall -q -x "[\\/]\.yfinance_cache|[\\/]logs" . }
if (-not $SkipTooling) {
    Invoke-Stage "Ruff format check" { python -m ruff format --check config.py decision_system.py run_screener.py ai_analysis.py send_email.py sample_daily_run.py tests }
    Invoke-Stage "Ruff lint" { python -m ruff check config.py decision_system.py run_screener.py ai_analysis.py send_email.py sample_daily_run.py tests }
    Invoke-Stage "mypy" { python -m mypy decision_system.py sample_daily_run.py --ignore-missing-imports --disable-error-code import-untyped }
}
Invoke-Stage "Unit and regression tests" { python -m pytest -q }
Invoke-Stage "Legacy unittest suite" { cmd.exe /d /c "python -m unittest 2>&1" }
Invoke-Stage "Industry integration tests" { python run_screener.py --industry-test }
Invoke-Stage "Report invariants" { python run_screener.py --report-test }
Invoke-Stage "Sample Daily Watchlist dry run" { python sample_daily_run.py }
Invoke-Stage "Generated HTML and semantic validation" { python scripts/validate_report.py daily_watchlist_dry_run.html daily_watchlist_dry_run.csv daily_watchlist_dry_run_email.txt }
Add-Content -LiteralPath $logPath -Value "`nVerification PASSED: $(Get-Date -Format o)"
Write-Host "Verification PASSED. Log: $logPath"
exit 0
