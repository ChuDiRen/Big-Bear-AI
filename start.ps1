[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$FrontendPort = 5173,

    [ValidateRange(1, 65535)]
    [int]$BackendPort = 2024
)

$ErrorActionPreference = 'Stop'
$runtime = Join-Path $PSScriptRoot 'runtime'
$frontend = Join-Path $PSScriptRoot 'Frontend'
$langGraphRuntime = Join-Path $PSScriptRoot '.langgraph_api'
$backendPidFile = Join-Path $runtime 'backend.pid'
$frontendPidFile = Join-Path $runtime 'frontend.pid'
$langGraphConfig = Join-Path $PSScriptRoot 'langgraph.json'

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

function Reset-LangGraphRuntime() {
    if (-not (Test-Path -LiteralPath $langGraphRuntime)) {
        return
    }
    $rootPath = [System.IO.Path]::GetFullPath($PSScriptRoot)
    $runtimePath = [System.IO.Path]::GetFullPath($langGraphRuntime)
    if (-not $runtimePath.StartsWith($rootPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove LangGraph runtime outside workspace: $runtimePath"
    }
    Remove-Item -LiteralPath $langGraphRuntime -Recurse -Force
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
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
Stop-OwnedProcess $frontendPidFile
Stop-OwnedProcess $backendPidFile
Reset-LangGraphRuntime
New-Item -ItemType Directory -Path $langGraphRuntime -Force | Out-Null
Assert-PortFree $BackendPort
Assert-PortFree $FrontendPort

$venvLangGraph = Join-Path $PSScriptRoot 'Backend\.venv\Scripts\langgraph.exe'
$backendFile = if (Test-Path -LiteralPath $venvLangGraph -PathType Leaf) { $venvLangGraph } else { 'langgraph' }
if ($backendFile -eq 'langgraph') {
    Assert-Command 'langgraph'
}

try {
    $backend = Start-Process -FilePath $backendFile `
        -WorkingDirectory $PSScriptRoot `
        -ArgumentList @('dev', '--no-browser', '--host', '127.0.0.1', '--port', $BackendPort, '--config', $langGraphConfig) `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtime 'backend.out.log') `
        -RedirectStandardError (Join-Path $runtime 'backend.err.log')
    Save-ProcessRecord $backend $backendPidFile
    Wait-Endpoint "http://127.0.0.1:$BackendPort/docs"

    $env:VITE_LANGGRAPH_PROXY_TARGET = "http://127.0.0.1:$BackendPort"
    $frontendProcess = Start-Process -FilePath 'pnpm' `
        -WorkingDirectory $frontend `
        -ArgumentList @('exec', 'vite', '--host', '127.0.0.1', '--port', $FrontendPort) `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtime 'frontend.out.log') `
        -RedirectStandardError (Join-Path $runtime 'frontend.err.log')
    Save-ProcessRecord $frontendProcess $frontendPidFile
    Wait-Endpoint "http://127.0.0.1:$FrontendPort/"
}
catch {
    Stop-OwnedProcess $frontendPidFile
    Stop-OwnedProcess $backendPidFile
    throw
}

Write-Host "Big Bear AI is ready: http://127.0.0.1:$FrontendPort"
Write-Host "LangGraph API docs: http://127.0.0.1:$BackendPort/docs"
Write-Host "Run .\stop.ps1 to stop both processes."
