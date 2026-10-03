"""Fetch SDSS plates politely, once; share them over irohds; load into DuckDB.

    plate | spectrum | line | line_fit        (see schema.sql)

SDSS [sdss_dr17]: one plate = up to 1000 spectra, each with the pipeline's
class (STAR/GALAXY/QSO) and redshift z. Flux is cut to a fixed log-wavelength window.
Balmer lines [nist_asd]: rest wavelengths from the Rydberg formula (theory) and
the lab (NIST), plus where each line is found in every galaxy spectrum (extraction).

    uv run python -m mseml.etl config.yaml data/dataset.db

Each plate function is decorated with `@irohds.memo(ns=NS)`: the first machine
to compute a plate stores it and announces it; every other machine in the
namespace downloads it instead.  Set MSEML_NS to change the namespace.
"""

import itertools
import os
import sys
import time
from pathlib import Path

import duckdb
import irohds
import numpy as np
import pandas as pd
import yaml
from astropy.io import fits
from scipy.constants import Rydberg, m_e, m_p

NS = os.environ.get("MSEML_NS", "mseml")
PAUSE = 1.0  # seconds between remote requests: one slow client, never parallel
SDSS = "https://data.sdss.org/sas/dr17/eboss/spectro/redux"
# Balmer lines: upper level n, lab (NIST) vacuum wavelength in Angstrom
BALMER = {"Halpha": (3, 6564.61), "Hbeta": (4, 4862.68), "Hgamma": (5, 4341.68)}


# --- transport -----------------------------------------------------------------

def open_fits(url: str) -> fits.HDUList:
    """Lazy FITS over HTTP range requests: only the HDUs we touch are transferred."""
    time.sleep(PAUSE)
    return fits.open(url, use_fsspec=True)


def save(rel: str, df: pd.DataFrame) -> irohds.FileRef:
    """Write one plate as zstd parquet inside the irohds data dir; return its FileRef."""
    path = Path(irohds.resolve(rel))
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="zstd", index=False)
    return irohds.FileRef(rel)


# --- memoization --------------------------------------------------

@irohds.memo(ns=NS)
def good_plates(run2d: str) -> list[tuple[int, int]]:
    with open_fits(f"{SDSS}/{run2d}/platelist.fits") as h:
        t = h[1].data
    good = np.char.strip(t["PLATEQUALITY"].astype(str)) == "good"
    return sorted(zip(t["PLATE"][good].tolist(), t["MJD"][good].tolist()))


@irohds.memo(ns=NS)
def plate_spectra(plate: int, mjd: int, run2d: str, lo: float, hi: float) -> irohds.FileRef:
    base = f"{SDSS}/{run2d}/{plate}"
    with open_fits(f"{base}/spPlate-{plate}-{mjd}.fits") as h:
        c0, c1 = h[0].header["COEFF0"], h[0].header["COEFF1"]  # log10(lambda) = c0 + c1 * pixel
        i0 = round((lo - c0) / c1)
        flux = h[0].section[:, i0 : i0 + round((hi - lo) / c1)]
    with open_fits(f"{base}/{run2d}/spZbest-{plate}-{mjd}.fits") as h:
        z = h[1].data
    ok = (z["ZWARNING"] == 0) & np.isfinite(flux).all(axis=1)
    return save(f"data/sdss/{run2d}/{plate}-{mjd}.parquet", pd.DataFrame({
        "plate": plate, "mjd": mjd, "fiber": z["FIBERID"][ok].astype(int),
        "class": np.char.strip(z["CLASS"][ok].astype(str)), "z": z["Z"][ok].astype(float),
        "loglam0": c0 + c1 * i0, "dloglam": c1, "flux": list(flux[ok].astype(np.float32))}))


# --- theory & extraction -------------------------------------------------------

def balmer() -> list[tuple]:
    """Rydberg formula with hydrogen's reduced mass: 1/lambda = R_H (1/2^2 - 1/n^2)."""
    R_H = Rydberg / (1 + m_e / m_p)  # CODATA constants from scipy, in 1/m
    return [(k, n, 1e10 / (R_H * (1 / 4 - 1 / n**2)), lab) for k, (n, lab) in BALMER.items()]


def fit_lines(d: pd.DataFrame) -> list[tuple]:
    """Find each Balmer line near where the pipeline z puts it; keep 5-sigma detections."""
    rows = []
    for r in d[d["class"] == "GALAXY"].itertuples():
        lam = 10 ** (r.loglam0 + r.dloglam * np.arange(len(r.flux)))
        for name, (_, rest) in BALMER.items():
            dist = abs(lam - rest * (1 + r.z))           # Angstrom from the expected spot
            near, side = dist < 8, (dist > 20) & (dist < 60)
            if near.sum() < 5 or side.sum() < 20:
                continue                                 # line falls outside the spectrum
            excess = r.flux[near] - np.median(r.flux[side])  # line above the continuum
            if excess.max() < 5 * r.flux[side].std():
                continue                                 # too weak to measure
            w = np.clip(excess, 0, None)
            obs = (lam[near] * w).sum() / w.sum()        # flux-weighted centroid
            rows.append((r.plate, r.mjd, r.fiber, name, obs, obs / rest - 1))
    return rows


# --- driver --------------------------------------------------------------------

def main(config: str, out: str) -> None:
    cfg = yaml.safe_load(open(config))
    s = cfg["sdss"]
    plates = itertools.islice(good_plates(s["run2d"]), cfg.get("plates"))  # None = all
    paths = [plate_spectra(p, m, s["run2d"], *s["loglam"]).path for p, m in plates]

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).unlink(missing_ok=True)  # rebuild from scratch: same inputs -> same database
    db = duckdb.connect(out)
    db.execute(Path("schema.sql").read_text())
    q = f"FROM read_parquet({[str(p) for p in paths]})"
    db.execute(f"INSERT INTO plate SELECT DISTINCT plate, mjd, loglam0, dloglam {q} ORDER BY ALL")
    db.execute(f"INSERT INTO spectrum SELECT plate, mjd, fiber, class, z, flux {q} "
               "ORDER BY plate, mjd, fiber")
    db.executemany("INSERT INTO line VALUES (?, ?, ?, ?)", balmer())
    found = pd.DataFrame([f for p in paths for f in fit_lines(pd.read_parquet(p))],
                         columns=["plate", "mjd", "fiber", "line", "lambda_obs", "z_line"])
    db.execute("INSERT INTO line_fit SELECT * FROM found ORDER BY ALL")  # DuckDB reads `found`
    n = db.sql("SELECT (FROM spectrum SELECT count(*)), (FROM line_fit SELECT count(*))").fetchone()
    print(f"[etl] {len(paths)} plates: {n[0]} spectra, {n[1]} line fits -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:])
