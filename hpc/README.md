# HPC

```bash
cp hpc/hpc.yaml.example hpc/hpc.yaml   # Copy and then edit `hpc/hpc.yaml` to fill out your host/user/partition (`hpc/hpc.yaml` is gitignored due to secrets)
just hpc --dry-run                     # Check to ensure job can make it to server
just hpc                               # Send the repo by rsync then do `sbatch hpc/job.slurm`
```

The job within the `hpc/job.slurm` will run `make all CONFIG=config.hpc.yaml`.

Your results can be retrieved with `rsync -azvP user@host:remote_dir/{figures,results,report} .`

If compute nodes block P2P traffic, run `make data/dataset.parquet CONFIG=config.hpc.yaml`
elsewhere first so irohds can fetch from there
