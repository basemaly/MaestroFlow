from datetime import datetime
from uuid import uuid4

from src.langgraph.storage_migration import (
    CatalogSummary,
    CheckpointSummary,
    build_migration_report,
    normalize_for_json,
    summarize_catalog,
)


def test_summarize_catalog_collects_counts_and_thread_ids():
    thread_id = uuid4()
    catalog = {
        "threads": [
            {"thread_id": thread_id},
            {"thread_id": "thread-2"},
        ],
        "runs": [1, 2, 3],
        "assistants": [1],
        "assistant_versions": [1, 2],
        "crons": [],
    }

    summary = summarize_catalog(catalog)

    assert summary.threads == 2
    assert summary.runs == 3
    assert summary.assistants == 1
    assert summary.assistant_versions == 2
    assert summary.thread_ids == {str(thread_id), "thread-2"}


def test_build_migration_report_marks_split_runtime():
    catalog_summary = CatalogSummary(
        threads=2,
        runs=3,
        assistants=1,
        assistant_versions=2,
        crons=0,
        thread_ids={"thread-1", "thread-2"},
    )
    checkpoint_summary = CheckpointSummary(
        checkpoints=5,
        thread_ids={"thread-2", "thread-3"},
        top_threads=[{"thread_id": "thread-3", "checkpoint_count": 4}],
    )

    report = build_migration_report(catalog_summary, checkpoint_summary)

    assert report["runtime_mode"] == "split"
    assert report["thread_id_overlap"] == 1
    assert report["catalog_only_threads"] == 1
    assert report["checkpoint_only_threads"] == 1
    assert report["catalog_only_thread_ids_sample"] == ["thread-1"]
    assert report["checkpoint_only_thread_ids_sample"] == ["thread-3"]


def test_normalize_for_json_handles_nested_runtime_types():
    value = {
        "thread_id": uuid4(),
        "updated_at": datetime(2026, 3, 18, 12, 0, 0),
        "items": [{"checkpoint_id": uuid4()}],
        "flags": {"a", "b"},
    }

    normalized = normalize_for_json(value)

    assert isinstance(normalized["thread_id"], str)
    assert normalized["updated_at"] == "2026-03-18T12:00:00"
    assert isinstance(normalized["items"][0]["checkpoint_id"], str)
    assert normalized["flags"] == ["a", "b"]
