"""Submit the `hpc/job.slurm` job from your `hpc/hpc.yaml`

  Usage:

    uv run python hpc/submit.py [--dry-run]
"""

import subprocess
import yaml
import sys
from pathlib import Path

here = Path(__file__).parent
with open(here / "hpc.yaml") as f:
  cfg = yaml.safe_load(f)
dest = f"{cfg['user']}@{cfg['host']}"
remote = cfg["remote_dir"]
dry = "--dry-run" in sys.argv

script = (here / "job.slurm.template").read_text()
for key, val in cfg.items():
    script = script.replace(f"{{{{{key}}}}}", str(val))
(here / "job.slurm").write_text(script)

ssh = ["sshpass", "-p", cfg["password"]] if cfg.get("password") else []  # prefer SSH keys
for cmd in (
    ssh + ["rsync", "-az", "--exclude-from", str(here / "rsync.exclude"), f"{here.parent}/", f"{dest}:{remote}/"],
    ssh + ["ssh", dest, f"cd {remote} && sbatch hpc/job.slurm"],
):
    print("$", " ".join("***" if a == cfg.get("password") else a for a in cmd))
    if not dry:
        subprocess.run(cmd, check=True)
