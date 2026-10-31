"""Download loop for raw Gaia tiles and the Hipparcos auxiliary tables (M2).

The contract (columns, ADQL, verification, atomic writes, manifest) is `raw.py`;
this module only moves bytes: a minimal IVOA UWS/TAP async client, a resumable
tile loop with retries, and `run_aux` for the two Hipparcos tables.

`requests` is imported here at module level; the package root never imports this
module, so the offline colour/photometry code stays dependency-free.
"""
import concurrent.futures as cf
import datetime
import io
import json
import logging
import threading
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
import requests

from . import raw
from .config import PROJECT_ROOT
from .storage import _atomic_write, _fsync, _sha256

AIP_TAP = "https://gaia.aip.de/tap"
ESA_TAP = "https://gea.esac.esa.int/tap-server/tap"
VIZIER_TAP = "https://tapvizier.cds.unistra.fr/TAPVizieR/tap"
DEFAULT_COUNTS = "docs/data/dr3_g15_hpx2_counts.csv"
RETRY_WAITS = (60, 300, 900)         # seconds before retry 1, 2, 3 of a transient failure
POLL = (2.0, 15.0)                   # polling interval grows from first to second
JOB_TIMEOUT_S = 2 * 3600
_HTTP_TIMEOUT = (30, 900)            # connect, read (a 462k-row tile downloads in ~50 s)

_log = logging.getLogger("milkyway.fetch")


class FetchError(RuntimeError):
    """The server reported ERROR/ABORTED (or gave an unusable answer); carries its text."""


class FetchTimeout(FetchError):
    """A job did not finish within the overall timeout (treated as transient)."""


def _session():
    """One HTTP session; tests replace this with a fake."""
    return requests.Session()


# A body stream cut mid-download raises these, which are not ConnectionErrors.
_STREAM_ERRORS = (requests.exceptions.ChunkedEncodingError,
                  requests.exceptions.ContentDecodingError)


def _is_transient(exc):
    if isinstance(exc, (requests.ConnectionError, requests.Timeout, FetchTimeout,
                        *_STREAM_ERRORS)):
        return True
    if isinstance(exc, requests.HTTPError):
        resp = exc.response
        return resp is not None and resp.status_code >= 500
    return isinstance(exc, pa.ArrowInvalid)        # truncated download


# --- TAP client -------------------------------------------------------------------

def submit(base, adql, *, fmt="parquet", session=None):
    """Start an async job; return its URL."""
    s = session or _session()
    r = s.post(f"{base.rstrip('/')}/async",
               data={"REQUEST": "doQuery", "LANG": "ADQL", "QUERY": adql, "QUEUE": "2h",
                     "RESPONSEFORMAT": fmt, "PHASE": "RUN"},
               allow_redirects=False, timeout=_HTTP_TIMEOUT)
    loc = r.headers.get("Location")
    if r.status_code in (301, 302, 303, 307) and loc:
        return loc
    r.raise_for_status()
    raise FetchError(f"submit: no job URL (HTTP {r.status_code}): {r.text[:300]}")


def _error_text(job_url, s):
    try:
        return s.get(f"{job_url}/error", timeout=_HTTP_TIMEOUT).text.strip()[:2000]
    except Exception as exc:                        # noqa: BLE001 - best effort
        return f"(error text unavailable: {exc})"


def wait(job_url, *, poll=POLL, timeout=JOB_TIMEOUT_S, session=None, sleep=time.sleep):
    """Block until COMPLETED; raise FetchError on ERROR/ABORTED, FetchTimeout on timeout."""
    s = session or _session()
    interval, deadline, failures = poll[0], time.monotonic() + timeout, 0
    while True:
        try:
            r = s.get(f"{job_url}/phase", timeout=_HTTP_TIMEOUT)
            r.raise_for_status()
            phase, failures = r.text.strip().upper(), 0
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError,
                *_STREAM_ERRORS):
            failures += 1
            if failures > 5:
                raise
            phase = "UNKNOWN"
        if phase == "COMPLETED":
            return
        if phase in ("ERROR", "ABORTED"):
            raise FetchError(f"job {phase}: {_error_text(job_url, s)}")
        if time.monotonic() > deadline:
            raise FetchTimeout(f"job {job_url} still {phase} after {timeout} s")
        sleep(interval)
        interval = min(poll[1], max(interval * 1.5, interval))


def result_bytes(job_url, *, session=None):
    s = session or _session()
    r = s.get(f"{job_url}/results/result", timeout=_HTTP_TIMEOUT)
    r.raise_for_status()
    return r.content


