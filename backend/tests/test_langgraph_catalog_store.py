from src.langgraph.catalog_store import _thread_row


def test_thread_row_preserves_message_shapes_and_normalizes_types():
    thread = {
        "thread_id": "11111111-1111-1111-1111-111111111111",
        "metadata": {"assistant_id": "agent-1"},
        "values": {
            "title": "Saved thread",
            "messages": [
                {
                    "type": "human",
                    "content": [{"type": "text", "text": "hello"}],
                    "additional_kwargs": {"foo": "bar"},
                }
            ],
        },
        "interrupts": [{"when": "never"}],
        "config": {"configurable": {"thread_id": "11111111-1111-1111-1111-111111111111"}},
    }

    row = _thread_row(thread)

    assert row["thread_id"] == "11111111-1111-1111-1111-111111111111"
    assert row["values"]["title"] == "Saved thread"
    assert row["values"]["messages"][0]["content"][0]["text"] == "hello"
    assert row["metadata"]["assistant_id"] == "agent-1"
    assert row["interrupts"][0]["when"] == "never"


def test_thread_row_serializes_non_string_error_payload():
    row = _thread_row(
        {
            "thread_id": "11111111-1111-1111-1111-111111111111",
            "error": {"message": "boom", "retryable": False},
        }
    )

    assert row["error"] == '{"message": "boom", "retryable": false}'
