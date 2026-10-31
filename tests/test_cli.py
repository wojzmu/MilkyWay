import json

import pandas as pd
import pytest

from milkyway import cli, csv_io


def test_parquet_roundtrip(sample_csv_path, tmp_path, monkeypatch):
    data = str(tmp_path / "data")
    rendered = []
    monkeypatch.setattr(cli, "render_all", rendered.append)

    cli.main(["--to-parquet", str(sample_csv_path), "--dataset-id", "t", "--data-dir", data])
    manifest = json.loads((tmp_path / "data" / "t" / "manifest.json").read_text())
    assert manifest["source"]["kind"] == "legacy_csv"
    assert len(manifest["source"]["sha256"]) == 64
    assert "\\" not in manifest["source"]["path"]
    assert not rendered

    cli.main(["--plot-only", "--dataset", "t", "--data-dir", data, "--max-dist", "20"])
    n_in = len(pd.read_csv(sample_csv_path))
    assert len(rendered) == 1 and 0 < len(rendered[0]) <= n_in
    assert (rendered[0]["dist_pc"] <= 20).all()

    out = tmp_path / "out.csv"
    cli.main(["--dataset", "t", "--data-dir", data, "--export-csv", str(out)])
    assert len(rendered) == 1
    src, got = pd.read_csv(sample_csv_path), pd.read_csv(out)
    assert list(got.columns) == list(csv_io.LEGACY_CSV_COLUMNS)
    assert set(got["star_id"]) == set(src["star_id"])


def test_default_dataset_id_is_stem(sample_csv_path, tmp_path):
    cli.main(["--to-parquet", str(sample_csv_path), "--data-dir", str(tmp_path)])
    assert (tmp_path / sample_csv_path.stem / "manifest.json").exists()


@pytest.mark.parametrize("argv", [
    ["--export-csv", "x.csv"],
    ["--dataset", "x"],
    ["--dataset-id", "x"],
    ["--to-parquet", "a.csv", "--plot-only"],
])
def test_misuse(argv):
    with pytest.raises(SystemExit):
        cli.main(argv)
