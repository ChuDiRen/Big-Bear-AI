# Big Bear AI LangGraph Backend Design

Date: 2026-07-17
Status: Architecture approved; written specification awaiting final review

## 1. Objective

Turn the existing Vue prototype into a working local AI testing application. All
visible business controls must have defined behavior, persist their data when
appropriate, and communicate through the LangGraph Agent Server started with
`langgraph dev`.

The implementation must:

- use `deepagents.create_deep_agent` for the user-facing AI assistant;
- expose the assistant and resource-management workflows as LangGraph graphs;
- use LangGraph threads and streaming runs for conversations;
- replace the frontend mock-data dependency with live graph calls;
- persist application resources across `langgraph dev` restarts;
- provide automated unit, integration, and browser-level verification.

## 2. Current State

The Vue application has seven routes: Home, Rules, Agents, Prompt, MCP,
Knowledge, and Plugins. Vue Router navigation works, but all business controls
are visual placeholders. The six catalogue pages read `Frontend/src/data/data.js`
directly. Search boxes, primary action buttons, cards, the Home textarea, send
button, mode selector, and quick actions have no event handlers or API calls.

The repository contains no backend project, API configuration, application
database, frontend HTTP client, or automated tests.

## 3. Approaches Considered

### 3.1 One graph for all behavior

A single graph could branch between chat and CRUD commands. It minimizes graph
count, but mixes conversational state with deterministic resource operations,
makes schemas weak, and makes frontend failures harder to diagnose.

### 3.2 Assistant and management graphs (selected)

Use two graphs with a shared repository:

- `assistant`: a Deep Agent graph for stateful, streaming user conversations;
- `management`: a deterministic graph for resource queries and commands.

This preserves a LangGraph-only service surface while keeping AI behavior and
CRUD behavior independently testable.

### 3.3 LangGraph plus a separate REST service

Use LangGraph only for chat and add FastAPI for CRUD and uploads. This is a
conventional architecture, but adds a second server lifecycle and does not meet
the request to implement the service through the LangGraph API as directly as
the selected approach.

## 4. System Architecture

```text
Vue frontend (127.0.0.1:5173)
  |
  | @langchain/langgraph-sdk / fetch streaming
  v
LangGraph Agent Server (127.0.0.1:2024)
  |-- assistant graph
  |     |-- Deep Agent supervisor
  |     |-- resource and knowledge tools
  |     `-- generic MCP and installed-plugin tools
  |
  `-- management graph
        |-- typed query/command router
        |-- validation and secret redaction
        `-- repository services
              |-- SQLite database (WAL mode)
              `-- managed upload directory
```

A root `langgraph.json` will declare both graphs and the backend dependency.
Running `langgraph dev` from the repository root will start the complete backend
without a second process. Vite will proxy `/api/langgraph` to port 2024 during
development so normal browser requests are same-origin from the frontend's
perspective.

## 5. Project Layout

```text
Backend/
  pyproject.toml
  src/big_bear_ai/
    config.py
    database.py
    models.py
    repositories/
    services/
    graphs/
      assistant.py
      management.py
    tools/
      resources.py
      knowledge.py
      mcp.py
      plugins.py
  tests/
Frontend/
  src/api/
  src/components/
  src/views/
langgraph.json
.env.example
```

Application data is stored under a configurable local data directory. The
default development paths are `runtime/big-bear.db` and `runtime/uploads/`, both
already excluded from Git.

## 6. Runtime Configuration

The backend reads configuration only from environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `BIG_BEAR_MODEL` | `google_genai:gemini-2.5-flash` | LangChain model identifier |
| `BIG_BEAR_DATA_DIR` | `./runtime` | Database and upload root |
| `BIG_BEAR_MAX_UPLOAD_MB` | `10` | Per-document upload limit |
| `BIG_BEAR_MCP_TIMEOUT_SECONDS` | `15` | MCP connect/call timeout |
| `LANGSMITH_TRACING` | `false` | Avoid sending local traces by default |

Model credentials remain provider-native environment variables. The repository
will include `.env.example`, never real secrets. Model construction is isolated
behind a factory so tests use a deterministic fake chat model.

## 7. Graph Contracts

### 7.1 Assistant graph

The assistant graph accepts normal LangGraph message state plus optional context:

```json
{
  "messages": [{"role": "human", "content": "Design API tests"}],
  "context": {
    "mode": "auto",
    "project_id": "optional-id",
    "agent_id": "optional-id"
  }
}
```

