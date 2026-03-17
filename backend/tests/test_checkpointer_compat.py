from src.agents.checkpointer.compat import CompatibleAsyncCheckpointer


def test_sqlite_compatible_checkpointer_prunes_keep_latest(tmp_path):
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    async def run():
        db_path = tmp_path / "checkpoints.db"
        async with AsyncSqliteSaver.from_conn_string(str(db_path)) as saver:
            wrapped = CompatibleAsyncCheckpointer(saver)
            await saver.setup()

            for checkpoint_id in ("1", "2"):
                config = {
                    "configurable": {
                        "thread_id": "thread-1",
                        "checkpoint_ns": "",
                        "checkpoint_id": checkpoint_id,
                    }
                }
                checkpoint = {"id": checkpoint_id, "ts": checkpoint_id, "channel_values": {}, "channel_versions": {}}
                await wrapped.aput(config, checkpoint, {}, {})

            await wrapped.aprune(["thread-1"], strategy="keep_latest")

            remaining = [item async for item in wrapped.alist({"configurable": {"thread_id": "thread-1"}})]
            assert len(remaining) == 1
            assert remaining[0].config["configurable"]["checkpoint_id"] == "2"

    import asyncio

    asyncio.run(run())


def test_memory_compatible_checkpointer_deletes_matching_run_ids():
    from langgraph.checkpoint.memory import InMemorySaver

    async def run():
        wrapped = CompatibleAsyncCheckpointer(InMemorySaver())

        keep_config = {
            "configurable": {"thread_id": "thread-1", "checkpoint_ns": "", "checkpoint_id": "keep"},
            "metadata": {"run_id": "keep-run"},
        }
        drop_config = {
            "configurable": {"thread_id": "thread-1", "checkpoint_ns": "", "checkpoint_id": "drop"},
            "metadata": {"run_id": "drop-run"},
        }

        for config in (keep_config, drop_config):
            checkpoint = {
                "id": config["configurable"]["checkpoint_id"],
                "ts": config["configurable"]["checkpoint_id"],
                "channel_values": {},
                "channel_versions": {},
            }
            await wrapped.aput(config, checkpoint, {}, {})

        await wrapped.adelete_for_runs(["drop-run"])

        remaining = [item async for item in wrapped.alist({"configurable": {"thread_id": "thread-1"}})]
        ids = {item.config["configurable"]["checkpoint_id"] for item in remaining}
        assert ids == {"keep"}

    import asyncio

    asyncio.run(run())
