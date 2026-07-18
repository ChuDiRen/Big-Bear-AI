# Big Bear AI

Big Bear AI is a local AI testing workspace. The Vue frontend talks only to a
LangGraph Agent Server, which exports two graphs:

- `assistant`: a streaming Deep Agent created with `deepagents.create_deep_agent`;
- `management`: deterministic resource, knowledge, MCP, and plugin operations.

Application resources persist in `runtime/big-bear.db`. LangGraph's development
thread/run storage remains in-memory by design.

## Requirements

- Python 3.11+
- Node.js 20+ and pnpm
- a provider API key for real assistant responses

## Install

```powershell
python -m venv Backend\.venv
Backend\.venv\Scripts\python.exe -m pip install -e "Backend[dev]"
pnpm --dir Frontend install
Copy-Item .env.example .env
```

Set a valid provider key in `.env`. The default model uses
`GOOGLE_GENERATIVE_AI_API_KEY`; change `BIG_BEAR_MODEL` for another LangChain
model identifier.

## Run

Backend only, using the requested startup command:

```powershell
Backend\.venv\Scripts\langgraph.exe dev --no-browser
```

The graphs are available at `http://127.0.0.1:2024`, with API documentation at
`http://127.0.0.1:2024/docs`.

Complete development stack:

```powershell
.\start.ps1
```

Open `http://127.0.0.1:5173`. The script starts `langgraph dev` and Vite in
hidden processes, waits for both services, and records process ownership under
`runtime/`. Stop only those recorded processes with:

```powershell
.\stop.ps1
```

Custom ports are supported:

```powershell
.\start.ps1 -BackendPort 2025 -FrontendPort 5174
```

## Verify

```powershell
Backend\.venv\Scripts\python.exe -m pytest Backend\tests -q
pnpm --dir Frontend test -- --run
pnpm --dir Frontend build
Backend\.venv\Scripts\python.exe Backend\scripts\smoke_langgraph.py
Backend\.venv\Scripts\python.exe Backend\scripts\smoke_assistant.py
```

## MCP Secrets

MCP environment variables and HTTP headers accept environment references only:

```json
{
  "Authorization": "$env:GITHUB_TOKEN"
}
```

Literal secrets are rejected. Only the variable name is stored and returned.

## Data

- SQLite database: `runtime/big-bear.db`
- uploaded files: `runtime/uploads/`
- local service logs and PID records: `runtime/`

These paths and `.env` are excluded from Git.
