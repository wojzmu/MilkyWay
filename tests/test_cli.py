import json
import os

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


@pytest.mark.parametrize("bad", ["", ".", "..", "a/b", "a\b", "a b", "reference", "ü"])
def test_dataset_id_rejected(sample_csv_path, tmp_path, bad):
    with pytest.raises(SystemExit):
        cli.main(["--to-parquet", str(sample_csv_path), "--dataset-id", bad,
                  "--data-dir", str(tmp_path)])


def test_stem_id_validated(tmp_path):
    p = tmp_path / "bad name.csv"
    with pytest.raises(SystemExit):
        cli.main(["--to-parquet", str(p), "--data-dir", str(tmp_path)])


@pytest.mark.parametrize("bad", [".", "..", "reference", "a b"])
def test_dataset_bare_id_validated(tmp_path, bad):
    with pytest.raises(SystemExit):
        cli.main(["--dataset", bad, "--export-csv", str(tmp_path / "o.csv"),
                  "--data-dir", str(tmp_path)])


def test_dataset_dir_resolution(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "t").mkdir()                       # cwd dir must not shadow the id
    assert cli._dataset_dir("t", "D") == os.path.join("D", "t")
    assert cli._dataset_dir(os.path.join(".", "t"), "D") == os.path.join(".", "t")
    assert cli._dataset_dir("sub/t", "D") == "sub/t"
    assert cli._dataset_dir(str(tmp_path / "t"), "D") == str(tmp_path / "t")


@pytest.mark.parametrize("argv", [["--build", "--min-mass", "0.5"], ["--build", "--max-dist", "30"],
                                  ["--build", "--csv", "x.csv"], ["--build", "--plot-only"],
                                  ["--legacy-cuts"]])
def test_build_rejects_unused_flags(argv):
    with pytest.raises(SystemExit):
        cli.main(argv)
