"""
GUI пакет для PC Agent.

Предоставляет локальный Qt GUI для взаимодействия с агентом через SSE.
"""

__all__ = ["run_gui"]


def __getattr__(name: str):
    if name == "run_gui":
        from .main import run_gui

        return run_gui
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")







