"""Fetch shards politely, once, into one parquet schema; share them over irohds.

    id | label | target | f0 .. fN        (features are float32)

SDSS  [sdss_dr17]: label = CLASS, target = redshift,
                   features = flux on a fixed log-wavelength grid.
AFLOW [aflow2022, rose2017aflux]: one page per iroh doc. label = Egap_type,
                   target = formation enthalpy/atom, features = element fractions + cell scalars.

    uv run python -m mseml.etl config.yaml data/dataset.parquet

Each shard function is decorated with `@irohds.memo(ns=NS)`: the first machine
to compute a shard stores it and announces it; every other machine in the
namespace downloads it instead.  Set MSEML_NS to change the namespace.
"""

import itertools
import json
import os
import sys
import time
from pathlib import Path

import irohds
import numpy as np
import pandas as pd
import requests
import yaml
from astropy.io import fits
from mendeleev import element

NS = os.environ.get("MSEML_NS", "mseml")
PAUSE = 1.0  # seconds between remote requests: one slow client, never parallel
SDSS = "https://data.sdss.org/sas/dr17/eboss/spectro/redux"
AFLUX = "https://aflow.org/API/aflux/?"
AFLOW_KEYS = ("auid,species,stoichiometry,nspecies,natoms,enthalpy_formation_atom,"
              "Egap_type,spacegroup_relax,density,volume_atom,spin_atom")
AFLOW_SCALARS = ["nspecies", "natoms", "spacegroup_relax", "density", "volume_atom", "spin_atom"]
ELEMENTS = [e.symbol for e in element(list(range(1, 95)))]


# --- transport -----------------------------------------------------------------

def get(url: str) -> bytes:
    """Paced GET with exponential backoff on transient errors."""
    for attempt in range(6):
        time.sleep(PAUSE * 2**attempt)
        r = requests.get(url, timeout=120)
        if r.ok:
            return r.content
        if r.status_code not in (429, 500, 502, 503, 504):
            r.raise_for_status()
    raise RuntimeError(f"gave up: {url}")


def open_fits(url: str) -> fits.HDUList:
    """Lazy FITS over HTTP range requests: only the HDUs we touch are transferred."""
    time.sleep(PAUSE)
    return fits.open(url, use_fsspec=True)


def save(rel: str, ids, labels, targets, X) -> irohds.FileRef:
    """Write one shard as zstd parquet inside the irohds data dir; return its FileRef."""
    X = np.asarray(X, np.float32)
    df = pd.DataFrame({"id": ids, "label": labels, "target": targets})
    df[[f"f{i}" for i in range(X.shape[1])]] = X
    path = Path(irohds.resolve(rel))
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="zstd", index=False)
    return irohds.FileRef(rel)


# --- memoization --------------------------------------------------

@irohds.memo(ns=NS)
def sdss_plates(run2d: str) -> list[tuple[int, int]]:
    with open_fits(f"{SDSS}/{run2d}/platelist.fits") as h:
        t = h[1].data
    good = np.char.strip(t["PLATEQUALITY"].astype(str)) == "good"
    return sorted(zip(t["PLATE"][good].tolist(), t["MJD"][good].tolist()))


@irohds.memo(ns=NS)
def sdss_shard(plate: int, mjd: int, run2d: str, lo: float, hi: float) -> irohds.FileRef:
    base = f"{SDSS}/{run2d}/{plate}"
    with open_fits(f"{base}/spPlate-{plate}-{mjd}.fits") as h:
        c0, c1 = h[0].header["COEFF0"], h[0].header["COEFF1"]  # log10(lambda) = c0 + c1 * pixel
        i0 = round((lo - c0) / c1)
        flux = h[0].section[:, i0 : i0 + round((hi - lo) / c1)]
    with open_fits(f"{base}/{run2d}/spZbest-{plate}-{mjd}.fits") as h:
        z = h[1].data
    ok = (z["ZWARNING"] == 0) & np.isfinite(flux).all(axis=1)
    ids = [f"{plate}-{mjd}-{f}" for f in z["FIBERID"][ok]]
    labels = np.char.strip(z["CLASS"][ok].astype(str))
    return save(f"sdss/{run2d}/{plate}-{mjd}.parquet", ids, labels, z["Z"][ok].astype(float), flux[ok])


@irohds.memo(ns=NS)
def aflow_shard(catalogs: tuple, page: int) -> irohds.FileRef | None:
    """AFLUX page of 1000 entries, sorted by auid (stable); None once exhausted."""
    rows = json.loads(get(f"{AFLUX}catalog({':'.join(catalogs)}),{AFLOW_KEYS},$paging({page},1000)"))
    if not rows:
        return None
    d = pd.DataFrame(rows).dropna(subset=["enthalpy_formation_atom", "Egap_type"])
    comp = np.zeros((len(d), len(ELEMENTS)), np.float32)
    for i, (species, fracs) in enumerate(zip(d["species"], d["stoichiometry"])):
        comp[i, [ELEMENTS.index(s) for s in species]] = fracs
    X = np.hstack([comp, d[AFLOW_SCALARS].to_numpy(np.float32)])
    labels = d["Egap_type"].str.replace("_spin-polarized", "").tolist()
    return save(f"aflow/{'-'.join(catalogs)}/page{page:05d}.parquet",
                d["auid"].tolist(), labels, d["enthalpy_formation_atom"].astype(float).tolist(), X)


# --- driver --------------------------------------------------------------------

def shards(cfg: dict):
    """Yield FileRefs for the configured source until exhausted."""
    if cfg["source"] == "sdss":
        s = cfg["sdss"]
        for plate, mjd in sdss_plates(s["run2d"]):
            yield sdss_shard(plate, mjd, s["run2d"], *s["loglam"])
    else:
        catalogs = tuple(cfg["aflow"]["catalogs"])
        for page in itertools.count(1):
            ref = aflow_shard(catalogs, page)
            if ref is None:
                return
            yield ref


def main(config: str, out: str) -> None:
    cfg = yaml.safe_load(open(config))
    refs = itertools.islice(shards(cfg), cfg.get("shards"))  # None = no cap
    df = pd.concat([pd.read_parquet(r.path) for r in refs], ignore_index=True)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, compression="zstd", index=False)
    print(f"[etl] {cfg['source']}: {len(df)} rows x {df.shape[1] - 3} features -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:])
