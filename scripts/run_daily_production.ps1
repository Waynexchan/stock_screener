param([switch]$MutexProbe)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

if ($MutexProbe -and $env:SCREENER_MUTEX_PROBE -ne "1") {
    Write-Output "Mutex probe requires SCREENER_MUTEX_PROBE=1."
    exit 64
}

$hashAlgorithm = [System.Security.Cryptography.SHA256]::Create()
try {
    $rootBytes = [System.Text.Encoding]::UTF8.GetBytes($projectRoot.ToLowerInvariant())
    $rootHash = [System.BitConverter]::ToString($hashAlgorithm.ComputeHash($rootBytes)).Replace("-", "").Substring(0, 20)
} finally {
    $hashAlgorithm.Dispose()
}
$mutexName = "Global\StockScreenerProduction_$rootHash"
$createdNew = $false
$productionMutex = [System.Threading.Mutex]::new($true, $mutexName, [ref]$createdNew)
if (-not $createdNew) {
    $productionMutex.Dispose()
    Write-Output "Production run already active; lock contention exit 75."
    exit 75
}

if ($MutexProbe) {
    try {
        Write-Output "MUTEX_PROBE_ACQUIRED"
        Start-Sleep -Seconds 2
    } finally {
        $productionMutex.ReleaseMutex()
        $productionMutex.Dispose()
    }
    exit 0
}

