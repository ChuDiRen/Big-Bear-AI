[CmdletBinding()]
param(
    [ValidateSet('inmem', 'postgres')]
    [string]$Runtime = 'inmem',

    [ValidateRange(1, 65535)]
    [int]$FrontendPort = 5173,

    [ValidateRange(1, 65535)]
    [int]$BackendPort = 2026
)

$ErrorActionPreference = 'Stop'
$runtimeDir = Join-Path $PSScriptRoot 'runtime'
$frontend = Join-Path $PSScriptRoot 'Frontend'
$backendPidFile = Join-Path $runtimeDir 'backend.pid'
$frontendPidFile = Join-Path $runtimeDir 'frontend.pid'
$backendLauncherName = if ($Runtime -eq 'postgres') { 'start_postgres.py' } else { 'start__inmem.py' }
$backendLauncher = Join-Path $PSScriptRoot $backendLauncherName
$backendPython = Join-Path $PSScriptRoot 'backend\.venv\Scripts\python.exe'

function Assert-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command is not available: $Name"
    }
}

function Assert-PortFree([int]$Port) {
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -ne $listener) {
        throw "Port $Port is already in use by process $($listener.OwningProcess)."
    }
}

function Save-ProcessRecord([System.Diagnostics.Process]$Process, [string]$Path) {
    @{
        Pid = $Process.Id
        StartTimeUtcTicks = $Process.StartTime.ToUniversalTime().Ticks
    } | ConvertTo-Json -Compress | Set-Content -LiteralPath $Path -Encoding utf8
}

function Stop-OwnedProcess([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return
    }
    try {
        $record = Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json
        $process = Get-Process -Id ([int]$record.Pid) -ErrorAction SilentlyContinue
        if ($null -ne $process) {
            $tickDelta = [Math]::Abs(
                $process.StartTime.ToUniversalTime().Ticks - [long]$record.StartTimeUtcTicks
            )
            $delta = [TimeSpan]::FromTicks($tickDelta).TotalSeconds
            if ($delta -lt 2) {
                & taskkill.exe /PID $process.Id /T /F | Out-Null
            }
        }
    }
    finally {
        Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    }
}

function Wait-Endpoint([string]$Url, [int]$TimeoutSeconds = 45) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 250
        }
    } while ((Get-Date) -lt $deadline)
    throw "Timed out waiting for $Url"
}

Assert-Command 'pnpm'
if (-not (Test-Path -LiteralPath $backendPython -PathType Leaf)) {
    throw "Backend virtual environment Python was not found: $backendPython"
}
if (-not (Test-Path -LiteralPath $backendLauncher -PathType Leaf)) {
    throw "Backend launcher was not found: $backendLauncher"
}

New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
Stop-OwnedProcess $frontendPidFile
Stop-OwnedProcess $backendPidFile
Assert-PortFree $BackendPort
Assert-PortFree $FrontendPort

try {
    $env:BIG_BEAR_SERVER_PORT = "$BackendPort"
    $backend = Start-Process -FilePath $backendPython `
        -WorkingDirectory $PSScriptRoot `
        -ArgumentList @($backendLauncher) `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtimeDir 'backend.out.log') `
        -RedirectStandardError (Join-Path $runtimeDir 'backend.err.log')
    Save-ProcessRecord $backend $backendPidFile
    Wait-Endpoint "http://127.0.0.1:$BackendPort/docs"

    $env:VITE_LANGGRAPH_PROXY_TARGET = "http://127.0.0.1:$BackendPort"
    $frontendProcess = Start-Process -FilePath 'pnpm.cmd' `
        -WorkingDirectory $frontend `
        -ArgumentList @('exec', 'vite', '--host', '127.0.0.1', '--port', $FrontendPort) `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtimeDir 'frontend.out.log') `
        -RedirectStandardError (Join-Path $runtimeDir 'frontend.err.log')
    Save-ProcessRecord $frontendProcess $frontendPidFile
    Wait-Endpoint "http://127.0.0.1:$FrontendPort/"
}
catch {
    Stop-OwnedProcess $frontendPidFile
    Stop-OwnedProcess $backendPidFile
    throw
}

Write-Host "Big Bear AI ($Runtime) is ready: http://127.0.0.1:$FrontendPort"
Write-Host "LangGraph API docs: http://127.0.0.1:$BackendPort/docs"
Write-Host "Run .\stop.ps1 to stop both processes."
