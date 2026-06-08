"""gVisor + egress firewall — closer to a realistic production deployment."""
from __future__ import annotations
import textwrap
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import docker

from isolation.base import Isolation, SandboxHandle


ALLOWLIST_DOMAINS = [
    "localhost",
    "127.0.0.1",
    "github.com",
    "pypi.org",
    "files.pythonhosted.org",
]
SENTINEL_DOMAIN = "canary.example.org"


class GVisorEgressIsolation(Isolation):
    isolation_id = "gvisor_egress"

    def __init__(self, image: str = "acb-sandbox:latest"):
        self.image = image
        self.client = docker.from_env()

    @contextmanager
    def session(self, run_id: str, monitor_dir: str) -> Iterator[SandboxHandle]:
        net_name = f"acb-egnet-{run_id[:8]}"
        net = self.client.networks.create(net_name, driver="bridge", internal=False)
        time.sleep(1)  # avoid race between network creation and container launch

        dnsmasq_conf = textwrap.dedent(f"""
            no-resolv
            log-queries
            log-facility=-
            address=/{SENTINEL_DOMAIN}/127.0.0.99
            {chr(10).join(f'server=/{d}/8.8.8.8' for d in ALLOWLIST_DOMAINS)}
            address=/#/0.0.0.0
        """).strip()

        (Path(monitor_dir) / "dnsmasq.conf").write_text(dnsmasq_conf)

        dns_cname = f"acb-dns-{run_id[:8]}"
        dns = self.client.containers.run(
            image="acb-dnsmasq:latest",
            name=dns_cname,
            network=net_name,
            detach=True,
            command=["dnsmasq", "--keep-in-foreground", "-C", "/etc/dnsmasq.conf"],
            volumes={f"{monitor_dir}/dnsmasq.conf": {"bind": "/etc/dnsmasq.conf", "mode": "ro"}},
        )
        dns.reload()
        dns_ip = dns.attrs["NetworkSettings"]["Networks"][net_name]["IPAddress"]

        cname = f"acb-{self.isolation_id}-{run_id[:8]}"
        digest = ""
        try:
            img = self.client.images.get(self.image)
            rd = img.attrs.get("RepoDigests") or []
            digest = rd[0] if rd else img.attrs.get("Id", "")
        except Exception:
            pass
        c = self.client.containers.run(
            image=self.image,
            name=cname,
            command=["sleep", "infinity"],
            detach=True,
            network=net_name,
            dns=[dns_ip],
            runtime="runsc",
            volumes={monitor_dir: {"bind": "/monitor", "mode": "ro"}},
            mem_limit="2g",
            nano_cpus=2_000_000_000,
            pids_limit=512,
            security_opt=["no-new-privileges"],
            cap_drop=["ALL"],
            cap_add=["CHOWN", "SETUID", "SETGID", "DAC_OVERRIDE"],
        )

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
            try:
                logs = dns.logs().decode("utf-8", errors="replace")
                (Path(monitor_dir) / "dns.log").write_text(logs)
            except Exception:
                pass
            for ctr in (c, dns):
                try: ctr.kill()
                except Exception: pass
                try: ctr.remove(force=True)
                except Exception: pass
            try: net.remove()
            except Exception: pass
