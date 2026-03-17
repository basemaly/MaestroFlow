from .config import GatewayConfig, get_gateway_config


def create_app():
    from .app import create_app as _create_app

    return _create_app()


def get_app():
    from .app import app as _app

    return _app


__all__ = ["create_app", "get_app", "GatewayConfig", "get_gateway_config"]
