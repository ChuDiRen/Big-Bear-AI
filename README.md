# Big Bear AI

## 安装

```powershell
uv sync
```

## PostgreSQL 运行时

- `storage/migrations/` 是 LangGraph PostgreSQL 运行时的建表与升级脚本，必须保留。
- `openapi.json` 是 API 描述文件，必须与运行时文件一同保留。
- 在 `langgraph.json` 的 `graphs` 中配置可用智能体。

启动持久化服务前，请在当前终端设置连接串。不要将真实密钥、密码或连接地址提交到仓库。

```powershell
$env:BIG_BEAR_POSTGRES_URI = "postgresql://<用户>:<密码>@<主机>:5432/<数据库>"
$env:BIG_BEAR_REDIS_URI = "redis://:<密码>@<主机>:6379/0"
python .\start_postgres.py
```

未设置环境变量时，启动器会使用本机开发默认值：PostgreSQL `postgresql://postgres@127.0.0.1:5432/big_bear_ai` 与 Redis `redis://127.0.0.1:6379/0`。

## 独立认证服务

根目录 `src/app/main.py` 是独立的注册与登录 API，可按需单独运行：

```powershell
python .\src\app\main.py
```
