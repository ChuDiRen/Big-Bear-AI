# Big Bear AI

## 安装

```powershell
uv sync
```

## 前后端联调

统一入口会启动 LangGraph 后端与 Vite 前端。前端始终通过同源路径 `/api/langgraph` 请求后端，启动脚本会将当前后端端口注入 Vite 代理。

```powershell
# 内存运行时，默认模式
.\start.ps1
.\start.ps1 -Runtime inmem

# PostgreSQL 持久化运行时
.\start.ps1 -Runtime postgres
```

默认地址为前端 `http://127.0.0.1:5173`、后端文档 `http://127.0.0.1:2026/docs`。两个运行时互斥运行；可通过 `-FrontendPort` 与 `-BackendPort` 同时指定其他端口。

```powershell
.\start.ps1 -Runtime postgres -FrontendPort 5174 -BackendPort 2027
.\stop.ps1
```

## 认证

认证已集成到 LangGraph 后端。后端提供：

- `POST /auth/register`：创建账户。
- `POST /auth/login`：登录并返回 Bearer JWT。
- 所有 LangGraph 资源接口要求 `Authorization: Bearer <token>`，并按账户隔离资源。

存储策略随运行时切换：`inmem` 使用独立的 `runtime/auth.db`；`postgres` 使用当前 PostgreSQL 数据库中的 `users` 表。JWT 配置使用本地 `.env` 中的 `AUTH_DEV_SECRET` 与可选 `AUTH_AUDIENCE`。

## PostgreSQL 运行时

- `storage/migrations/` 是 LangGraph PostgreSQL 运行时的建表与升级脚本，必须保留。
- `openapi.json` 是 API 描述文件，必须与运行时文件一同保留。
- 在 `langgraph.json` 的 `graphs` 中配置可用智能体。

启动持久化服务前，请在当前终端设置连接串。不要将真实密钥、密码或连接地址提交到仓库。

```powershell
$env:BIG_BEAR_POSTGRES_URI = "postgresql://<用户>:<密码>@<主机>:5432/<数据库>"
$env:BIG_BEAR_REDIS_URI = "redis://:<密码>@<主机>:6379/0"
.\start.ps1 -Runtime postgres
```

未设置 `BIG_BEAR_POSTGRES_URI` / `BIG_BEAR_REDIS_URI` 时，启动器会读取本地 `.env` 中的 `DATABASE_URI` 与 `REDIS_URI`。
