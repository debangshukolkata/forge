"""Shared fixtures for the model-independent pass checks. BENCH_REPO is the delivered repository copy."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo() -> Path:
    return Path(os.environ["BENCH_REPO"])
