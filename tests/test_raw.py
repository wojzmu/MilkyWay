"""Contract tests for milkyway.raw (no network)."""
import json
import sys

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from milkyway import raw

SEL = raw.DEFAULT_SELECTION
INT64_MAX = 2 ** 63 - 1


def make_table(tile, n=5, **over):
    """A valid synthetic tile table; `over` replaces whole columns (lists)."""
    cols = {}
    for f in raw.RAW_SCHEMA:
        if f.name == "source_id":
            vals = [tile.lo + 1000 * i for i in range(n)]
        elif f.name == "parallax":
            vals = [1.0 + i for i in range(n)]
        elif f.name == "phot_g_mean_mag":
            vals = [10.0 + 0.5 * i for i in range(n)]
        elif pa.types.is_boolean(f.type):
            vals = [False] * n
        else:
            vals = [1] * n if pa.types.is_integer(f.type) else [1.5] * n
        cols[f.name] = vals
    cols.update(over)
    return pa.table({f.name: pa.array(cols[f.name], type=f.type) for f in raw.RAW_SCHEMA})


def tile_of(k=5, rows=5):
    return raw.plan_tiles()[k]._replace(expected_rows=rows)


def test_tile_range_covers_source_id_space():
    tiles = raw.plan_tiles()
    assert len(tiles) == 192
    assert tiles[0].lo == 0
    assert tiles[-1].hi == (192 << 55) - 1 and tiles[-1].hi <= INT64_MAX
    for a, b in zip(tiles, tiles[1:]):
        assert b.lo == a.hi + 1
    assert all(t.hi - t.lo + 1 == 1 << 55 for t in tiles)


def test_tile_range_nests_levels():
    lo, hi = raw.tile_range(7, 1)
    kids = [raw.tile_range(c, 2) for c in range(28, 32)]
    assert kids[0][0] == lo and kids[-1][1] == hi
    assert all(b[0] == a[1] + 1 for a, b in zip(kids, kids[1:]))


def test_plan_tiles_counts():
    counts = {k: k + 1 for k in range(192)}
    tiles = raw.plan_tiles(counts)
    assert [t.expected_rows for t in tiles[:3]] == [1, 2, 3]
    assert raw.plan_tiles()[0].expected_rows is None
    with pytest.raises(ValueError):
        raw.plan_tiles({k: 1 for k in range(191)})


def test_load_counts_real_file():
    from milkyway.config import PROJECT_ROOT
    import os
    counts = raw.load_counts(os.path.join(PROJECT_ROOT, "docs/data/dr3_g15_hpx2_counts.csv"))
    assert len(counts) == 192 and sum(counts.values()) > 1_000_000


def test_tile_query():
    t = raw.plan_tiles()[3]
    q = raw.tile_query(t, SEL)
    assert f"source_id BETWEEN {t.lo} AND {t.hi}" in q
    assert "parallax > 0.5" in q and "phot_g_mean_mag < 15.0" in q
    where = q.split(" WHERE ")[1]
    for bad in ("ruwe", "parallax_over_error", "astrometric", "duplicated"):
        assert bad not in where
    with pytest.raises(ValueError):
        raw.tile_query(t, {"ruwe_max": 1.4})
    with pytest.raises(ValueError):
        raw.tile_query(t, SEL, columns=("source_id", "nonexistent"))


def test_verify_accepts_good():
    t = tile_of()
    raw.verify_tile(make_table(t), t, SEL)


def _bad_cases(t):
    good = make_table(t)
    return {
        "wrong type": good.set_column(1, "ra", pa.array([1.0] * 5, pa.float32())),
        "missing col": good.drop(["ra"]),
        "row count": make_table(t, n=4),
        "null source_id": make_table(t, source_id=[t.lo, None, t.lo + 2, t.lo + 3, t.lo + 4]),
        "dup source_id": make_table(t, source_id=[t.lo] * 5),
        "out of range": make_table(t, source_id=[t.lo, t.lo + 1, t.lo + 2, t.lo + 3, t.hi + 1]),
        "parallax at min": make_table(t, parallax=[0.5, 1, 2, 3, 4]),
        "null parallax": make_table(t, parallax=[None, 1, 2, 3, 4]),
        "G at max": make_table(t, phot_g_mean_mag=[15.0, 1, 2, 3, 4]),
        "null G": make_table(t, phot_g_mean_mag=[None, 1, 2, 3, 4]),
    }


