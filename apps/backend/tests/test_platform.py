import pytest
from fastapi.testclient import TestClient

from ago.main import create_app
from ago.platform import Container, DependencyError, Lifetime, Settings, build_container


def test_settings_injection():
    config = Settings(environment="test")
    assert build_container(config).resolve("settings") is config


def test_singleton_and_transient():
    container = Container()
    container.register("singleton", lambda _: object(), Lifetime.SINGLETON)
    container.register("transient", lambda _: object())
    assert container.resolve("singleton") is container.resolve("singleton")
    assert container.resolve("transient") is not container.resolve("transient")


def test_scoped():
    container = Container()
    container.register("scoped", lambda _: object(), Lifetime.SCOPED)
    with container.scope() as resolver:
        assert resolver.resolve("scoped") is resolver.resolve("scoped")
    with container.scope() as other:
        assert other.resolve("scoped") is not resolver.resolve("scoped")


def test_duplicate_and_missing():
    container = Container()
    container.register("a", lambda _: 1)
    with pytest.raises(DependencyError, match="Duplicate"):
        container.register("a", lambda _: 2)
    with pytest.raises(DependencyError, match="not registered"):
        container.resolve("unknown")


def test_cycle():
    container = Container()
    container.register("a", lambda resolver: resolver.resolve("b"))
    container.register("b", lambda resolver: resolver.resolve("a"))
    with pytest.raises(DependencyError, match="Circular"):
        container.resolve("a")


def test_health_and_request_id():
    client = TestClient(create_app())
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]
    assert client.get("/health/ready").status_code == 200
