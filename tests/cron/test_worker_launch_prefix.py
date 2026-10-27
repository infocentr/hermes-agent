"""The external cron worker must boot through the published launcher."""

from __future__ import annotations

import sys
from pathlib import Path


def test_worker_launch_prefix_prefers_the_published_launcher(monkeypatch):
    """With a launcher published, the worker is spawned through it, not an interpreter.

    A bare ``-m cron.scheduler`` runs no bootstrap, so under the PM topology the
    worker has no dependencies attached and dies on its first import.
    """
    from cron import scheduler

    real_exists = Path.exists
    monkeypatch.setattr(
        Path, "exists",
        lambda self: self.name in {"hermes", "hermes.exe"} or real_exists(self),
    )

    prefix = scheduler._worker_launch_prefix()

    assert prefix[0].endswith(("hermes", "hermes.exe"))
    assert prefix[1:] == ["--run-module", "cron.scheduler"]


def test_worker_launch_prefix_falls_back_without_a_launcher(monkeypatch):
    """A bare checkout or test tree keeps the historical ``-m`` behaviour."""
    from cron import scheduler

    monkeypatch.setattr(Path, "exists", lambda self: False)

    assert scheduler._worker_launch_prefix() == [sys.executable, "-m", "cron.scheduler"]
