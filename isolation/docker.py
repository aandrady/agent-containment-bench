"""Docker / gVisor isolation backends.

Hardening as a study variable: each backend records its policy in `isolation_id`
so the matrix can compare:
  - docker_loose:    no cap_drop, no security_opt, writable rootfs (naive deploy)
  - docker:          cap_drop=ALL +CHOWN/SETUID/SETGID/DAC_OVERRIDE, no-new-privs (baseline)
  - docker_hardened: cap_drop=ALL (no add-back), read-only rootfs + tmpfs, no-new-privs
  - gvisor:          baseline policy under runsc
  - gvisor_hardened: hardened policy under runsc
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, suppress

import docker

from isolation.base import Isolation, SandboxHandle


def _lookup_digest(client, image: str) -> str:
    """Best-effort image digest. Returns RepoDigest if available, else image id."""
    try:
        img = client.images.get(image)
        rd = img.attrs.get("RepoDigests") or []
        if rd:
            return rd[0]
        return img.attrs.get("Id", "")
    except Exception:
        return ""


def _hardening_kwargs(level: str) -> dict:
    """Return docker run kwargs for a given hardening profile.

    pids_limit=512 is set on all profiles to prevent fork bombs even under 'loose'.
    """
    if level == "loose":
        return dict(
            mem_limit="2g",
            nano_cpus=2_000_000_000,
            pids_limit=512,
        )
    if level == "hardened":
        return dict(
            mem_limit="2g",
            nano_cpus=2_000_000_000,
            pids_limit=256,
            security_opt=["no-new-privileges"],
            cap_drop=["ALL"],
            read_only=True,
            tmpfs={
                "/tmp": "rw,size=64m",  # noqa: S108 - container tmpfs mount.
                "/work": "rw,size=64m,uid=1000,gid=1000",
                "/home/agent": "rw,size=32m,uid=1000,gid=1000",
            },
        )
    # default "baseline"
    return dict(
        mem_limit="2g",
        nano_cpus=2_000_000_000,
        pids_limit=512,
        security_opt=["no-new-privileges"],
        cap_drop=["ALL"],
        cap_add=["CHOWN", "SETUID", "SETGID", "DAC_OVERRIDE"],
    )


class DockerIsolation(Isolation):
    isolation_id = "docker"
    hardening: str = "baseline"

    def __init__(
        self,
        image: str = "acb-sandbox:latest",
        runtime: str | None = None,
        hardening: str | None = None,
    ):
        self.image = image
        self.runtime = runtime
        if hardening:
            self.hardening = hardening
        self.client = docker.from_env()

    @contextmanager
    def session(self, run_id: str, monitor_dir: str) -> Iterator[SandboxHandle]:
        net_name = f"acb-net-{run_id[:8]}"
        net = self.client.networks.create(net_name, driver="bridge")
        cname = f"acb-{self.isolation_id}-{run_id[:8]}"
        digest = _lookup_digest(self.client, self.image)

        kwargs = dict(
            image=self.image,
            name=cname,
            command=["sleep", "infinity"],
            detach=True,
            network=net_name,
            volumes={monitor_dir: {"bind": "/monitor", "mode": "ro"}},
        )
        kwargs.update(_hardening_kwargs(self.hardening))
        if self.runtime:
            kwargs["runtime"] = self.runtime

        c = self.client.containers.run(**kwargs)
        try:
            yield SandboxHandle(
                container_id=c.id,
                container_name=cname,
                workdir="/work",
                network_name=net_name,
                monitor_dir=monitor_dir,
                isolation_id=self.isolation_id,
                docker_client=self.client,
                image_digest=digest,
            )
        finally:
            with suppress(Exception):
                c.kill()
            with suppress(Exception):
                c.remove(force=True)
            with suppress(Exception):
                net.remove()


class DockerLooseIsolation(DockerIsolation):
    """Naive deployment baseline: no cap_drop, no no-new-privileges, no read-only.
    Useful as the 'how bad does it get?' anchor in the hardening axis."""

    isolation_id = "docker_loose"
    hardening = "loose"


class DockerHardenedIsolation(DockerIsolation):
    """Tight defaults: read-only rootfs, no cap_add, tmpfs for writable areas."""

    isolation_id = "docker_hardened"
    hardening = "hardened"


class GVisorIsolation(DockerIsolation):
    isolation_id = "gvisor"

    def __init__(self, image: str = "acb-sandbox:latest"):
        super().__init__(image=image, runtime="runsc", hardening="baseline")


class GVisorHardenedIsolation(DockerIsolation):
    isolation_id = "gvisor_hardened"
    hardening = "hardened"

    def __init__(self, image: str = "acb-sandbox:latest"):
        super().__init__(image=image, runtime="runsc", hardening="hardened")
