"""Acceptance tests for the partitioned Parquet store (milkyway.storage)."""
import json
import shutil
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from milkyway import csv_io, schema, storage

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_CSV = ROOT / "tests" / "fixtures" / "stars_sample.csv"
REFERENCE_CSV = ROOT / "data" / "reference" / "nearby_stars_60.0pc.csv"
SEL = {"g_max": None}
SRC = {"kind": "test"}
SHIFT = 2 * (schema.HEALPIX_LEVEL - schema.PARTITION_LEVEL)


def _build(table, d, **kw):
    return storage.write_dataset([table], d, dataset_id="ref", selection=SEL,
                                 source=SRC, **kw)


def _files(root):
    return sorted(Path(root).glob("catalog/*/*.parquet"))


def _key(f):
    return int(f.parent.name.split("=")[1])


# ---------------------------------------------------------------- fixtures

@pytest.fixture(scope="module")
def sample_table():
    return csv_io.read_catalogue_csv(SAMPLE_CSV)


@pytest.fixture(scope="module")
def reference_table():
    if not REFERENCE_CSV.exists():
        pytest.skip("frozen reference catalogue not present")
    return csv_io.read_catalogue_csv(REFERENCE_CSV)


@pytest.fixture(scope="module")
def reference_dataset(reference_table, tmp_path_factory):
    d = tmp_path_factory.mktemp("ref") / "ds"
    manifest = _build(reference_table, d)
    return d, manifest


@pytest.fixture(scope="module")
def sample_dataset(sample_table, tmp_path_factory):
    d = tmp_path_factory.mktemp("smp") / "ds"
    manifest = _build(sample_table, d)
    return d, manifest


@pytest.fixture(params=["sample", "reference"])
def case(request):
    """(table, dataset_dir, manifest) for the sample and the reference catalogue."""
    if request.param == "sample":
        return (request.getfixturevalue("sample_table"),
                *request.getfixturevalue("sample_dataset"))
    return (request.getfixturevalue("reference_table"),
            *request.getfixturevalue("reference_dataset"))


@pytest.fixture
def fresh(sample_table, tmp_path):
    """A private, mutable copy of a good sample dataset."""
    d = tmp_path / "ds"
    _build(sample_table, d)
    return d


# ------------------------------------------------------- 1. completeness

def test_completeness(case):
    table, d, manifest = case
    files = _files(d)
    tables = [pq.read_table(f) for f in files]
    total = sum(t.num_rows for t in tables)
    assert total == table.num_rows
    assert manifest["storage"]["total_rows"] == table.num_rows
    assert sum(p["rows"] for p in manifest["storage"]["partitions"]) == table.num_rows
    assert len(files) == len(manifest["storage"]["partitions"])
    back = pa.concat_tables(tables)
    ids = back["star_id"].to_pylist()
    assert len(set(ids)) == len(ids)
    assert set(ids) == set(table["star_id"].to_pylist())
    for col in ("source_id", "hip"):
        vals = back[col].drop_null().to_pylist()
        assert len(vals) == len(set(vals)), f"duplicate {col}"


# ------------------------------------------------------- 2. partition key

def test_partition_key(case):
    _, d, _ = case
    for f in _files(d):
        k = _key(f)
        t = pq.read_table(f, columns=["healpix", "source_id"])
        for hpx, sid in zip(t["healpix"].to_pylist(), t["source_id"].to_pylist()):
            assert hpx >> SHIFT == k
            if sid is not None:
                assert hpx == sid >> schema.GAIA_HEALPIX_SHIFT


# ------------------------------------------------------- 3. order

def test_order_within_file(case):
    _, d, _ = case
    for f in _files(d):
        t = pq.read_table(f, columns=list(schema.SORT_KEY))
        keys = [(h, s is None, s or 0, p is None, p or 0)
                for h, s, p in zip(t["healpix"].to_pylist(),
                                   t["source_id"].to_pylist(),
                                   t["hip"].to_pylist())]
        assert keys == sorted(keys), f"{f} not sorted"


# ------------------------------------------------------- 4. row groups

