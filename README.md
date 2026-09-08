# EMA 5937 template

```
just  →  podman  →  make  →  uv run mseml.etl → mseml.analysis  →  typst  →  report/main.pdf
```

| File | Description |
|------|------|
| `Makefile`              | orchestrates report & analysis |
| `src/mseml/etl.py`      | Downloads data (slowly - no ddos), writes parquets (zstd), shares over irohds, concatenates into `data/dataset.parquet` |
| `src/mseml/analysis.py` | PCA, LDA, SVC, MLP -> `figures/*.png` & `results/results.json` |
| `report/main.typ`       | Idempotent Typst pdf |

```bash
just                              # containerized build of report/main.pdf
make all                          # same, but on host (deps: uv, make, typst, cargo)
make all CONFIG=config.hpc.yaml   # pulls all data (`just hpc` also submits this to slurm)
```

## Data

`config.yaml` picks one of two sources (sdss or aflow).
Both make same `id | label | target | f0..fN` schema.

| source  | rows * features | label, target |
|---------|-----------------|----------------|
| `sdss`  | ~4 million  spectra * 3800 pixels | STAR/GALAXY/QSO, redshift |
| `aflow` | ~60,000 ICSD | `Egap_type`, formation enthalpy/atom |

`shards: 3` locally, `null` (all) in `config.hpc.yaml`. No API keys. Each shard
is fetched once by whoever asks first and thereafter served peer-to-peer within
the irohds `namespace`, so the origin sees a single crawl.

## Report

`report/main.typ` reads `results/results.json` and `figures/`, so just write the text.

## Notes

- irohds ships wheels for macOS/aarch64 Linux; on x86_64 Linux `uv sync` compiles
  its Rust daemon (the Containerfile and Slurm template install rustup).
- The full SDSS matrix is large (~80 GB parquet, 4M * 3800 float32). Use a
  large-memory node, or bin pixels in `sdss_shard`.
