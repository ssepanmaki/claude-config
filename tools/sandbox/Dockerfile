FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl git python3 ripgrep \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/bash dev
USER dev
RUN curl -m 120 -fsSL https://claude.ai/install.sh | bash
ENV PATH=/home/dev/.local/bin:$PATH
WORKDIR /work
ENTRYPOINT ["claude"]
