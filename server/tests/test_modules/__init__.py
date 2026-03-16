"""Test modules for integration tests."""
# Lazy imports to avoid import errors when pc_agent is not in path
# These modules will be loaded by the agent when needed

__all__ = ["TestEchoModule", "TestFailModule"]

def __getattr__(name):
    """Lazy import of test modules."""
    if name == "TestEchoModule":
        from .test_echo import TestEchoModule
        return TestEchoModule
    elif name == "TestFailModule":
        from .test_fail import TestFailModule
        return TestFailModule
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

