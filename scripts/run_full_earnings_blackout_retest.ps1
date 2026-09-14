$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

$prices = "research/output/yahoo_engineering/prices.csv"
$benchmark = "research/output/yahoo_engineering/benchmark.csv"
$earnings = "research/output/yahoo_earnings_engineering/earnings.csv"
$earningsMetadata = "research/output/yahoo_earnings_engineering/download_metadata.json"
$outputRoot = "research/output/earnings_blackout_full_retest_v1"

foreach ($required in @($prices, $benchmark, $earnings, $earningsMetadata)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required research input is missing: $required"
    }
}

function Invoke-ResearchRunner {
    param(
        [Parameter(Mandatory = $true)][string]$Module,
        [Parameter(Mandatory = $true)][string]$OutputDirectory,
        [switch]$NeedsBenchmark
    )
    $arguments = @(
        "-m", $Module,
        "--prices", $prices,
        "--earnings", $earnings,
        "--earnings-metadata", $earningsMetadata,
        "--output-dir", $OutputDirectory
    )
    if ($NeedsBenchmark) {
        $arguments += @("--benchmark", $benchmark)
    }
    & python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Module failed with exit code $LASTEXITCODE"
    }
}

Invoke-ResearchRunner -Module "research.run_filter_audit" -OutputDirectory "$outputRoot/filter_audit" -NeedsBenchmark
Invoke-ResearchRunner -Module "research.run_exit_stop_grid" -OutputDirectory "$outputRoot/exit_stop_grid"
Invoke-ResearchRunner -Module "research.run_portfolio_exposure" -OutputDirectory "$outputRoot/portfolio_exposure" -NeedsBenchmark
Invoke-ResearchRunner -Module "research.run_combined_exit_exposure_grid" -OutputDirectory "$outputRoot/combined_exit_exposure_grid" -NeedsBenchmark
Invoke-ResearchRunner -Module "research.run_easy_execution_cross_validation" -OutputDirectory "$outputRoot/easy_execution_cross_validation" -NeedsBenchmark

$gitCommit = (& git rev-parse HEAD).Trim()
$gitDirty = [bool](& git status --porcelain)
$manifest = [ordered]@{
    experiment_id = "EARNINGS_BLACKOUT_FULL_RETEST_V1"
    execution_status = "COMPLETED_ADAPTIVE_ROBUSTNESS_NO_UNTOUCHED_HOLDOUT"
    research_label = "SURVIVORSHIP-AND-EARNINGS-SCHEDULE-BIASED RESEARCH"
    preregistration_commit = "a677f75"
    run_git_commit = $gitCommit
    run_git_dirty = $gitDirty
    production_effect = "NONE"
    blackout_calendar_days = 10
    retrospective_schedule = $true
    retested_configuration_count = 385
    suite_configuration_counts = [ordered]@{
        filter_audit = 8
        exit_stop_grid = 20
        portfolio_exposure = 9
        combined_exit_exposure_grid = 180
        easy_execution_cross_validation = 168
    }
    price_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $prices).Hash.ToLowerInvariant()
    benchmark_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $benchmark).Hash.ToLowerInvariant()
    earnings_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $earnings).Hash.ToLowerInvariant()
    earnings_metadata_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $earningsMetadata).Hash.ToLowerInvariant()
    historical_decision = "HOLD"
    untouched_holdout_evaluated = $false
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath "$outputRoot/run_manifest.json" -Encoding utf8

Write-Host "Completed 385-setting earnings-blackout retest: $outputRoot"