The frontend creates a thread with `POST /threads` and starts a streaming run at
`POST /threads/{thread_id}/runs/stream`. It requests `messages-tuple`, `updates`,
and `custom` stream modes with subgraph streaming enabled. The thread ID is kept
in local storage and can be replaced by starting a new conversation.

The exported assistant is a small StateGraph wrapper. Its first node loads the
selected project, Agent profile, enabled Rules, installed Plugins, and available
Knowledge metadata. Its second node invokes a compiled graph returned by
`create_deep_agent`. The wrapper injects the resolved profile as a system message
and exposes only the allowed generic tools, so selecting an Agent changes runtime
behavior without changing the public graph ID or rebuilding the server.

### 7.2 Management graph

The management graph is invoked with threadless runs because each command is
self-contained:

```json
{
  "operation": "list | get | create | update | delete | action",
  "resource": "project | design | rule | prompt | agent | document | mcp | plugin",
  "resource_id": "optional-id",
  "query": {"search": "optional text", "limit": 50, "cursor": null},
  "payload": {}
}
```

Its result has one stable envelope:

```json
{
  "ok": true,
  "data": {},
  "error": null
}
```

Failures use a machine-readable code, a safe user-facing message, and optional
field errors. Secret values are accepted on writes but are never returned.

Supported actions include:

- projects: create, update, delete, list, and open recent designs;
- designs: create, update, delete, list, and attach assistant output;
- rules: CRUD, enable/disable, with seeded official rules read-only;
- prompts: CRUD, render variables, and send a rendered prompt to Home;
- agents: CRUD, choose model/instructions/allowed resources, and launch in Home;
- documents: upload, extract, index, inspect, and delete;
- MCP: CRUD, connect, disconnect, health check, list tools, and invoke tools;
- plugins: list catalogue, install, configure, disable, and uninstall.

## 8. Persistence Model

All application-generated IDs are UUID strings. Timestamps use UTC ISO 8601.
SQLite runs in WAL mode with foreign keys enabled. Schema migrations are
idempotent and run when either graph is first loaded.

Core entities:

- `projects`: name, description, status, timestamps;
- `test_designs`: project ID, title, content, status, source thread/run IDs;
- `rules`: title, description, definition, tags, official/read-only, enabled;
- `prompts`: title, description, template, variables, tags;
- `agent_profiles`: name, description, instructions, model override, allowed IDs;
- `documents`: filename, media type, size, extracted text, index status, path;
- `document_chunks`: document ID, ordinal, text, FTS search data;
- `mcp_servers`: name, transport, public config, environment-variable references,
  desired state, last health status, and last error;
- `plugin_catalogue`: immutable built-in plugin definitions;
- `plugin_installations`: plugin ID, enabled flag, and validated configuration.

The existing frontend mock records become idempotent seed data. Official records
remain read-only; user-created records are editable and deletable.

## 9. Knowledge Behavior

The upload flow accepts `.txt`, `.md`, `.json`, `.csv`, `.pdf`, and `.docx` up to
the configured size limit. The browser sends file bytes as base64 in the
management graph payload because LangGraph runs are JSON inputs. The backend
validates the declared type, filename, decoded size, and content before writing.

Text is extracted, normalized, divided into bounded overlapping chunks, and
indexed with SQLite FTS5. The assistant receives a `search_knowledge` tool that
returns ranked excerpts with document IDs and filenames. Unsupported, empty, or
malformed files fail without leaving database rows or orphan files.

## 10. MCP Behavior and Security

MCP supports `stdio` and `streamable_http` transports. Server records initially
remain disconnected. Connect performs a real handshake and tool discovery; only
a successful handshake yields `Connected`. Disconnect closes active clients and
updates desired state.

The assistant uses generic `list_mcp_tools` and `call_mcp_tool` tools. Each call
revalidates that the server is enabled and applies the timeout. Secret-bearing
environment and header values must use references such as `$env:GITHUB_TOKEN`.
The backend validates and resolves those references only at connection time. It
rejects literal secret values and persists only the variable names, so SQLite,
graph output, logs, and frontend state never contain the secret itself.

The service never treats the seeded mock `Connected` values as evidence of real
connectivity. Seeded MCP examples are disconnected until valid configuration is
provided.

## 11. Plugin Behavior and Security

Version one uses a curated built-in catalogue. Installing a plugin enables a
known backend tool bundle and stores validated configuration. It does not fetch
or execute arbitrary npm packages, Python packages, Git repositories, or URLs.

The initial catalogue provides working local tools corresponding to the current
cards:

