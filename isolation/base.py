"""Abstract isolation environment — provides a sandbox for one agent run."""
from __future__ import annotations
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Any
import io
import tarfile


@dataclass
class SandboxHandle:
    """Handle exposing the running sandbox to the framework and scenario."""
    container_id: str
    container_name: str
    workdir: str            # path inside the sandbox where the agent works
    network_name: str       # docker network the sandbox is on
    monitor_dir: str        # host-side path where monitoring artifacts go
    isolation_id: str
    docker_client: Any      # docker.DockerClient

    def exec(self, cmd: list[str], **kw) -> tuple[int, str]:
        """Run a command inside the sandbox, return (exit_code, output)."""
        c = self.docker_client.containers.get(self.container_id)
        result = c.exec_run(cmd, **kw)
        return result.exit_code, result.output.decode("utf-8", errors="replace")

    def write_file(self, path: str, content: str) -> None:
        """Write a file inside the sandbox."""
        c = self.docker_client.containers.get(self.container_id)
        data = content.encode("utf-8")
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            info = tarfile.TarInfo(name=path.lstrip("/"))
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        tar_stream.seek(0)
        c.put_archive("/", tar_stream)


class Isolation(ABC):
    """Abstract isolation backend. Implementations differ in runtime + network."""
    isolation_id: str = "abstract"

    @abstractmethod
    @contextmanager
    def session(self, run_id: str, monitor_dir: str) -> Iterator[SandboxHandle]:
        """Context manager that stands up, yields, tears down a sandbox."""
        ...
