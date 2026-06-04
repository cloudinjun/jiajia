param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateRange(0, 100)]
    [double] $RemainingPercent,

    [Parameter(Position = 1)]
    [string] $ResetAt = "",

    [string] $Plan = "",
    [string] $Source = "manual"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$outputPath = Join-Path $projectRoot "codex_usage_status.json"

function Convert-ResetAt {
    param([string] $Value)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return ""
    }

    $now = [DateTimeOffset]::Now
    $parsed = [DateTimeOffset]::Parse($Value)
    $looksLikeTimeOnly = $Value -notmatch '\d{4}[-/]|\d{1,2}[-/]\d{1,2}'
    if ($looksLikeTimeOnly -and $parsed -le $now) {
        $parsed = $parsed.AddDays(1)
    }
    return $parsed.ToString("o")
}

$data = [ordered]@{
    usage_remaining_percent = [math]::Round($RemainingPercent, 1)
    reset_at = Convert-ResetAt $ResetAt
    plan = $Plan
    source = $Source
    updated_at = [DateTimeOffset]::Now.ToString("o")
    stale = $false
}

$data | ConvertTo-Json | Set-Content -LiteralPath $outputPath -Encoding utf8
Write-Host "Wrote $outputPath"
