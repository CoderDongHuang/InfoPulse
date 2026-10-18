"""Request/task-local settings snapshots. Never mutate the process singleton."""
from contextlib import contextmanager
from contextvars import ContextVar

from app.config import Settings, get_settings

_runtime: ContextVar[Settings | None] = ContextVar("private_service_settings", default=None)


def get_runtime_settings() -> Settings:
    return _runtime.get() or get_settings()


class RuntimeSettings:
    def __getattr__(self, name):
        return getattr(get_runtime_settings(), name)


@contextmanager
def use_settings(settings: Settings):
    token = _runtime.set(settings)
    try:
        yield settings
    finally:
        _runtime.reset(token)
