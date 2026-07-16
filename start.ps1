[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 5173
)

$frontend = Join-Path $PSScriptRoot 'Frontend'

if (-not (Test-Path -LiteralPath $frontend -PathType Container)) {
    throw "找不到前端目录：$frontend"
}

# 检查端口是否已被占用
$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -ne $existing) {
    Write-Host "端口 $Port 已被进程 $($existing.OwningProcess) 占用，请先执行 stop.ps1 或更换端口。"
    return
}

# 新窗口启动 vite，日志实时可见
Start-Process -FilePath 'powershell.exe' `
    -ArgumentList '-NoProfile', '-Command', "Set-Location '$frontend'; pnpm exec vite --host 127.0.0.1 --port $Port" `
    -WindowStyle Normal

Write-Host "前端服务已在新窗口启动：http://127.0.0.1:$Port"
Write-Host "执行 stop.ps1 可停止服务。"