"""Download loop against a fake TAP service (no network)."""
import io
import json
import re

import pyarrow.parquet as pq
import pytest
import requests

from milkyway import cli, fetch, raw
from .test_raw import make_table

BASE = "https://fake.example/tap"
NOSLEEP = dict(retry_waits=(0, 0, 0), poll=(0, 0), sleep=lambda s: None, progress=None)
ROWS = 3


def resp(status=200, text="", content=b"", headers=None):
    r = requests.Response()
    r.status_code = status
    r._content = content or text.encode()
    r.headers.update(headers or {})
    r.url = BASE
    return r


class FakeTAP:
    """Stands in for requests.Session; behaviour is scripted per tile."""

    def __init__(self):
        self.jobs, self.deleted, self.submits = {}, [], []
        self.post_failures = {}     # tile -> [status, ...] consumed on submit
        self.rows = {}              # tile -> row count of the returned table
        self.phase_script = {}      # tile -> final phase (default COMPLETED)
        self.tiles = {t.k: t for t in raw.plan_tiles()}

    def post(self, url, data=None, allow_redirects=True, timeout=None):
        assert allow_redirects is False and data["RESPONSEFORMAT"] == "parquet"
        k = int(re.search(r"BETWEEN (\d+) AND", data["QUERY"]).group(1)) >> 55
        self.submits.append(k)
        if self.post_failures.get(k):
            return resp(self.post_failures[k].pop(0))
        job = f"{BASE}/async/{len(self.jobs)}"
        self.jobs[job] = k
        return resp(303, headers={"Location": job})

    def get(self, url, timeout=None):
        job, _, what = url.partition("/async/")[2].partition("/")
        k = self.jobs[f"{BASE}/async/{job}"]
        if what == "phase":
            return resp(text=self.phase_script.get(k, "COMPLETED"))
        if what == "error":
            return resp(text="boom: bad query")
        assert what == "results/result"
        buf = io.BytesIO()
        pq.write_table(make_table(self.tiles[k], n=self.rows.get(k, ROWS)), buf)
        return resp(content=buf.getvalue())

    def delete(self, url, allow_redirects=True, timeout=None):
        self.deleted.append(url)
        return resp(303)


@pytest.fixture
def tap(monkeypatch):
    fake = FakeTAP()
    monkeypatch.setattr(fetch, "_session", lambda: fake)
    return fake


@pytest.fixture
def counts(tmp_path):
    p = tmp_path / "counts.csv"
    p.write_text("hpx2,n\n" + "".join(f"{k},{ROWS}\n" for k in range(192)))
    return p


def run(tmp_path, counts, **kw):
    return fetch.run_fetch(data_dir=tmp_path / "data", counts_path=counts, base_url=BASE,
                           **{**NOSLEEP, **kw})


def fdir(tmp_path):
    return tmp_path / "data" / "raw" / "dr3" / raw.DEFAULT_FETCH_ID


def test_full_success(tmp_path, tap, counts):
    s = run(tmp_path, counts)
    assert s["tiles_planned"] == 192 and s["tiles_fetched_now"] == 192
    assert s["tiles_done_before"] == 0 and s["tiles_failed"] == []
    assert s["rows_total_on_disk"] == 192 * ROWS and s["bytes_on_disk"] > 0
    assert s["manifest_written"] is True
    assert len(tap.deleted) == 192 == len(set(tap.deleted))
    d = fdir(tmp_path)
    assert raw.open_fetch(d, verify_hashes=True)["service"] == BASE
    on_disk = json.loads((d / "fetch_summary.json").read_text())
    assert on_disk == s
    assert set(on_disk) == {"fetch_id", "started_utc", "finished_utc", "elapsed_s",
                            "tiles_planned", "tiles_done_before", "tiles_fetched_now",
                            "tiles_failed", "rows_total_on_disk", "bytes_on_disk",
                            "manifest_written"}
    assert "tile 7 ok" in (d / "fetch.log").read_text()


def test_retry_after_503(tmp_path, tap, counts):
    tap.post_failures[7] = [503]
    slept = []
    s = run(tmp_path, counts, tiles=[7, 8], sleep=slept.append)
    assert s["tiles_failed"] == [] and s["tiles_fetched_now"] == 2
    assert tap.submits.count(7) == 2 and slept == [0]
    assert s["manifest_written"] is False                 # pilot: never a manifest
    assert not (fdir(tmp_path) / raw.FETCH_MANIFEST_NAME).exists()


def test_503_forever_fails_after_three_retries(tmp_path, tap, counts):
    tap.post_failures[2] = [503] * 10
    s = run(tmp_path, counts, tiles=[2])
    assert tap.submits.count(2) == 4
    assert [f["tile"] for f in s["tiles_failed"]] == [2]
    assert not raw.tile_path(fdir(tmp_path), 2).exists()


def test_verification_failure_retried_once_then_failed(tmp_path, tap, counts):
    tap.rows[9] = ROWS - 1
    s = run(tmp_path, counts)
    assert tap.submits.count(9) == 2
    assert [f["tile"] for f in s["tiles_failed"]] == [9]
    assert "expected" in s["tiles_failed"][0]["error"]
    assert not raw.tile_path(fdir(tmp_path), 9).exists()
    assert s["manifest_written"] is False
    assert not (fdir(tmp_path) / raw.FETCH_MANIFEST_NAME).exists()
    assert len(tap.deleted) == len(tap.submits)           # every job deleted, also failures
    assert s["tiles_fetched_now"] == 191

    # resume: only the missing tile is fetched, then the manifest appears
    tap.rows.clear()
    tap.submits.clear()
    s2 = run(tmp_path, counts)
    assert tap.submits == [9]
    assert s2["tiles_done_before"] == 191 and s2["tiles_fetched_now"] == 1
    assert s2["manifest_written"] is True
    raw.open_fetch(fdir(tmp_path))


