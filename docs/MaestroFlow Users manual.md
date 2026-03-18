# MaestroFlow User's Manual

Welcome to MaestroFlow! This manual will guide you through the core concepts, usage, and advanced features of the MaestroFlow super agent harness.

## Table of Contents
1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Core Concepts](#core-concepts)
4. [Workflows & Features](#workflows--features)
5. [Advanced Usage](#advanced-usage)

---

## Introduction
MaestroFlow is a powerful open-source super agent harness. Forked from Deerflow, MaestroFlow provides an advanced orchestration backend, an executive steering system, and a suite of tools designed for deep research, document editing, and complex task decomposition.

## Getting Started
To get started, you can run MaestroFlow locally via Docker:

```bash
make docker-init
make docker-start
```

Access the application at `http://localhost:2027`.

### Configuration
Edit the `config.yaml` file to configure your preferred models (e.g., OpenAI, Anthropic, or local models) and API keys.

## Core Concepts
- **Sub-Agents:** MaestroFlow decomposes complex tasks by spawning specialized sub-agents. These sub-agents run in parallel where possible and return structured results that are synthesized by the lead agent.
- **Skills:** MaestroFlow's capabilities are defined using Markdown-based skills. These skills outline workflows, best practices, and references for specific tasks.
- **Sandbox:** A secure execution environment for your agents. Tasks run in isolated Docker containers with a full filesystem, ensuring zero contamination between sessions.
- **Executive System:** The control plane for runtime profile management, workflow steering, approvals, and operational actions.
- **Autoresearcher:** A separate optimization lab for running bounded experiments on prompts and workflows. It is manual-start only and uses Executive for approval and rollback.
- **Memory:** Across sessions, MaestroFlow builds a persistent memory of your profile, preferences, and accumulated knowledge.

## Workflows & Features
- **Chats:** The default general-purpose workspace for asking, planning, researching, and executing tasks.
- **Documents:** The primary writing surface for persistent drafts, working notes, and iterative refinement.
- **Revision Lab:** The compare-and-choose writing workspace for heavier multi-version editing sessions.
- **Context Dock:** A shared source/context surface for snippets, scoped knowledge, and active retrieval sources.
- **Activity Feed:** A unified recent-activity surface that replaces scattered recents across chats and editing tools.
- **Editorial Subagents:** Specialized agents including an argument critic and a writing refiner.
- **Calibre Integration:** Seamless knowledge management and retrieval via Calibre backend improvements (HTTP pooling, request caching).
- **SurfSense:** Advanced web search and deep research capabilities. Handoff workflows easily handle deep research queries.
- **Executive:** Service health, approvals, routing overrides, project management, and operational workflows.
- **Autoresearcher:** Prompt experiments with benchmark metadata, candidate tracking, and Executive-gated promotion into the live prompt registry.
- **UI Design Optimization:** A manual Autoresearcher workflow that renders a component, critiques it against a visual rubric, mutates it, and stores the best candidate with screenshots.

### How Executive and Autoresearcher differ

- **Executive** is for control-plane work: approvals, runtime steering, status, and rollback.
- **Autoresearcher** is for lab work: creating and inspecting experiments, candidates, and benchmarks.
- Autoresearcher does **not** start automatically on page load or in the background by default.
- A winning experiment still requires explicit approval before it changes live defaults.

## Advanced Usage
### MCP Server Integration
MaestroFlow supports configurable MCP servers and skills to extend its capabilities. HTTP/SSE MCP servers with OAuth token flows (`client_credentials`, `refresh_token`) are fully supported.

### Plan Mode
For complex, multi-step tasks, you can use the built-in planning and steering systems to generate a plan and get a sophisticated planning review before executing.

### Autoresearcher experiments

Autoresearcher is intentionally conservative:

1. Open the **Autoresearcher** workspace.
2. Start an experiment explicitly for a supported role or launch a `ui_design` experiment with a component snippet.
3. Review candidate scores, screenshots, and benchmark coverage in the lab.
4. Use **Executive** to approve, reject, stop, or roll back prompt changes when the experiment affects live defaults.

This keeps optimization work separate from normal chats, documents, and runtime operations.

### Sandbox Execution Modes
MaestroFlow supports multiple execution modes for sandboxing your tasks:
- **Local Execution:** Runs code directly on the host machine.
- **Docker Execution:** Runs code in isolated Docker containers (recommended).
- **Docker Execution with Kubernetes:** Runs code in Kubernetes pods via a provisioner service.

### Embedded Python Client
MaestroFlow can also be embedded directly in Python applications:
```python
from src.client import MaestroFlowClient

client = MaestroFlowClient()
response = client.chat("Analyze this paper for me", thread_id="my-thread")
```

For more detailed technical documentation and references, please see the `backend/docs/` directory or the architecture specifications in the `docs` folder.
