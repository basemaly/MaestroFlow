"""LangGraph assembly for the doc-edit workflow."""

from __future__ import annotations

import uuid

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.doc_editing.nodes import collector, dispatch_skills, finalizer, human_review, prepare_run, skill_agent
from src.doc_editing.run_tracker import get_doc_edit_checkpoints_db_path
from src.doc_editing.state import DocEditState

_graph = None
_checkpointer = None
_checkpointer_ctx = None


async def _get_doc_edit_checkpointer():
    global _checkpointer
    global _checkpointer_ctx
    if _checkpointer is None:
        conn_str = str(get_doc_edit_checkpoints_db_path())
        _checkpointer_ctx = AsyncSqliteSaver.from_conn_string(conn_str)
        _checkpointer = await _checkpointer_ctx.__aenter__()
        await _checkpointer.setup()
    return _checkpointer


def build_doc_edit_graph(*, checkpointer):
    builder = StateGraph(DocEditState)
    builder.add_node("prepare_run", prepare_run)
    builder.add_node("skill_agent", skill_agent)
    builder.add_node("collector", collector)
    builder.add_node("human_review", human_review)
    builder.add_node("finalizer", finalizer)

    builder.set_entry_point("prepare_run")
    builder.add_conditional_edges("prepare_run", dispatch_skills, ["skill_agent"])
    builder.add_edge("skill_agent", "collector")
    builder.add_edge("collector", "human_review")
    builder.add_edge("human_review", "finalizer")
    builder.add_edge("finalizer", END)
    return builder.compile(checkpointer=checkpointer)


async def get_doc_edit_graph():
    global _graph
    if _graph is None:
        _graph = build_doc_edit_graph(checkpointer=await _get_doc_edit_checkpointer())
    return _graph


def make_run_id() -> str:
    return uuid.uuid4().hex[:8]
