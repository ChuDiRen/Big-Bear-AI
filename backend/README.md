# Big Bear AI Backend

The backend is a Python package loaded directly by the root `langgraph.json`.
It exports `assistant` and `management` and requires no separate REST process.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
Set-Location ..
Backend\.venv\Scripts\langgraph.exe dev --no-browser
```

Run tests from the repository root:

```powershell
Backend\.venv\Scripts\python.exe -m pytest Backend\tests -q
```
