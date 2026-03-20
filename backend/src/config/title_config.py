"""Configuration for automatic thread title generation."""

from pydantic import BaseModel, Field


class TitleConfig(BaseModel):
    """Configuration for automatic thread title generation."""

    enabled: bool = Field(
        default=True,
        description="Whether to enable automatic title generation",
    )
    max_words: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Maximum number of words in the generated title",
    )
    max_chars: int = Field(
        default=60,
        ge=10,
        le=200,
        description="Maximum number of characters in the generated title",
    )
    model_name: str | None = Field(
        default=None,
        description="Model name to use for title generation (None = use default model)",
    )
    prompt_template: str = Field(
        default=(
            "MUST: Return one plain line only — title case, no quotes, no markdown, "
            "no prefix like 'Title:', no trailing period.\n"
            "MUST: Maximum {max_words} words. Maximum {max_chars} characters.\n\n"
            "Conversation:\n"
            "User: {user_msg}\n"
            "Assistant: {assistant_msg}\n\n"
            "Write a title naming the specific task or topic discussed.\n\n"
            "Correct: Migrating Postgres to TimescaleDB\n"
            "Wrong: Title: Setting Up the Docker Environment\n"
            "Wrong: Helping the user configure their project\n\n"
            "Return the title and nothing else."
        ),
        description="Prompt template for title generation",
    )


# Global configuration instance
_title_config: TitleConfig = TitleConfig()


def get_title_config() -> TitleConfig:
    """Get the current title configuration."""
    return _title_config


def set_title_config(config: TitleConfig) -> None:
    """Set the title configuration."""
    global _title_config
    _title_config = config


def load_title_config_from_dict(config_dict: dict) -> None:
    """Load title configuration from a dictionary."""
    global _title_config
    _title_config = TitleConfig(**config_dict)
