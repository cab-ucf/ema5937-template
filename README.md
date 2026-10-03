# EMA 5937 template

```
just  →  podman  →  make  →  uv run mseml.etl → mseml.analysis  →  typst  →  report/main.pdf
```

| File | Description |
|------|------|
| `Makefile`              | orchestrates report & analysis |
| `schema.sql`            | The database: `plate`, `spectrum`, `line`, `line_fit` tables |
| `src/mseml/etl.py`      | Downloads SDSS plates (slowly - no ddos), writes parquets (zstd), shares over irohds, loads `data/dataset.db` |
| `src/mseml/analysis.py` | PCA, LDA, SVC, MLP, Balmer lines -> `figures/*.png` & `results/results.json` |
| `report/main.typ`       | Idempotent Typst pdf |

```bash
just                              # containerized build of report/main.pdf
make all                          # same, but on host (deps: uv, make, typst, cargo)
make all CONFIG=config.hpc.yaml   # pulls all data (`just hpc` also submits this to slurm)
```

## Data

SDSS eBOSS optical spectra: one plate holds up to 1000 spectra, each labelled
STAR/GALAXY/QSO with a redshift by the SDSS pipeline.

| table      | one row per | holds |
|------------|-------------|-------|
| `plate`    | plate       | wavelength grid of its spectra |
| `spectrum` | spectrum    | class, redshift, flux (3800 pixels) |
| `line`     | Balmer line | rest wavelength: Rydberg formula (theory) and NIST (lab) |
| `line_fit` | line found in a galaxy | observed wavelength and the redshift it implies |

`plates: 16` (~60 MB, ~1000 spectra each, ~1 GB total) locally, `null` (all) in
`config.hpc.yaml`. No API keys. Each plate is fetched once by whoever asks first
and thereafter served peer-to-peer within the irohds namespace (`MSEML_NS`), so
the origin sees a single crawl.

## Report

`report/main.typ` reads `results/results.json` and `figures/`, so just write the text.

## Notes

- irohds ships wheels for macOS/aarch64 Linux; on x86_64 Linux `uv sync` compiles
  its Rust daemon (the Containerfile and Slurm template install rustup).
- The full SDSS matrix is large (~80 GB parquet, 4M * 3800 float32). Use a
  large-memory node, or bin pixels in `plate_spectra`.
