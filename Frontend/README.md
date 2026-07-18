# Big Bear AI Frontend

Vue 3 frontend for the Big Bear AI LangGraph service.

```powershell
pnpm install
pnpm dev
pnpm test -- --run
pnpm build
```

During development, Vite proxies `/api/langgraph` to
`http://127.0.0.1:2024`. Set `VITE_LANGGRAPH_PROXY_TARGET` before starting Vite
when the backend uses another port. The browser never receives model or MCP
secret values.
