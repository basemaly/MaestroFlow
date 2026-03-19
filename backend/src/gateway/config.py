import os

from pydantic import BaseModel, Field

DEFAULT_CORS_ORIGINS = [
    "http://localhost:2027",
    "http://127.0.0.1:2027",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3010",
    "http://127.0.0.1:3010",
]


class GatewayConfig(BaseModel):
    """Configuration for the API Gateway."""

    host: str = Field(default="0.0.0.0", description="Host to bind the gateway server")
    port: int = Field(default=8001, description="Port to bind the gateway server")
    cors_origins: list[str] = Field(default_factory=lambda: DEFAULT_CORS_ORIGINS.copy(), description="Allowed CORS origins")


_gateway_config: GatewayConfig | None = None


def get_gateway_config() -> GatewayConfig:
    """Get gateway config, loading from environment if available."""
    global _gateway_config
    if _gateway_config is None:
        cors_origins_str = os.getenv("CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS))
        _gateway_config = GatewayConfig(
            host=os.getenv("GATEWAY_HOST", "0.0.0.0"),
            port=int(os.getenv("GATEWAY_PORT", "8001")),
            cors_origins=cors_origins_str.split(","),
        )
    return _gateway_config
