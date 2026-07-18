[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$runtime = Join-Path $PSScriptRoot 'runtime'
$records = @(
    @{ Name = 'backend'; Path = (Join-Path $runtime 'backend.pid') },
    @{ Name = 'frontend'; Path = (Join-Path $runtime 'frontend.pid') }
)

foreach ($entry in $records) {
    if (-not (Test-Path -LiteralPath $entry.Path -PathType Leaf)) {
        Write-Host "$($entry.Name) has no recorded process."
        continue
    }

    try {
        $record = Get-Content -Raw -LiteralPath $entry.Path | ConvertFrom-Json
        $process = Get-Process -Id ([int]$record.Pid) -ErrorAction SilentlyContinue
        if ($null -eq $process) {
            Write-Host "$($entry.Name) process is already stopped."
            continue
        }

        $tickDelta = [Math]::Abs(
            $process.StartTime.ToUniversalTime().Ticks - [long]$record.StartTimeUtcTicks
        )
        $startTimeDelta = [TimeSpan]::FromTicks($tickDelta).TotalSeconds
        if ($startTimeDelta -ge 2) {
            Write-Warning "Skipped $($entry.Name): PID $($record.Pid) belongs to another process."
            continue
        }

        & taskkill.exe /PID $process.Id /T /F | Out-Null
        Write-Host "Stopped $($entry.Name) process $($process.Id)."
    }
    finally {
        Remove-Item -LiteralPath $entry.Path -Force -ErrorAction SilentlyContinue
    }
}