@pytest.mark.parametrize("which", ["sample", "reference"])
def test_row_groups_fixed_size(which, tmp_path, request):
    if which == "sample":
        table, size = request.getfixturevalue("sample_table"), 16
    else:
        table, size = request.getfixturevalue("reference_table"), 1024
    d = tmp_path / "rg"
    manifest = _build(table, d, row_group_size=size)
    assert manifest["storage"]["row_group_size"] == size
    multi = 0
    for f in _files(d):
        md = pq.ParquetFile(f).metadata
        counts = [md.row_group(i).num_rows for i in range(md.num_row_groups)]
        assert all(c == size for c in counts[:-1]), (f, counts)
        assert 0 < counts[-1] <= size
        multi += len(counts) > 1
    assert multi > 0, "test did not exercise multiple row groups"


# ------------------------------------------------------- 5. schema

def test_file_schema_and_metadata(case):
    _, d, _ = case
    for f in _files(d):
        s = pq.read_schema(f)
        assert s.equals(schema.CATALOGUE_SCHEMA, check_metadata=False)
        # pyarrow does round-trip the schema metadata into the Parquet footer.
        assert s.metadata[schema.SCHEMA_METADATA_KEY] == b"1"


# ------------------------------------------------------- 6. values

def test_values_roundtrip(case):
    table, d, _ = case
    back = pa.concat_tables([pq.read_table(f, schema=schema.CATALOGUE_SCHEMA)
                             for f in _files(d)])
    assert back.sort_by("star_id").equals(table.sort_by("star_id"))


# ------------------------------------------------------- 7. manifest

def test_manifest_contents(case):
    _, d, m = case
    on_disk = json.loads((d / storage.MANIFEST_NAME).read_text())
    assert on_disk == m
    assert m["status"] == "complete"
    assert m["schema_version"] == schema.SCHEMA_VERSION
    assert m["columns"] == list(schema.COLUMNS)
    assert m["selection"] == SEL
    assert m["source"] == SRC
    assert m["dataset_id"] == "ref"
    assert m["storage"]["partition_level"] == 2
    assert m["storage"]["row_group_size"] == storage.ROW_GROUP_SIZE
    assert list(Path(d).rglob("*.tmp")) == []
    for p in m["storage"]["partitions"]:
        assert p["path"] == storage.partition_path(p["part_hpx"])
        assert storage._sha256(d / p["path"]) == p["sha256"]


# ------------------------------------------------------- 8. determinism

def test_determinism(case, tmp_path):
    table, _, _ = case
    m1 = _build(table, tmp_path / "a")
    m2 = _build(table, tmp_path / "b")
    h1 = [(p["path"], p["sha256"]) for p in m1["storage"]["partitions"]]
    h2 = [(p["path"], p["sha256"]) for p in m2["storage"]["partitions"]]
    assert h1 == h2


# ------------------------------------------------------- 9. write refusals

def test_refuses_existing_manifest(fresh, sample_table):
    with pytest.raises(FileExistsError):
        _build(sample_table, fresh)


def test_refuses_leftover_parquet(sample_table, tmp_path):
    d = tmp_path / "ds"
    (d / "catalog" / "part_hpx=1").mkdir(parents=True)
    (d / "catalog" / "part_hpx=1" / "part-0.parquet").write_bytes(b"x")
    with pytest.raises(FileExistsError):
        _build(sample_table, d)
    assert not (d / storage.MANIFEST_NAME).exists()


def test_refuses_partition_split_across_tables(sample_table, tmp_path):
    half = sample_table.num_rows // 2
    with pytest.raises(ValueError, match="split"):
        storage.write_dataset([sample_table.slice(0, half),
                               sample_table.slice(0, half)], tmp_path / "ds",
                              dataset_id="x", selection=SEL, source=SRC)


def test_orphan_tmp_files_removed(sample_table, tmp_path):
    d = tmp_path / "ds"
    (d / "catalog" / "part_hpx=3").mkdir(parents=True)
    (d / "catalog" / "part_hpx=3" / "part-0.parquet.tmp").write_bytes(b"partial")
    (d / "manifest.json.tmp").write_bytes(b"{")
    _build(sample_table, d)
    assert list(d.rglob("*.tmp")) == []
    storage.open_catalog(d)


# ------------------------------------------------------- 10. open_catalog

