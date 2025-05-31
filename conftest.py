import pytest

@pytest.fixture(autouse=True)
def change_cwd(tmp_path, monkeypatch):
    """
    Change working directory for each test to a fresh temporary path.
    Ensures all test artifact files are created in isolation.
    """
    monkeypatch.chdir(tmp_path)