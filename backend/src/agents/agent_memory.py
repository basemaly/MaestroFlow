"""Persistent per-agent memory — a user-authored scratchpad injected into system prompts."""
from __future__ import annotations

import time
from pathlib import Path


def _memory_path(agent_name: str) -> Path:
    from src.config.paths import get_paths
    return get_paths().agent_dir(agent_name) / "memory.txt"


def get_memory(agent_name: str) -> str:
    path = _memory_path(agent_name)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def set_memory(agent_name: str, content: str) -> None:
    path = _memory_path(agent_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def append_to_memory(agent_name: str, content: str) -> None:
    existing = get_memory(agent_name)
    timestamp = time.strftime("%Y-%m-%d %H:%M")
    separator = f"\n\n--- {timestamp} ---\n"
    new_content = existing + separator + content if existing.strip() else content
    set_memory(agent_name, new_content)


def clear_memory(agent_name: str) -> None:
    path = _memory_path(agent_name)
    if path.exists():
        path.write_text("", encoding="utf-8")
