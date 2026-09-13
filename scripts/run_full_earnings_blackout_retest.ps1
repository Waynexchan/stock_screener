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

Write-Host "Completed 385-setting earnings-blackout retest: $outputRoot"
