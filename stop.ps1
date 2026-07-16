[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 5173
)

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1

if ($null -eq $listener) {
    Write-Host "端口 $Port 未发现运行中的前端服务。"
    return
}

& taskkill.exe /PID $listener.OwningProcess /T /F | Out-Null
Write-Host "已停止监听端口 $Port 的前端服务，进程 ID：$($listener.OwningProcess)"