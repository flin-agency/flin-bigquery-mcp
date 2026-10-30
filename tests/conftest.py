import os

import pytest


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for key in tuple(os.environ):
        if key.startswith("GOOGLE_"):
            monkeypatch.delenv(key, raising=False)
