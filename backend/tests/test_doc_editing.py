import asyncio
from pathlib import Path

from src.doc_editing.nodes.collector import collector
from src.doc_editing.nodes.dispatcher import dispatch_skills
from src.doc_editing.nodes.skill_agent import _sanitize_skill_output
from src.doc_editing.nodes.finalizer import _resolve_final_path
from src.doc_editing.run_tracker import get_run, list_runs, persist_run
from src.gateway.routers import doc_editing


def test_dispatch_skills_trims_to_budget():
    document = "word " * 160
    state = {
        "document": document,
        "skills": ["writing-refiner", "argument-critic", "humanizer"],
        "model_location": "mixed",
        "model_strength": "fast",
        "preferred_model": None,
        "token_budget": 920,
        "run_id": "run12345",
        "run_dir": "/tmp/doc-edit-test",
        "versions": [],
    }

    sends = dispatch_skills(state)

    assert len(sends) == 2
    assert [send.arg["current_skill"] for send in sends] == ["writing-refiner", "argument-critic"]


def test_dispatch_skills_deduplicates_requested_skills():
    state = {
        "document": "word " * 20,
        "skills": ["writing-refiner", "writing-refiner", "argument-critic"],
        "model_location": "mixed",
        "model_strength": "fast",
        "preferred_model": None,
        "token_budget": 4000,
        "run_id": "run12345",
        "run_dir": "/tmp/doc-edit-test",
        "versions": [],
    }

    sends = dispatch_skills(state)

    assert [send.arg["current_skill"] for send in sends] == ["writing-refiner", "argument-critic"]


def test_dispatch_skills_crosses_selected_models():
    state = {
        "document": "word " * 20,
        "skills": ["writing-refiner", "argument-critic"],
        "model_location": "mixed",
        "model_strength": "fast",
        "preferred_model": None,
        "selected_models": [("gemini-2-5-flash", "gemini"), ("gpt-5-2-codex", "gpt-5.2-mini")],
        "token_budget": 4000,
        "run_id": "run12345",
        "run_dir": "/tmp/doc-edit-test",
        "versions": [],
    }

    sends = dispatch_skills(state)

    assert len(sends) == 4
    assert sends[0].arg["current_model_name"] == "gemini-2-5-flash"
    assert sends[-1].arg["current_model_name"] == "gpt-5-2-codex"


def test_collector_writes_report_and_selects_top_version(tmp_path: Path):
    run_dir = tmp_path / "run-1"
    state = {
        "document": "Example document",
        "skills": ["writing-refiner", "argument-critic"],
        "model_location": "mixed",
        "model_strength": "fast",
        "preferred_model": None,
        "token_budget": 4000,
        "run_id": "run-1",
        "run_dir": str(run_dir),
        "versions": [
            {
                "version_id": "writing-refiner-gemini-2-5-flash",
                "skill_name": "writing-refiner",
                "subagent_type": "writing-refiner",
                "requested_model": None,
                "output": "edited a",
                "score": 0.62,
                "quality_dims": {"completeness": 0.8, "error_rate": 0.0},
                "token_count": 120,
                "latency_ms": 10,
                "file_path": str(run_dir / "01-writing-refiner.md"),
                "model_name": "gemini-2-5-flash",
            },
            {
                "version_id": "argument-critic-gemini-2-5-flash",
                "skill_name": "argument-critic",
                "subagent_type": "argument-critic",
                "requested_model": None,
                "output": "edited b",
                "score": 0.91,
                "quality_dims": {"completeness": 0.9, "error_rate": 0.0},
                "token_count": 140,
                "latency_ms": 12,
                "file_path": str(run_dir / "02-argument-critic.md"),
                "model_name": "gemini-2-5-flash",
            },
        ],
    }

    result = collector(state)

    assert result["ranked_versions"][0]["skill_name"] == "argument-critic"
    assert result["tokens_used"] == 260
    assert (run_dir / "run-report.md").exists()
    assert (run_dir / "versions.json").exists()
    assert (run_dir / "run.json").exists()


