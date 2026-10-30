import pytest

from keepmum import legacy


@pytest.fixture(autouse=True)
def _no_migration(monkeypatch):
    """CLI tests run with the real HOME: never move the developer's own sotto folders."""
    monkeypatch.setattr(legacy, "migrate_quietly", lambda: None)