def result_table(job_url, *, fmt="parquet", session=None, column_types=None):
    """Download a finished job's result as a pyarrow Table."""
    data = result_bytes(job_url, session=session)
    if fmt == "parquet":
        return pq.read_table(io.BytesIO(data))
    if fmt == "csv":
        conv = pacsv.ConvertOptions(column_types=column_types or {})
        return pacsv.read_csv(io.BytesIO(data), convert_options=conv)
    raise ValueError(f"unsupported result format {fmt!r}")


def delete(job_url, *, session=None):
    """Delete a job; never raises."""
    try:
        (session or _session()).delete(job_url, allow_redirects=False, timeout=_HTTP_TIMEOUT)
    except Exception as exc:                        # noqa: BLE001
        _log.warning("could not delete job %s: %s", job_url, exc)


# --- tile loop --------------------------------------------------------------------

def _fetch_one(tile, fetch_dir, selection, base_url, log, retry_waits, poll, sleep):
    """Fetch one tile with retries. Returns (rows, None) or (None, error_text)."""
    transient, verify_retried = 0, False
    adql = raw.tile_query(tile, selection)
    while True:
        s, job = _session(), None
        try:
            job = submit(base_url, adql, session=s)
            log.info("tile %s submitted %s", tile.k, job)
            wait(job, poll=poll, session=s, sleep=sleep)
            table = result_table(job, session=s)
            raw.write_tile(table, fetch_dir, tile, selection)
            return table.num_rows, None
        except raw.TileError as exc:
            log.warning("tile %s verification failed: %s", tile.k, exc)
            if verify_retried:
                return None, str(exc)
            verify_retried = True
        except Exception as exc:                    # noqa: BLE001 - reported per tile
            if _is_transient(exc) and transient < len(retry_waits):
                w = retry_waits[transient]
                transient += 1
                log.warning("tile %s transient error (%r); retry %d in %s s",
                            tile.k, exc, transient, w)
                sleep(w)
            else:
                log.error("tile %s failed: %r", tile.k, exc)
                return None, f"{type(exc).__name__}: {exc}"
        finally:
            if job:
                delete(job, session=s)