def test_open_catalog_good(fresh, sample_table):
    m = storage.open_catalog(fresh)
    assert m["status"] == "complete"
    assert m["storage"]["total_rows"] == sample_table.num_rows
    assert storage.open_catalog(fresh, verify_hashes=True) == m


def test_open_missing_manifest(fresh):
    (fresh / storage.MANIFEST_NAME).unlink()
    with pytest.raises(storage.IncompleteDatasetError):
        storage.open_catalog(fresh)
    with pytest.warns(UserWarning):
        assert storage.open_catalog(fresh, allow_incomplete=True) is None


def test_open_status_building(fresh):
    p = fresh / storage.MANIFEST_NAME
    m = json.loads(p.read_text())
    m["status"] = "building"
    p.write_text(json.dumps(m))
    with pytest.raises(storage.IncompleteDatasetError):
        storage.open_catalog(fresh)


def test_open_partition_deleted(fresh):
    _files(fresh)[0].unlink()
    with pytest.raises(storage.IncompleteDatasetError):
        storage.open_catalog(fresh)


def test_open_extra_partition(fresh):
    extra = fresh / "catalog" / "part_hpx=999" / "part-0.parquet"
    extra.parent.mkdir()
    shutil.copy(_files(fresh)[0], extra)
    with pytest.raises(storage.IncompleteDatasetError):
        storage.open_catalog(fresh)


def test_open_file_with_fewer_rows(fresh):
    f = max(_files(fresh), key=lambda p: pq.ParquetFile(p).metadata.num_rows)
    t = pq.read_table(f)
    assert t.num_rows > 1
    pq.write_table(t.slice(0, t.num_rows - 1), f)
    with pytest.raises(storage.IncompleteDatasetError):
        storage.open_catalog(fresh)


def test_flipped_byte_caught_only_by_hash_check(fresh):
    f = _files(fresh)[0]
    data = bytearray(f.read_bytes())
    data[len(data) // 4] ^= 0xFF          # data region, well before the footer
    f.write_bytes(bytes(data))
    storage.open_catalog(fresh)           # cheap check: footer unchanged
    with pytest.raises(storage.IncompleteDatasetError):
        storage.open_catalog(fresh, verify_hashes=True)


# ------------------------------------------------------- 11. crash safety

def test_simulated_crash_leaves_no_partial_parquet(sample_table, tmp_path, monkeypatch):
    d = tmp_path / "ds"
    real = storage._write_partition
    calls = []

    def flaky(root, k, rows, row_group_size):
        calls.append(k)
        if len(calls) == 5:
            raise OSError("simulated crash")
        return real(root, k, rows, row_group_size)

    monkeypatch.setattr(storage, "_write_partition", flaky)
    with pytest.raises(OSError, match="simulated"):
        _build(sample_table, d)

    assert not (d / storage.MANIFEST_NAME).exists()
    with pytest.raises(storage.IncompleteDatasetError):
        storage.open_catalog(d)

    files = _files(d)
    assert len(files) == 4
    hp = sample_table["healpix"].to_pylist()
    for f in files:
        k = _key(f)
        want = sum(1 for h in hp if h >> SHIFT == k)
        assert pq.ParquetFile(f).metadata.num_rows == want
        pq.read_table(f)                  # fully readable

    # Intended behaviour: a retry into the same dir is refused (leftover .parquet);
    # the user removes the directory and rebuilds.
    monkeypatch.setattr(storage, "_write_partition", real)
    with pytest.raises(FileExistsError):
        _build(sample_table, d)
    shutil.rmtree(d)
    _build(sample_table, d)
    storage.open_catalog(d, verify_hashes=True)


def test_crash_inside_pq_write_leaves_no_partial_parquet(sample_table, tmp_path,
                                                         monkeypatch):
    d = tmp_path / "ds"
    real = pq.write_table
    n = []

    def boom(table, where, **kw):
        n.append(1)
        if len(n) == 5:
            Path(where).write_bytes(b"PAR1partial")
            raise OSError("disk died")
        return real(table, where, **kw)

    monkeypatch.setattr(storage.pq, "write_table", boom)
    with pytest.raises(OSError):
        _build(sample_table, d)
    assert len(_files(d)) == 4
    for f in _files(d):
        pq.read_table(f)
    assert not (d / storage.MANIFEST_NAME).exists()
