# Development image for humanauthn-python-sdk.
# Pins Python 3.14 (the Current release line) via the official slim image so
# Cloud Agents develop against the same toolchain as .python-version.
FROM python:3.14-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Official uv installer; place the binary on the default PATH for every user.
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

# python:3.14-slim has no non-root user; Cloud Agents expect `ubuntu`.
RUN useradd --create-home --shell /bin/bash --uid 1000 ubuntu

USER ubuntu
