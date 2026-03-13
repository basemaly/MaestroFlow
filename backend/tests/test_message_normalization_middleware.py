from langchain_core.messages import AIMessage, HumanMessage

from src.agents.middlewares.message_normalization_middleware import (
    MessageNormalizationMiddleware,
    normalize_message_content,
)


def test_normalize_message_content_leaves_strings_unchanged():
    assert normalize_message_content("hello") == "hello"


def test_normalize_message_content_converts_mixed_lists_to_text_blocks():
    content = [
        "plain text",
        {"type": "image_url", "image_url": {"url": "https://example.com/image.png"}},
        42,
        None,
    ]

    assert normalize_message_content(content) == [
        {"type": "text", "text": "plain text"},
        {"type": "image_url", "image_url": {"url": "https://example.com/image.png"}},
        {"type": "text", "text": "42"},
    ]


def test_before_model_normalizes_mixed_message_content():
    middleware = MessageNormalizationMiddleware()
    state = {
        "messages": [
            HumanMessage(content=["hello", {"type": "text", "text": "world"}]),
            AIMessage(content="done"),
        ]
    }

    result = middleware.before_model(state, runtime=None)

    assert result is not None
    first_message = result["messages"][0]
    assert first_message.content == [
        {"type": "text", "text": "hello"},
        {"type": "text", "text": "world"},
    ]