def test_verify_rejects_each_violation():
    t = tile_of()
    for name, table in _bad_cases(t).items():
        with pytest.raises(raw.TileError):
            raw.verify_tile(table, t, SEL)
        # nothing may be written for a rejected table
    # and with no selection the cut checks are off
    raw.verify_tile(make_table(t, parallax=[0.1] * 5), t, {})


def test_write_tile_atomic_and_rejects(tmp_path):
    t = tile_of()
    entry = raw.write_tile(make_table(t), tmp_path, t, SEL)
    path = raw.tile_path(tmp_path, t.k)
    assert path.exists() and not list((tmp_path / "tiles").glob("*.tmp"))
    assert entry["rows"] == 5 and len(entry["sha256"]) == 64
    assert entry["path"] == "tiles/tile_005.parquet"
    other = raw.plan_tiles()[6]._replace(expected_rows=4)
    with pytest.raises(raw.TileError):
        raw.write_tile(make_table(other, n=5), tmp_path, other, SEL)
    assert not raw.tile_path(tmp_path, 6).exists()


def test_done_tiles(tmp_path):
    t = tile_of()
    raw.write_tile(make_table(t), tmp_path, t, SEL)
    (tmp_path / "tiles" / "tile_009.parquet.tmp").write_bytes(b"junk")
    assert set(raw.done_tiles(tmp_path, [t])) == {5}
    assert not list((tmp_path / "tiles").glob("*.tmp"))


def test_done_tiles_deletes_wrong_row_count(tmp_path):
    t = tile_of()
    raw.write_tile(make_table(t), tmp_path, t, SEL)
    changed = t._replace(expected_rows=6)
    assert raw.done_tiles(tmp_path, [changed]) == {}
    assert not raw.tile_path(tmp_path, 5).exists()


def _full_fetch(tmp_path, n_tiles=3):
    # a plan of the first n tiles stands in for the full set
    tiles = [raw.plan_tiles()[k]._replace(expected_rows=5) for k in range(n_tiles)]
    for t in tiles[:-1]:
        raw.write_tile(make_table(t), tmp_path, t, SEL)
    return tiles


def test_finalize_and_open(tmp_path):
    tiles = _full_fetch(tmp_path)
    with pytest.raises(raw.TileError):
        raw.finalize_fetch(tmp_path, tiles, fetch_id="x", selection=SEL, service="s")
    assert not (tmp_path / raw.FETCH_MANIFEST_NAME).exists()
    raw.write_tile(make_table(tiles[-1]), tmp_path, tiles[-1], SEL)
    m = raw.finalize_fetch(tmp_path, tiles, fetch_id="x", selection=SEL, service="s")
    assert m["status"] == "complete" and m["total_rows"] == 15
    assert json.loads((tmp_path / raw.FETCH_MANIFEST_NAME).read_text())["fetch_id"] == "x"
    assert raw.open_fetch(tmp_path, verify_hashes=True)["total_rows"] == 15
    assert [k for k, _ in raw.read_tiles(tmp_path)] == [0, 1, 2]


def test_open_fetch_detects_problems(tmp_path):
    tiles = _full_fetch(tmp_path)
    raw.write_tile(make_table(tiles[-1]), tmp_path, tiles[-1], SEL)
    raw.finalize_fetch(tmp_path, tiles, fetch_id="x", selection=SEL, service="s")

    extra = tmp_path / "tiles" / "tile_100.parquet"
    extra.write_bytes(b"x")
    with pytest.raises(raw.TileError):
        raw.open_fetch(tmp_path)
    extra.unlink()

    victim = raw.tile_path(tmp_path, 1)
    data = bytearray(victim.read_bytes())
    saved = bytes(data)
    victim.unlink()
    with pytest.raises(raw.TileError):
        raw.open_fetch(tmp_path)

    # flip a byte in the middle of the data pages: still readable footer, wrong hash
    data[len(data) // 2] ^= 0xFF
    victim.write_bytes(bytes(data))
    with pytest.raises(raw.TileError):
        raw.open_fetch(tmp_path, verify_hashes=True)
    victim.write_bytes(saved)
    raw.open_fetch(tmp_path, verify_hashes=True)
