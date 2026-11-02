import pandas as pd


def _load(p):
    return pd.read_csv(p, dtype=str, keep_default_na=False)


def test_rows_and_header(sample_csv_path, reference_csv_path):
    df = _load(sample_csv_path)
    ref = pd.read_csv(reference_csv_path, nrows=0)
    assert len(df) == 200
    assert list(df.columns) == list(ref.columns)


def test_star_id_unique(sample_csv_path):
    assert _load(sample_csv_path).star_id.is_unique


def test_star_id_prefix(sample_csv_path):
    assert _load(sample_csv_path).star_id.str.match(r"^(Gaia DR3 |HIP )").all()