- Mock Server: generate deterministic mock API response specifications;
- Data Generator: generate bounded structured test fixtures;
- API Validator: validate JSON data against a JSON Schema;
- Log Analyzer: filter and summarize uploaded/plain-text logs.

The assistant can call only installed and enabled plugin tools. This boundary
keeps the visible install/uninstall workflow functional without introducing a
remote-code-execution feature.

## 12. Frontend Behavior

### Home

- textarea is reactive; Enter sends and Shift+Enter inserts a newline;
- send creates or reuses a thread and renders streamed assistant tokens;
- mode selector offers Auto, Test Design, Analysis, and Execution;
- stop cancels the active run; failures expose retry;
- Start Testing inserts a focused starter request and sends it;
- Open Test Design opens a searchable project/design chooser;
- New Test Project opens a validated create form;
- selecting an Agent, Prompt, or Rule from another page navigates Home with the
  appropriate context.

### Rules, Agents, Prompts, Knowledge, MCP, and Plugins

- initial content is loaded from the management graph;
- search is reactive and debounced;
- loading, empty, validation, and failure states are visible;
- primary buttons open complete forms;
- cards open a detail panel instead of acting as dead visual elements;
- user-owned records can be edited/deleted with confirmation;
- official or catalogue records remain read-only where specified;
- page-specific actions are available from the detail panel.

`UnifiedCard` will emit a click event and will stop injecting server-provided
values with `v-html`. Icons and colors are selected from frontend allowlists.

## 13. Error Handling

- Invalid graph input returns `VALIDATION_ERROR` with field errors.
- Missing records return `NOT_FOUND`.
- Read-only seed mutation returns `READ_ONLY_RESOURCE`.
- File failures return `UNSUPPORTED_FILE`, `FILE_TOO_LARGE`, or
  `EXTRACTION_FAILED`.
- MCP failures return `MCP_CONNECTION_FAILED`, `MCP_TIMEOUT`, or
  `MCP_TOOL_FAILED` without leaking credentials.
- Model failures remain LangGraph run failures; the frontend retains the user's
  message and offers retry.
- Database writes use transactions. Files are written to a temporary path and
  moved only after successful validation and database commit preparation.

## 14. Testing Strategy

Implementation follows red-green-refactor. No production behavior is added
without first observing its targeted test fail.

Backend tests:

- configuration and input validation;
- migration and seed idempotency;
- repository CRUD, search, read-only rules, and transactions;
- document validation, extraction, chunking, FTS search, and cleanup;
- plugin installation and tool permission checks;
- MCP lifecycle using an in-process test MCP server;
- management graph contract for every resource/operation;
- assistant context/tool assembly with a fake chat model.

Frontend tests:

- graph client envelope parsing and stream reduction;
- each page's load, search, form submit, detail, and error states;
- Home thread creation, streaming, cancellation, and retry;
- safe card icon rendering and click emission.

Integration and browser tests:

- start a real `langgraph dev` server and verify both graph schemas;
- create/list/update/delete each writable resource through LangGraph API;
- upload and retrieve a document, then verify assistant knowledge-tool access;
- connect to a test MCP server and invoke a discovered tool;
- install a plugin and invoke its tool;
- run the Vue app and complete the primary workflow on every route;
- verify desktop and mobile layouts have no overlap or clipped controls.

## 15. Acceptance Criteria

The change is complete only when all of the following are demonstrated from a
clean checkout:

1. `langgraph dev` starts from the repository root and exposes `assistant` and
   `management` without import or schema errors.
2. The frontend builds and connects to the local LangGraph server.
3. Home streams a real model response using a persisted LangGraph thread.
4. Every visible search field, primary action button, card, and Home quick
   action has working behavior.
5. Project, design, rule, prompt, Agent, and document changes survive a backend
   restart.
6. Knowledge uploaded through the UI can be retrieved by the assistant.
7. MCP reports Connected only after a real handshake and can execute a test
   tool from the assistant.
8. Installed plugins expose working tools; disabled/uninstalled plugins do not.
9. Secrets are absent from API responses, logs, Git-tracked files, and rendered
   UI state.
10. Backend tests, frontend tests, frontend build, LangGraph API smoke tests, and
    browser end-to-end checks all pass with fresh evidence.

## 16. Explicit Non-Goals

- production authentication, authorization, tenancy, billing, or deployment;
- arbitrary third-party plugin download or code execution;
- production-grade encrypted secret vaulting;
- cloud vector databases or semantic embedding infrastructure;
- production persistence for LangGraph's own thread/run store;
- executing destructive tests against arbitrary user systems without an
  explicit future approval workflow.
