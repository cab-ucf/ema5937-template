# This python image is based on debian-slim
# Move up from smallest to largest to use minimal resources necessary:
# busybox -> alpine -> debian (if gcc needed) -> ubuntu (for gpu / cuda drivers)
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ARG TYPST_VERSION=v0.13.1

# Get dependencies: typst and cargo
RUN apt-get update \
 && apt-get install -y --no-install-recommends make curl ca-certificates xz-utils build-essential pkg-config \
 && rm -rf /var/lib/apt/lists/* \
 && arch="$(uname -m)" \
 && curl -fsSL "https://github.com/typst/typst/releases/download/${TYPST_VERSION}/typst-${arch}-unknown-linux-musl.tar.xz" \
    | tar -xJ --strip-components=1 -C /usr/local/bin "typst-${arch}-unknown-linux-musl/typst" \
 && typst --version \
 && curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /work
