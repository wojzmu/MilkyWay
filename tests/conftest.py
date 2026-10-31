from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def sample_csv_path() -> Path:
    return ROOT / "tests" / "fixtures" / "stars_sample.csv"


@pytest.fixture(scope="session")
def reference_csv_path() -> Path:
    p = ROOT / "data" / "reference" / "nearby_stars_60.0pc.csv"
    if not p.exists():
        pytest.skip("frozen reference catalogue not present")
    return p


@pytest.fixture
def tmp_dataset_dir(tmp_path) -> Path:
    return tmp_path
