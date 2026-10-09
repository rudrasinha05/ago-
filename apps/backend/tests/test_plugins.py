import pytest

from ago.plugins import PluginRegistry


class Example:
    def __init__(self, name, dependencies=(), trace=None, fail=False):
        self.name = name
        self.dependencies = dependencies
        self.trace = trace if trace is not None else []
        self.fail = fail

    def start(self):
        self.trace.append("start:" + self.name)
        if self.fail:
            raise RuntimeError("failed")

    def stop(self):
        self.trace.append("stop:" + self.name)


def test_dependency_order_and_reverse_shutdown():
    trace = []
    registry = PluginRegistry()
    registry.register(Example("web", ("db",), trace))
    registry.register(Example("db", trace=trace))
    registry.start()
    assert trace == ["start:db", "start:web"]
    assert all(state.running for state in registry.states())
    registry.stop()
    assert trace[-2:] == ["stop:web", "stop:db"]


def test_cycle_and_missing_dependencies_rejected():
    registry = PluginRegistry()
    registry.register(Example("a", ("b",)))
    registry.register(Example("b", ("a",)))
    with pytest.raises(ValueError, match="Circular"):
        registry.start()


def test_failed_start_rolls_back():
    trace = []
    registry = PluginRegistry()
    registry.register(Example("ok", trace=trace))
    registry.register(Example("broken", ("ok",), trace, True))
    with pytest.raises(RuntimeError):
        registry.start()
    assert trace[-1] == "stop:ok"
