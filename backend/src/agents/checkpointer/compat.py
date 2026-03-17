"""Compatibility helpers for LangGraph checkpointers.

These wrappers add a small set of newer async maintenance methods that
`langgraph-api` probes for during startup. Stock memory/sqlite savers in the
current dependency set do not implement all of them, which leads to degraded
rollback/pruning behavior and noisy startup warnings.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver


class CompatibleAsyncCheckpointer(BaseCheckpointSaver):
    """Delegate to an async saver and provide best-effort maintenance methods."""

    def __init__(self, inner: BaseCheckpointSaver) -> None:
        self._inner = inner
        super().__init__(serde=getattr(inner, "serde", None))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def aget_tuple(self, config):
        return await self._inner.aget_tuple(config)

    async def alist(self, config, *, filter=None, before=None, limit=None):
        async for item in self._inner.alist(config, filter=filter, before=before, limit=limit):
            yield item

    async def aput(self, config, checkpoint, metadata, new_versions):
        return await self._inner.aput(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        await self._inner.aput_writes(config, writes, task_id, task_path)

    async def adelete_thread(self, thread_id: str) -> None:
        await self._inner.adelete_thread(thread_id)

    async def adelete_for_runs(self, run_ids: Iterable[str]) -> None:
        run_ids = {str(run_id) for run_id in run_ids if run_id}
        if not run_ids:
            return
        if hasattr(self._inner, "storage") and hasattr(self._inner, "writes"):
            self._delete_runs_in_memory(run_ids)
            return
        if hasattr(self._inner, "conn"):
            await self._delete_runs_in_sqlite(run_ids)
            return

    async def acopy_thread(self, source_thread_id: str, target_thread_id: str) -> None:
        checkpoints = [cp async for cp in self._inner.alist({"configurable": {"thread_id": source_thread_id}})]
        checkpoints.sort(key=lambda x: x.config["configurable"]["checkpoint_id"])
        for cp in checkpoints:
            ns = cp.config["configurable"].get("checkpoint_ns", "")
            new_config = {"configurable": {"thread_id": target_thread_id, "checkpoint_ns": ns}}
            parent_config = cp.parent_config
            if parent_config and parent_config.get("configurable"):
                parent_id = parent_config["configurable"].get("checkpoint_id")
                if parent_id is not None:
                    new_config["configurable"]["checkpoint_id"] = parent_id
            new_metadata = dict(cp.metadata)
            if "thread_id" in new_metadata:
                new_metadata["thread_id"] = target_thread_id
            stored_config = await self._inner.aput(
                new_config,
                cp.checkpoint,
                new_metadata,
                cp.checkpoint.get("channel_versions", {}),
            )
            if cp.pending_writes:
                writes_by_task: dict[str, list[tuple[str, Any]]] = {}
                for task_id, channel, value in cp.pending_writes:
                    writes_by_task.setdefault(task_id, []).append((channel, value))
                for task_id, writes in writes_by_task.items():
                    await self._inner.aput_writes(stored_config, writes, task_id)

    async def aprune(self, thread_ids: Sequence[str], *, strategy: str = "keep_latest") -> None:
        if strategy == "delete_all":
            for thread_id in thread_ids:
                await self.adelete_thread(str(thread_id))
            return
        if strategy != "keep_latest":
            raise ValueError(f"Unsupported prune strategy: {strategy}")
        if hasattr(self._inner, "storage") and hasattr(self._inner, "writes"):
            self._prune_in_memory(thread_ids)
            return
        if hasattr(self._inner, "conn"):
            await self._prune_in_sqlite(thread_ids)
            return
        raise RuntimeError("keep_latest pruning is not supported by this checkpointer")

    def get_next_version(self, current, channel):
        return self._inner.get_next_version(current, channel)

    def _delete_runs_in_memory(self, run_ids: set[str]) -> None:
        storage = self._inner.storage
        writes = self._inner.writes
        blobs = self._inner.blobs
        doomed: list[tuple[str, str, str]] = []
        for thread_id, namespaces in storage.items():
            for checkpoint_ns, checkpoints in namespaces.items():
                for checkpoint_id, (_, metadata_typed, _) in list(checkpoints.items()):
                    metadata = self._loads_metadata_typed(metadata_typed)
                    if self._metadata_matches_run_ids(metadata, run_ids):
                        doomed.append((thread_id, checkpoint_ns, checkpoint_id))
        for thread_id, checkpoint_ns, checkpoint_id in doomed:
            checkpoints = storage.get(thread_id, {}).get(checkpoint_ns, {})
            checkpoint_record = checkpoints.pop(checkpoint_id, None)
            writes.pop((thread_id, checkpoint_ns, checkpoint_id), None)
            if checkpoint_record is not None:
                self._remove_blob_versions(thread_id, checkpoint_ns, checkpoint_record[0])

    def _prune_in_memory(self, thread_ids: Sequence[str]) -> None:
        storage = self._inner.storage
        writes = self._inner.writes
        blobs = self._inner.blobs
        for thread_id in [str(t) for t in thread_ids]:
            namespaces = storage.get(thread_id, {})
            for checkpoint_ns, checkpoints in namespaces.items():
                checkpoint_ids = sorted(checkpoints.keys(), reverse=True)
                for checkpoint_id in checkpoint_ids[1:]:
                    checkpoint_record = checkpoints.pop(checkpoint_id, None)
                    writes.pop((thread_id, checkpoint_ns, checkpoint_id), None)
                    if checkpoint_record is not None:
                        self._remove_blob_versions(thread_id, checkpoint_ns, checkpoint_record[0])
        self._inner.blobs = blobs

    def _remove_blob_versions(self, thread_id: str, checkpoint_ns: str, checkpoint_typed: tuple[str, bytes]) -> None:
        try:
            checkpoint = self.serde.loads_typed(checkpoint_typed)
        except Exception:
            return
        channel_versions = checkpoint.get("channel_versions", {})
        for channel, version in channel_versions.items():
            self._inner.blobs.pop((thread_id, checkpoint_ns, channel, version), None)

    async def _delete_runs_in_sqlite(self, run_ids: set[str]) -> None:
        await self._inner.setup()
        async with self._inner.lock, self._inner.conn.cursor() as cur:
            await cur.execute("SELECT thread_id, checkpoint_ns, checkpoint_id, metadata FROM checkpoints")
            doomed: list[tuple[str, str, str]] = []
            async for thread_id, checkpoint_ns, checkpoint_id, metadata_bytes in cur:
                metadata = self._loads_json_bytes(metadata_bytes)
                if self._metadata_matches_run_ids(metadata, run_ids):
                    doomed.append((thread_id, checkpoint_ns, checkpoint_id))
            for thread_id, checkpoint_ns, checkpoint_id in doomed:
                await self._delete_sqlite_checkpoint(cur, thread_id, checkpoint_ns, checkpoint_id)
            if doomed:
                await self._inner.conn.commit()

    async def _prune_in_sqlite(self, thread_ids: Sequence[str]) -> None:
        await self._inner.setup()
        async with self._inner.lock, self._inner.conn.cursor() as cur:
            for thread_id in [str(t) for t in thread_ids]:
                await cur.execute(
                    "SELECT checkpoint_ns, checkpoint_id FROM checkpoints WHERE thread_id = ? ORDER BY checkpoint_ns, checkpoint_id DESC",
                    (thread_id,),
                )
                latest_by_ns: dict[str, str] = {}
                doomed: list[tuple[str, str, str]] = []
                async for checkpoint_ns, checkpoint_id in cur:
                    if checkpoint_ns not in latest_by_ns:
                        latest_by_ns[checkpoint_ns] = checkpoint_id
                    else:
                        doomed.append((thread_id, checkpoint_ns, checkpoint_id))
                for doomed_thread_id, checkpoint_ns, checkpoint_id in doomed:
                    await self._delete_sqlite_checkpoint(cur, doomed_thread_id, checkpoint_ns, checkpoint_id)
            await self._inner.conn.commit()

    async def _delete_sqlite_checkpoint(self, cur, thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> None:
        await cur.execute(
            "DELETE FROM writes WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?",
            (thread_id, checkpoint_ns, checkpoint_id),
        )
        await cur.execute(
            "DELETE FROM checkpoints WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?",
            (thread_id, checkpoint_ns, checkpoint_id),
        )

    @staticmethod
    def _loads_json_bytes(payload: bytes | None) -> dict[str, Any]:
        if not payload:
            return {}
        try:
            return json.loads(payload)
        except Exception:
            return {}

    def _loads_metadata_typed(self, metadata_typed: tuple[str, bytes]) -> dict[str, Any]:
        try:
            value = self.serde.loads_typed(metadata_typed)
        except Exception:
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _metadata_matches_run_ids(metadata: dict[str, Any], run_ids: set[str]) -> bool:
        for key in ("run_id", "run_attempt_id", "langgraph_run_id"):
            value = metadata.get(key)
            if value is not None and str(value) in run_ids:
                return True
        return False
