# MaestroFlow AIO Sandbox Activation

## What AIO sandbox is

The AIO sandbox is MaestroFlow's isolated execution environment for shell, file, browser, MCP, and editor-style operations. It is not the primary source of thread memory or orchestration state. LangGraph and its persistence layer still provide the main runtime state for conversations and workflows.

## What changes when AIO sandbox is enabled

- Tool execution moves out of direct host execution and into isolated sandbox containers.
- Thread workspaces remain mounted so generated files and edits stay available to MaestroFlow.
- Sandbox-backed features can expose richer file and editor flows than the local sandbox mode.

## Current MaestroFlow defaults

- Primary app URL: `http://localhost:2027`
- Primary startup paths:
  - `make dev` for local frontend/gateway plus Docker-backed LangGraph
  - `make docker-start` for the containerized app flow
- Sandbox activation is controlled by the root `config.yaml`

## Recommended activation flow

1. Confirm Docker is healthy and the daemon is running.
2. Set the sandbox provider in `config.yaml`:

```yaml
sandbox:
  use: src.community.aio_sandbox:AioSandboxProvider
  port: 8080
  auto_start: true
  container_prefix: deer-flow-sandbox
```

3. Pre-pull the sandbox image:

```bash
make setup-sandbox
```

4. Start MaestroFlow:

```bash
make dev
```

Or use:

```bash
make docker-start
```

5. Open MaestroFlow at `http://localhost:2027`
6. Validate at least one sandbox-backed flow:
  - file read/write
  - shell execution
  - artifact generation into the thread workspace

## Rollback

To disable AIO sandbox and return to host execution:

```yaml
sandbox:
  use: src.sandbox.local:LocalSandboxProvider
```

Then restart MaestroFlow.

## Operational notes

- AIO sandbox improves isolation and editor-style workflows, but it does not replace LangGraph persistence.
- If sandbox startup fails, check Docker first before debugging MaestroFlow UI behavior.
- Every new runtime profile should still preserve the primary app entrypoint at `http://localhost:2027`.
