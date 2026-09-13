$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$logDir = Join-Path $projectRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir "verify_research.log"
Set-Content -LiteralPath $logPath -Value "Research verification started: $(Get-Date -Format o)"

function Invoke-Stage {
    param([string]$Name, [scriptblock]$Command)
    Write-Host "[$Name]"
    Add-Content -LiteralPath $logPath -Value "`n[$Name]"
    try {
        $previousErrorPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $global:LASTEXITCODE = 0
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

function Get-ProtectedState {
    $fixed = @(
        "config.py",
        "decision_system.py",
        "run_screener.py",
        "ai_analysis.py",
        "send_email.py",
        "scripts\run_daily_production.ps1",
        "daily_watchlist.csv",
        "daily_watchlist.md",
        "daily_watchlist.html",
        "daily_watchlist_last_good.csv",
        "daily_watchlist_last_good.md",
        "daily_watchlist_last_good.html",
        "email_summary.txt",
        "summary_history.csv"
    )
    $files = @()
    foreach ($relative in $fixed) {
        $candidate = Join-Path $projectRoot $relative
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $files += Get-Item -LiteralPath $candidate
        }
    }
    foreach ($relativeDirectory in @("data", "output\forward_snapshots")) {
        $directory = Join-Path $projectRoot $relativeDirectory
        if (Test-Path -LiteralPath $directory) {
            $files += Get-ChildItem -LiteralPath $directory -File -Recurse
        }
    }
    $state = @{}
    $rootPrefix = $projectRoot.TrimEnd("\") + "\"
    foreach ($file in $files | Sort-Object FullName -Unique) {
        if (-not $file.FullName.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "protected file is outside the project root: $($file.FullName)"
        }
        $relative = $file.FullName.Substring($rootPrefix.Length)
        $state[$relative] = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash
    }
    return $state
}

function Assert-ProtectedStateEqual {
    param([hashtable]$Before, [hashtable]$After)
    $beforeKeys = @($Before.Keys | Sort-Object)
    $afterKeys = @($After.Keys | Sort-Object)
    if (($beforeKeys -join "`n") -ne ($afterKeys -join "`n")) {
        throw "research execution added or removed a protected production file"
    }
    foreach ($key in $beforeKeys) {
        if ($Before[$key] -ne $After[$key]) {
            throw "research execution modified protected file: $key"
        }
    }
}

Set-Location $projectRoot
$before = Get-ProtectedState
Invoke-Stage "Research syntax" { python -m compileall -q research }
Invoke-Stage "Research Ruff format check" { python -m ruff format --check research }
Invoke-Stage "Research Ruff lint" { python -m ruff check research }
Invoke-Stage "Research mypy" { python -m mypy research/engine research/run_baseline.py research/run_filter_audit.py research/run_forward_test.py research/run_exit_stop_grid.py research/run_portfolio_exposure.py research/run_combined_exit_exposure_grid.py research/run_easy_execution_cross_validation.py research/run_earnings_exposure_robustness.py research/download_yahoo.py research/download_yahoo_earnings.py --ignore-missing-imports --disable-error-code import-untyped }
Invoke-Stage "Research tests" { python -m pytest -q research/tests }
Invoke-Stage "Gated MODEL_0 baseline" { python -m research.run_baseline --output-dir research/output/baseline }
$after = Get-ProtectedState
Invoke-Stage "Production isolation" { Assert-ProtectedStateEqual -Before $before -After $after }
Add-Content -LiteralPath $logPath -Value "`nResearch verification PASSED: $(Get-Date -Format o)"
Write-Host "Research verification PASSED. Log: $logPath"
exit 0