def test_persist_run_round_trip(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "doc_runs.db"
    monkeypatch.setenv("DOC_EDIT_RUNS_DB_PATH", str(db_path))

    state = {
        "document": "Example document for persistence",
        "skills": ["writing-refiner"],
        "model_location": "mixed",
        "model_strength": "fast",
        "preferred_model": None,
        "token_budget": 4000,
        "run_id": "persist01",
        "run_dir": str(tmp_path / "persist01"),
        "versions": [
            {
                "version_id": "writing-refiner-gemini-2-5-flash",
                "skill_name": "writing-refiner",
                "subagent_type": "writing-refiner",
                "requested_model": None,
                "output": "edited",
                "score": 0.88,
                "quality_dims": {"completeness": 0.9, "error_rate": 0.0},
                "token_count": 100,
                "latency_ms": 25,
                "file_path": str(tmp_path / "persist01" / "01-writing-refiner.md"),
                "model_name": "gemini-2-5-flash",
            }
        ],
        "ranked_versions": [
            {
                "version_id": "writing-refiner-gemini-2-5-flash",
                "skill_name": "writing-refiner",
                "subagent_type": "writing-refiner",
                "requested_model": None,
                "output": "edited",
                "score": 0.88,
                "quality_dims": {"completeness": 0.9, "error_rate": 0.0},
                "token_count": 100,
                "latency_ms": 25,
                "file_path": str(tmp_path / "persist01" / "01-writing-refiner.md"),
                "model_name": "gemini-2-5-flash",
            }
        ],
        "tokens_used": 100,
    }

    winner = state["ranked_versions"][0]
    persist_run(state, winner, "/tmp/final.md")
    loaded = get_run("persist01")

    assert loaded["selected_skill"] == "writing-refiner"
    assert loaded["final_path"] == "/tmp/final.md"
    assert loaded["document"] == "Example document for persistence"
    assert loaded["title"].startswith("Example document")
    assert loaded["versions"][0]["score"] == 0.88


def test_list_runs_includes_human_readable_title(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "doc_runs.db"
    monkeypatch.setenv("DOC_EDIT_RUNS_DB_PATH", str(db_path))
    monkeypatch.setenv("DOC_EDIT_DOCS_DIR", str(tmp_path / "docs"))

    state = {
        "document": "A useful title for the run list view",
        "skills": ["writing-refiner"],
        "model_location": "mixed",
        "model_strength": "fast",
        "preferred_model": None,
        "token_budget": 4000,
        "run_id": "list01",
        "run_dir": str(tmp_path / "list01"),
        "versions": [
            {
                "version_id": "writing-refiner-gemini-2-5-flash",
                "skill_name": "writing-refiner",
                "subagent_type": "writing-refiner",
                "requested_model": None,
                "output": "edited",
                "score": 0.88,
                "quality_dims": {"completeness": 0.9, "error_rate": 0.0},
                "token_count": 100,
                "latency_ms": 25,
                "file_path": str(tmp_path / "list01" / "01-writing-refiner.md"),
                "model_name": "gemini-2-5-flash",
            }
        ],
        "ranked_versions": [
            {
                "version_id": "writing-refiner-gemini-2-5-flash",
                "skill_name": "writing-refiner",
                "subagent_type": "writing-refiner",
                "requested_model": None,
                "output": "edited",
                "score": 0.88,
                "quality_dims": {"completeness": 0.9, "error_rate": 0.0},
                "token_count": 100,
                "latency_ms": 25,
                "file_path": str(tmp_path / "list01" / "01-writing-refiner.md"),
                "model_name": "gemini-2-5-flash",
            }
        ],
        "tokens_used": 100,
    }

    persist_run(state, state["ranked_versions"][0], "/tmp/final.md")
    listing = list_runs()

    assert listing["runs"][0]["run_id"] == "list01"
    assert listing["runs"][0]["title"] == "A useful title for the run list view"


def test_resolve_final_path_avoids_collisions(tmp_path: Path):
    base = tmp_path / "report.md"
    base.write_text("first", encoding="utf-8")

    resolved = _resolve_final_path(base)

    assert resolved == tmp_path / "report-2.md"


def test_sanitize_skill_output_prefers_revised_text_section():
    raw = """
## Summary
The text is more direct.

## Revised Text
# Async Python

Use async only when it genuinely helps.

## Notes
- Removed filler.
""".strip()

    assert _sanitize_skill_output(raw) == "# Async Python\n\nUse async only when it genuinely helps."


def test_sanitize_skill_output_drops_summary_and_notes_labels():
    raw = """
Summary: tightened the prose.

# Async Python

Notes: removed repetition.
""".strip()

    assert _sanitize_skill_output(raw) == "tightened the prose.\n\n# Async Python"


def test_start_doc_edit_returns_graph_result(monkeypatch, tmp_path: Path):
    captured = {}

    class FakeGraph:
        async def ainvoke(self, state, config=None):
            captured["state"] = state
            return {
                **state,
                "title": "Hello world",
                "tokens_used": 321,
                "final_path": str(tmp_path / "final.md"),
                "selected_version": {"skill_name": "writing-refiner"},
                "versions": [{"skill_name": "writing-refiner", "score": 0.8}],
            }

    async def fake_get_graph():
        return FakeGraph()

    monkeypatch.setattr(doc_editing, "get_doc_edit_graph", fake_get_graph)
    monkeypatch.setattr(doc_editing, "ensure_run_dir", lambda run_id: tmp_path / run_id)

    response = asyncio.run(
        doc_editing.start_doc_edit(
            doc_editing.DocEditRequest(
                document="Hello world",
                skills=["writing-refiner"],
                model_location="remote",
                model_strength="cheap",
                preferred_model="gpt-5.2-mini",
            )
        )
    )

    assert response.selected_skill == "writing-refiner"
    assert response.title == "Hello world"
    assert response.status == "completed"
    assert response.token_count == 321
    assert response.versions[0]["skill_name"] == "writing-refiner"
    assert captured["state"]["model_location"] == "remote"
    assert captured["state"]["model_strength"] == "cheap"
    assert captured["state"]["preferred_model"] == "gpt-5.2-mini"


def test_start_doc_edit_returns_pending_selection(monkeypatch, tmp_path: Path):
    class FakeGraph:
        async def ainvoke(self, state, config=None):
            return {"__interrupt__": [{"value": "pause"}]}

    async def fake_get_graph():
        return FakeGraph()

    monkeypatch.setattr(doc_editing, "get_doc_edit_graph", fake_get_graph)
    monkeypatch.setattr(doc_editing, "ensure_run_dir", lambda run_id: tmp_path / run_id)
    monkeypatch.setattr(
        doc_editing,
        "get_run",
        lambda run_id: {
            "versions": [{"skill_name": "argument-critic", "score": 0.91}],
            "title": "Pending run",
            "tokens_used": 222,
            "review_payload": {"instruction": "pick one"},
            "final_path": None,
            "selected_version": None,
        },
    )

    response = asyncio.run(
        doc_editing.start_doc_edit(
            doc_editing.DocEditRequest(document="Hello world", skills=["writing-refiner"])
        )
    )

    assert response.status == "awaiting_selection"
    assert response.title == "Pending run"
    assert response.review_payload == {"instruction": "pick one"}
    assert response.versions[0]["skill_name"] == "argument-critic"


def test_select_doc_run_version_resumes_graph(monkeypatch, tmp_path: Path):
    captured = {}

    class FakeGraph:
        async def ainvoke(self, command, config=None):
            captured["command"] = command
            captured["config"] = config
            return {
                "tokens_used": 111,
                "title": "Resume run",
                "final_path": str(tmp_path / "final.md"),
                "selected_version": {"skill_name": "writing-refiner"},
                "ranked_versions": [{"skill_name": "writing-refiner", "score": 0.8}],
            }

    async def fake_get_graph():
        return FakeGraph()

    monkeypatch.setattr(doc_editing, "get_doc_edit_graph", fake_get_graph)
    monkeypatch.setattr(doc_editing, "ensure_run_dir", lambda run_id: tmp_path / run_id)

    response = asyncio.run(doc_editing.select_doc_run_version("run42", "writing-refiner"))

    assert response.status == "completed"
    assert response.title == "Resume run"
    assert response.selected_skill == "writing-refiner"
    assert captured["config"] == {"configurable": {"thread_id": "run42"}}