def fetch_tiles(fetch_dir, tiles, *, selection=raw.DEFAULT_SELECTION, base_url=AIP_TAP,
                max_jobs=2, log=None, retry_waits=RETRY_WAITS, poll=POLL,
                sleep=time.sleep, progress=print):
    """Download the tiles not yet on disk. Returns
    {"already_done": [k], "fetched": [k], "failed": [{"tile": k, "error": str}]}."""
    log = log or _log
    fetch_dir = Path(fetch_dir)
    fetch_dir.mkdir(parents=True, exist_ok=True)
    done = raw.done_tiles(fetch_dir, tiles)
    todo = [t for t in tiles if t.k not in done]
    out = {"already_done": sorted(done), "fetched": [], "failed": []}
    log.info("fetch start: %d tiles planned, %d already done, %d to fetch",
             len(tiles), len(done), len(todo))
    lock, finished = threading.Lock(), [0]

    def work(tile):
        t0 = time.monotonic()
        rows, err = _fetch_one(tile, fetch_dir, selection, base_url, log,
                               retry_waits, poll, sleep)
        dt = time.monotonic() - t0
        with lock:
            finished[0] += 1
            if err is None:
                out["fetched"].append(tile.k)
                log.info("tile %s ok %d rows %.0f s", tile.k, rows, dt)
                line = f"tile {tile.k} ok {rows} rows {dt:.0f}s"
            else:
                out["failed"].append({"tile": tile.k, "error": err})
                line = f"tile {tile.k} FAILED ({err[:80]})"
            if progress:
                progress(f"[{finished[0]:>3}/{len(todo)}] {line}")

    with cf.ThreadPoolExecutor(max_workers=max(1, max_jobs)) as pool:
        list(pool.map(work, todo))
    out["fetched"].sort()
    out["failed"].sort(key=lambda f: f["tile"])
    return out


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def run_fetch(*, data_dir, fetch_id=raw.DEFAULT_FETCH_ID, counts_path=None,
              selection=raw.DEFAULT_SELECTION, tiles=None, base_url=AIP_TAP, max_jobs=2,
              retry_waits=RETRY_WAITS, poll=POLL, sleep=time.sleep, progress=print):
    """Fetch (or resume) a raw Gaia download under data_dir/raw/dr3/<fetch_id>."""
    counts_path = counts_path or Path(PROJECT_ROOT) / DEFAULT_COUNTS
    fetch_dir = Path(data_dir) / "raw" / raw.RELEASE / fetch_id
    if (fetch_dir / raw.FETCH_MANIFEST_NAME).exists():
        # A completed fetch is the permanent local copy: no network, nothing rewritten.
        # If it does not check out, raise (TileError) - the user decides, we never re-download.
        manifest = raw.open_fetch(fetch_dir)
        return {"fetch_id": fetch_id, "already_complete": True,
                "rows_total_on_disk": manifest["total_rows"],
                "tiles_planned": len(manifest["tiles"]), "tiles_failed": [],
                "manifest_written": False}
    fetch_dir.mkdir(parents=True, exist_ok=True)
    plan = raw.plan_tiles(raw.load_counts(counts_path))
    full = tiles is None
    if not full:
        wanted = set(tiles)
        unknown = wanted - {t.k for t in plan}
        if unknown:
            raise ValueError(f"unknown tile ids: {sorted(unknown)}")
        selected = [t for t in plan if t.k in wanted]
    else:
        selected = plan

    log = logging.getLogger(f"milkyway.fetch.run.{fetch_dir}")
    log.setLevel(logging.INFO)
    log.propagate = False
    handler = logging.FileHandler(fetch_dir / "fetch.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    started = _now()
    try:
        res = fetch_tiles(fetch_dir, selected, selection=selection, base_url=base_url,
                          max_jobs=max_jobs, log=log, retry_waits=retry_waits, poll=poll,
                          sleep=sleep, progress=progress)
        manifest_written = False
        if full and not res["failed"]:
            raw.finalize_fetch(fetch_dir, plan, fetch_id=fetch_id, selection=selection,
                               service=base_url,
                               notes={"counts_file": Path(counts_path).name,
                                      "counts_sha256": _sha256(counts_path)})
            manifest_written = True
        on_disk = raw.done_tiles(fetch_dir, selected)
        finished = _now()
        summary = {
            "fetch_id": fetch_id,
            "started_utc": started.isoformat(timespec="seconds"),
            "finished_utc": finished.isoformat(timespec="seconds"),
            "elapsed_s": round((finished - started).total_seconds(), 1),
            "tiles_planned": len(selected),
            "tiles_done_before": len(res["already_done"]),
            "tiles_fetched_now": len(res["fetched"]),
            "tiles_failed": res["failed"],
            "rows_total_on_disk": sum(e["rows"] for e in on_disk.values()),
            "bytes_on_disk": sum(raw.tile_path(fetch_dir, k).stat().st_size for k in on_disk),
            "manifest_written": manifest_written,
        }
        _atomic_write(fetch_dir / "fetch_summary.json", json.dumps(summary, indent=1).encode())
        log.info("fetch end: %s", json.dumps(summary))
        return summary
    finally:
        log.removeHandler(handler)
        handler.close()


# --- auxiliary datasets (Hipparcos) ------------------------------------------------

HIP2_QUERY = (
    "SELECT b.original_ext_source_id AS hip, b.source_id, b.angular_distance, "
    "b.number_of_neighbours, g.parallax, g.parallax_error, g.phot_g_mean_mag, g.bp_rp, "
    "g.astrometric_params_solved, g.ra, g.dec "
    "FROM gaiadr3.hipparcos2_best_neighbour AS b "
    "JOIN gaiadr3.gaia_source AS g ON g.source_id = b.source_id")
HIPPARCOS_ESA_QUERY = ("SELECT hip, ra, de, plx, e_plx, pmra, pmde, vmag, b_v, v_i "
                       "FROM public.hipparcos")
HIPPARCOS_VIZIER_QUERY = (
    'SELECT HIP AS hip, RAICRS AS ra, DEICRS AS de, Plx AS plx, e_Plx AS e_plx, '
    'pmRA AS pmra, pmDE AS pmde, Vmag AS vmag, "B-V" AS b_v, "V-I" AS v_i '
    'FROM "I/239/hip_main"')
_HIP_TYPES = {"hip": pa.int32(), **{c: pa.float64() for c in
              ("ra", "de", "plx", "e_plx", "pmra", "pmde", "vmag", "b_v", "v_i")}}


def _run_job(base, adql, fmt, column_types=None, log=_log):
    s = _session()
    job = submit(base, adql, fmt=fmt, session=s)
    try:
        wait(job, session=s)
        return result_table(job, fmt=fmt, session=s, column_types=column_types)
    finally:
        delete(job, session=s)


def _check_aux(table, name):
    problems = []
    if name == "hip2_best_neighbour":
        if table.num_rows <= 90_000:
            problems.append(f"only {table.num_rows} rows")
        for c in ("hip", "source_id"):
            if table[c].null_count:
                problems.append(f"null {c}")
        if len(table["source_id"].unique()) != table.num_rows:
            problems.append("duplicate source_id")
    else:
        if not 118_000 <= table.num_rows <= 118_300:
            problems.append(f"{table.num_rows} rows, expected 118000..118300")
        if table["hip"].null_count:
            problems.append("null hip")
        if len(table["hip"].unique()) != table.num_rows:
            problems.append("duplicate hip")
    if problems:
        raise raw.TileError(f"aux {name}: " + "; ".join(problems))


def _write_aux(table, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    pq.write_table(table.replace_schema_metadata(None), tmp, compression="zstd",
                   compression_level=3)
    _fsync(tmp)
    tmp.replace(path)


def _sync_csv(base, adql):
    """One synchronous TAP query returning CSV, as a Table typed by _HIP_TYPES."""
    r = _session().post(f"{base.rstrip('/')}/sync",
                        data={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv",
                              "QUERY": adql}, timeout=(30, 600))
    r.raise_for_status()
    return pacsv.read_csv(io.BytesIO(r.content),
                          convert_options=pacsv.ConvertOptions(column_types=_HIP_TYPES))


def _fetch_hipparcos(attempts=((ESA_TAP, HIPPARCOS_ESA_QUERY), (VIZIER_TAP, HIPPARCOS_VIZIER_QUERY))):
    errors = []
    for base, adql in attempts:
        try:
            if base == ESA_TAP:
                # ESA anonymous limits: async jobs die at 60 s, but every query here takes
                # ~75 s (table scan), so use /sync (longer limit); sync returns at most
                # 50 000 rows, so fetch 4 hip ranges of ~30 000 rows and concatenate.
                parts = []
                for lo in range(0, 120_000, 30_000):
                    part = _sync_csv(base, f"{adql} WHERE hip >= {lo} AND hip < {lo + 30_000}")
                    if part.num_rows >= 50_000:
                        raise FetchError("ESA row cap hit; chunk too large")
                    parts.append(part)
                t = pa.concat_tables(parts)
                adql = f"{adql} WHERE hip >= a AND hip < a+30000  (a = 0, 30000, 60000, 90000)"
            else:
                t = _run_job(base, adql, "csv", column_types=_HIP_TYPES)
            t = t.select(list(_HIP_TYPES)).cast(pa.schema(list(_HIP_TYPES.items())))
            _check_aux(t, "hipparcos")
            return t, base, adql
        except Exception as exc:                    # noqa: BLE001 - fall back to next service
            errors.append(f"{base}: {exc!r}")
            _log.warning("hipparcos from %s failed: %r", base, exc)
    raise FetchError("Hipparcos unavailable: " + " | ".join(errors))


def _aux_complete(aux_dir):
    """The aux manifest if every listed file is present with a matching SHA-256, else None."""
    path = aux_dir / "aux_manifest.json"
    if not path.exists():
        return None
    manifest = json.loads(path.read_text())
    files = manifest.get("files") or {}
    ok = bool(files) and all((aux_dir / n).exists() and _sha256(aux_dir / n) == e["sha256"]
                             for n, e in files.items())
    return manifest if ok else None


def run_aux(*, data_dir, base_url=AIP_TAP, progress=print):
    """Fetch hip2_best_neighbour and hipparcos into data_dir/raw/dr3/aux/."""
    aux_dir = Path(data_dir) / "raw" / raw.RELEASE / "aux"
    done = _aux_complete(aux_dir)
    if done:
        if progress:
            progress(f"aux already complete ({', '.join(done['files'])}); nothing to download. "
                     f"Delete {aux_dir} to fetch again.")
        return {**done, "already_complete": True}
    aux_dir.mkdir(parents=True, exist_ok=True)
    files = {}

    t = _run_job(base_url, HIP2_QUERY, "parquet")
    _check_aux(t, "hip2_best_neighbour")
    files["hip2_best_neighbour.parquet"] = (t, base_url, HIP2_QUERY)
    if progress:
        progress(f"hip2_best_neighbour: {t.num_rows} rows")

    t, svc, adql = _fetch_hipparcos()
    files["hipparcos.parquet"] = (t, svc, adql)
    if progress:
        progress(f"hipparcos: {t.num_rows} rows from {svc}")

    manifest = {"created_utc": _now().isoformat(timespec="seconds"), "files": {}}
    for name, (table, service, query) in files.items():
        _write_aux(table, aux_dir / name)
        manifest["files"][name] = {"rows": table.num_rows, "sha256": _sha256(aux_dir / name),
                                   "service": service, "query": query,
                                   "columns": {f.name: str(f.type) for f in table.schema}}
    _atomic_write(aux_dir / "aux_manifest.json", json.dumps(manifest, indent=1).encode())
    return manifest
