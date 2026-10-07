from pathlib import Path

import pytest


@pytest.fixture
def tmp_path_factory_fixture(tmp_path: Path) -> Path:
    return tmp_path
