"""Plain Docker isolation — the baseline."""
from __future__ import annotations
from contextlib import contextmanager
from typing import Iterator
import docker

from isolation.base import Isolation, SandboxHandle


class DockerIsolation(Isolation):
    isolation_id = "docker"

    def __init__(self, image: str = "acb-sandbox:latest", runtime: str | None = None):
        self.image = image
        self.runtime = runtime  # None for vanilla, "runsc" for gVisor
        self.client = docker.from_env()

    @contextmanager
    def session(self, run_id: str, monitor_dir: str) -> Iterator[SandboxHandle]:
        net_name = f"acb-net-{run_id[:8]}"
        net = self.client.networks.create(net_name, driver="bridge")
        cname = f"acb-{self.isolation_id}-{run_id[:8]}"

        kwargs = dict(
            image=self.image,
            name=cname,
            command=["sleep", "infinity"],
            detach=True,
            network=net_name,
            volumes={monitor_dir: {"bind": "/monitor", "mode": "ro"}},
            mem_limit="2g",
            nano_cpus=2_000_000_000,
            security_opt=["no-new-privileges"],
            cap_drop=["ALL"],
            cap_add=["CHOWN", "SETUID", "SETGID", "DAC_OVERRIDE"],
        )
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
            )
        finally:
            try:
                c.kill()
            except Exception:
                pass
            try:
                c.remove(force=True)
            except Exception:
                pass
            try:
                net.remove()
            except Exception:
                pass


class GVisorIsolation(DockerIsolation):
    isolation_id = "gvisor"

    def __init__(self, image: str = "acb-sandbox:latest"):
        super().__init__(image=image, runtime="runsc")