def test_server_error_reports_text_and_deletes(tmp_path, tap, counts):
    tap.phase_script[4] = "ERROR"
    s = run(tmp_path, counts, tiles=[4])
    assert "boom: bad query" in s["tiles_failed"][0]["error"]
    assert tap.submits.count(4) == 1 and len(tap.deleted) == 1


def test_wait_raises_fetch_error(tap):
    job = fetch.submit(BASE, "SELECT 1 /*BETWEEN 0 AND 1*/", session=tap)
    tap.phase_script[0] = "ABORTED"
    with pytest.raises(fetch.FetchError, match="boom"):
        fetch.wait(job, poll=(0, 0), session=tap, sleep=lambda s: None)


def test_wait_timeout(tap):
    job = fetch.submit(BASE, "SELECT 1 /*BETWEEN 0 AND 1*/", session=tap)
    tap.phase_script[0] = "EXECUTING"
    with pytest.raises(fetch.FetchTimeout):
        fetch.wait(job, poll=(0, 0), timeout=-1, session=tap, sleep=lambda s: None)


def test_unknown_tile_rejected(tmp_path, tap, counts):
    with pytest.raises(ValueError):
        run(tmp_path, counts, tiles=[500])


@pytest.mark.parametrize("argv", [
    ["--fetch", "--plot-only"],
    ["--fetch", "--to-parquet", "x.csv"],
    ["--fetch-aux", "--dataset", "x"],
    ["--fetch", "--max-jobs", "0"],
    ["--fetch", "--max-jobs", "5"],
    ["--fetch", "--fetch-id", "bad/id"],
    ["--fetch", "--fetch-id", "reference"],
    ["--fetch-id", "ok"],
    ["--fetch-tiles", "a,b"],
    ["--fetch-tiles", "192"],
    ["--fetch-aux", "--fetch"],
])
def test_cli_rejects(argv):
    with pytest.raises(SystemExit) as e:
        cli.main(argv)
    assert e.value.code == 2


def test_cli_dispatch_and_exit_code(monkeypatch, tmp_path):
    seen = {}

    def fake_run(**kw):
        seen.update(kw)
        return {"fetch_id": kw["fetch_id"], "tiles_fetched_now": 1, "tiles_done_before": 0,
                "tiles_planned": 2, "tiles_failed": [{"tile": 112, "error": "x"}],
                "rows_total_on_disk": 5, "bytes_on_disk": 10, "elapsed_s": 1.0,
                "manifest_written": False}

    monkeypatch.setattr(fetch, "run_fetch", fake_run)
    rc = cli.main(["--fetch-tiles", "112,111", "--fetch-id", "t1", "--max-jobs", "3",
                   "--data-dir", str(tmp_path)])
    assert rc == 1
    assert seen["tiles"] == [111, 112] and seen["fetch_id"] == "t1" and seen["max_jobs"] == 3
    monkeypatch.setattr(fetch, "run_fetch", lambda **kw: {**fake_run(**kw), "tiles_failed": []})
    assert cli.main(["--fetch", "--data-dir", str(tmp_path)]) == 0
    assert seen["tiles"] is None and seen["fetch_id"] == raw.DEFAULT_FETCH_ID


def test_complete_fetch_makes_no_http_calls(tmp_path, tap, counts, monkeypatch):
    run(tmp_path, counts)
    def boom():
        raise AssertionError("network touched")
    monkeypatch.setattr(fetch, "_session", boom)
    before = (fdir(tmp_path) / "fetch_summary.json").read_bytes()
    s = run(tmp_path, counts)
    assert s["already_complete"] and s["rows_total_on_disk"] == 192 * ROWS
    assert (fdir(tmp_path) / "fetch_summary.json").read_bytes() == before
    assert cli.main(["--fetch", "--data-dir", str(tmp_path / "data")]) == 0


def test_broken_complete_fetch_errors_without_download(tmp_path, tap, counts, monkeypatch):
    run(tmp_path, counts)
    raw.tile_path(fdir(tmp_path), 5).unlink()
    monkeypatch.setattr(fetch, "_session", lambda: pytest.fail("network touched"))
    with pytest.raises(raw.TileError):
        run(tmp_path, counts)
    assert cli.main(["--fetch", "--data-dir", str(tmp_path / "data")]) == 1


def test_run_aux_skips_when_complete(tmp_path, monkeypatch):
    aux = tmp_path / "raw" / "dr3" / "aux"
    aux.mkdir(parents=True)
    (aux / "a.parquet").write_bytes(b"abc")
    import hashlib
    sha = hashlib.sha256(b"abc").hexdigest()
    (aux / "aux_manifest.json").write_text(json.dumps({"files": {"a.parquet": {"sha256": sha}}}))
    monkeypatch.setattr(fetch, "_session", lambda: pytest.fail("network touched"))
    assert fetch.run_aux(data_dir=tmp_path, progress=None)["already_complete"]
    assert cli.main(["--fetch-aux", "--data-dir", str(tmp_path)]) == 0
