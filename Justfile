default:
    podman run --rm -v .:/work -w /work $(podman build -q .) make all

hpc *ARGS:
    uv run python hpc/submit.py {{ARGS}}
