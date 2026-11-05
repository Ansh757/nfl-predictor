"""Shared test fixtures."""
import pytest


@pytest.fixture(autouse=True)
def no_background_simulation(monkeypatch):
    """
    Endpoint tests must not start real 10,000-run simulations on the background
    worker - eight seconds of CPU and a cache file per game they touch. Queueing
    is recorded instead; a test that needs the real thing calls service.run.
    """
    from rotobot.pbp import service
    queued = []
    monkeypatch.setattr(service, "queue", lambda *args, **kwargs: queued.append(args) or True)
    return queued
