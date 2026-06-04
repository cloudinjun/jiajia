param(
    [ValidateSet("idle", "thinking", "reading", "working", "editing", "running", "running_command", "testing", "reconnecting", "disconnected", "waiting_user", "done", "error", "blocked")]
    [string]$Status = "idle",

    [string]$Summary = "",

    [string]$Source = "manual"
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$path = Join-Path $projectRoot "codex_status.json"
$normalizedStatus = if ($Status -eq "running_command") { "running" } else { $Status }
$payload = [ordered]@{
    status = $normalizedStatus
    summary = $Summary
    updated_at = (Get-Date -Format o)
    source = $Source
}

$json = $payload | ConvertTo-Json -Depth 4
$encoding = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($path, $json, $encoding)
Write-Output "codex_status.json -> $normalizedStatus"