$finalExitCode = 1
try {
    $runId = (Get-Date -Format "yyyyMMddTHHmmssfff") + "-" + [guid]::NewGuid().ToString("N").Substring(0, 8)
    $logDirectory = Join-Path $projectRoot "logs\production_runs"
    $runLog = Join-Path $logDirectory ("production_" + $runId + ".log")
    $compatibilityLog = Join-Path $projectRoot "logs\production.log"
    $relativeRunLog = "logs/production_runs/" + [System.IO.Path]::GetFileName($runLog)
    $currentStage = "initialization"
    $failureHandled = $false
    $recentOutput = [System.Collections.Generic.Queue[string]]::new()
    $maxFailureSummaryLength = 1000

    function Write-ProductionLog {
        param([string]$Message)
        $line = "$(Get-Date -Format o) $Message"
        Write-Host $line
        try {
            Add-Content -LiteralPath $runLog -Value $line -Encoding utf8
        } catch {
            Write-Warning "Could not append the per-run production log: $($_.Exception.Message)"
        }
        try {
            Add-Content -LiteralPath $compatibilityLog -Value $line -Encoding utf8
        } catch {
            Write-Warning "Could not append the compatibility production log: $($_.Exception.Message)"
        }
    }

    function Write-CommandOutput {
        process {
            $line = [string]$_
            Write-Host $line
            try {
                Add-Content -LiteralPath $runLog -Value $line -Encoding utf8
            } catch {
                Write-Warning "Could not append command output to the per-run log: $($_.Exception.Message)"
            }
            try {
                Add-Content -LiteralPath $compatibilityLog -Value $line -Encoding utf8
            } catch {
                Write-Warning "Could not append command output to the compatibility log: $($_.Exception.Message)"
            }
            $script:recentOutput.Enqueue($line)
            while ($script:recentOutput.Count -gt 12) {
                $script:recentOutput.Dequeue() | Out-Null
            }
        }
    }

    function Get-RecentFailureSummary {
        param([string]$Fallback)
        if ($script:recentOutput.Count -eq 0) {
            return $Fallback
        }
        return (($script:recentOutput.ToArray() | Select-Object -Last 8) -join " | ")
    }

    function ConvertTo-BoundedFailureSummary {
        param([string]$Summary)
        $normalized = (($Summary -replace "`0", "") -replace "\s+", " ").Trim()
        if ([string]::IsNullOrWhiteSpace($normalized)) {
            return "No error summary was available."
        }
        if ($normalized.Length -gt $script:maxFailureSummaryLength) {
            return $normalized.Substring(0, $script:maxFailureSummaryLength)
        }
        return $normalized
    }

    function Invoke-Monitor {
        param([string[]]$Arguments)
        & python production_monitor.py @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "production monitor exited with code $LASTEXITCODE"
        }
    }

    function Register-ProductionFailure {
        param(
            [string]$Stage,
            [int]$ExitCode,
            [string]$Summary
        )
        if ($script:failureHandled) {
            return
        }
        $script:failureHandled = $true
        $safeExitCode = if ($ExitCode -eq 0) { 1 } else { $ExitCode }
        $boundedSummary = ConvertTo-BoundedFailureSummary $Summary
        Write-ProductionLog "FAILED stage=$Stage exit_code=$safeExitCode summary=$boundedSummary"
        $previousPreference = $ErrorActionPreference
        $summaryFile = $null
        $monitorExitCode = 1
        try {
            $summaryFile = [System.IO.Path]::GetTempFileName()
            [System.IO.File]::WriteAllText($summaryFile, $boundedSummary, [System.Text.UTF8Encoding]::new($false))
            $ErrorActionPreference = "Continue"
            & python production_monitor.py fail --run-id $runId --stage $Stage --exit-code $safeExitCode --summary-file $summaryFile --notify 2>&1 | Write-CommandOutput
            $monitorExitCode = $LASTEXITCODE
        } catch {
            Write-ProductionLog "Failure monitor launch failed: $($_.Exception.Message)"
        } finally {
            $ErrorActionPreference = $previousPreference
            if ($null -ne $summaryFile) {
                Remove-Item -LiteralPath $summaryFile -Force -ErrorAction SilentlyContinue
            }
        }
        if ($monitorExitCode -ne 0) {
            $fallback = @{
                schema_version = 1
                run_id = $runId
                state = "FAILED"
                stage = $Stage
                started_at = $null
                completed_at = (Get-Date).ToUniversalTime().ToString("o")
                exit_code = $safeExitCode
                error_summary = $boundedSummary
                log_path = $relativeRunLog
            } | ConvertTo-Json
            Set-Content -LiteralPath (Join-Path $projectRoot "logs\production_status.json") -Value $fallback -Encoding utf8
            Set-Content -LiteralPath (Join-Path $projectRoot "data_failure_report.txt") -Value "FAILED: $Stage - $boundedSummary. See $relativeRunLog." -Encoding utf8
            Write-ProductionLog "Failure monitor also failed with exit code $monitorExitCode. Fallback status written."
        }
    }

    function Invoke-ProductionWorkflow {
        try {
            New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
            Set-Content -LiteralPath $runLog -Value "Production run log (UTF-8): $runId" -Encoding utf8
            Set-Content -LiteralPath $compatibilityLog -Value "Latest production run: $relativeRunLog" -Encoding utf8
            Invoke-Monitor @("start", "--run-id", $runId, "--log-path", $relativeRunLog)
            Write-ProductionLog "Production started."

            $script:currentStage = "verification"
            Invoke-Monitor @("stage", "--run-id", $runId, "--stage", $currentStage)
            $recentOutput.Clear()
            $previousPreference = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            & powershell -ExecutionPolicy Bypass -File .\scripts\verify_project.ps1 2>&1 | Write-CommandOutput
            $verificationExitCode = $LASTEXITCODE
            $ErrorActionPreference = $previousPreference
            if ($verificationExitCode -ne 0) {
                $summary = Get-RecentFailureSummary "Project verification did not pass; normal watchlist and email were blocked."
                Register-ProductionFailure $currentStage $verificationExitCode $summary
                return $verificationExitCode
            }

            $env:SCREENER_VERIFIED = "1"
            $env:PRODUCTION_RUN_ID = $runId
            $script:currentStage = "python"
            Invoke-Monitor @("stage", "--run-id", $runId, "--stage", $currentStage)
            $recentOutput.Clear()
            $previousPreference = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            & python run_screener.py 2>&1 | Write-CommandOutput
            $productionExitCode = $LASTEXITCODE
            $ErrorActionPreference = $previousPreference
            if ($productionExitCode -ne 0) {
                $summary = Get-RecentFailureSummary "Python production orchestration exited unsuccessfully."
                Register-ProductionFailure $currentStage $productionExitCode $summary
                return $productionExitCode
            }

            Invoke-Monitor @("success", "--run-id", $runId)
            Write-ProductionLog "Production completed successfully with exit code 0."
            return 0
        } catch {
            $summary = $_.Exception.Message
            Register-ProductionFailure $currentStage 1 $summary
            return 1
        }
    }

    $finalExitCode = Invoke-ProductionWorkflow
} finally {
    $productionMutex.ReleaseMutex()
    $productionMutex.Dispose()
}
exit $finalExitCode
