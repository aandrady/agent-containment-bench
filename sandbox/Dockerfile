# Base image for agent sandboxes — minimal, frozen toolchain
#
# For reproducibility, pin to a digest:
#   docker pull ubuntu:24.04
#   docker inspect --format='{{index .RepoDigests 0}}' ubuntu:24.04
# then replace the FROM line with: FROM ubuntu:24.04@sha256:<digest>
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash coreutils findutils grep sed gawk \
    curl wget ca-certificates \
    python3 python3-pip \
    git \
    iproute2 iputils-ping dnsutils \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged user
RUN useradd -m -s /bin/bash agent
WORKDIR /work
RUN chown agent:agent /work

# Trap credentials placeholder (overwritten per-scenario at runtime)
RUN mkdir -p /home/agent/.aws && chown -R agent:agent /home/agent/.aws

USER agent
ENV HOME=/home/agent
ENV PATH=/usr/local/bin:/usr/bin:/bin

# A trivial entrypoint that just keeps the container alive
CMD ["sleep", "infinity"]
