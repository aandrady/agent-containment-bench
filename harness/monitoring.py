"""Filesystem and network monitors that record evidence into monitor_dir."""
from __future__ import annotations
import json
import os
import threading
import time
from pathlib import Path
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class FSMonitor(FileSystemEventHandler):
    """Records every file event under sentinel paths."""

    def __init__(self, sentinel_paths: list[str], log_path: str):
        self.sentinels = [os.path.abspath(p) for p in sentinel_paths]
        self.log_path = log_path
        self.events: list[dict] = []
        self._lock = threading.Lock()

    def on_any_event(self, event):
        for s in self.sentinels:
            if event.src_path.startswith(s):
                with self._lock:
                    self.events.append({
                        "ts": time.time(),
                        "type": event.event_type,
                        "path": event.src_path,
                        "is_directory": event.is_directory,
                    })
                break

    def flush(self) -> list[dict]:
        with self._lock:
            with open(self.log_path, "w") as f:
                for e in self.events:
                    f.write(json.dumps(e) + "\n")
            return list(self.events)


def start_fs_monitor(sentinel_paths: list[str], log_path: str) -> tuple[Observer, FSMonitor]:
    """Start watching sentinel_paths; returns (observer, handler).
    Caller is responsible for observer.stop() + observer.join()."""
    handler = FSMonitor(sentinel_paths, log_path)
    obs = Observer()
    for p in sentinel_paths:
        Path(p).mkdir(parents=True, exist_ok=True)
        obs.schedule(handler, p, recursive=True)
    obs.start()
    return obs, handler


def parse_dnsmasq_log(log_path: str) -> list[dict]:
    """Extract DNS query events from dnsmasq stderr log."""
    events = []
    if not Path(log_path).exists():
        return events
    for line in Path(log_path).read_text().splitlines():
        # dnsmasq log format: "<date> <pid>: query[type] <name> from <ip>"
        if " query[" in line:
            try:
                parts = line.split(" query[", 1)[1]
                qtype, rest = parts.split("] ", 1)
                qname, src = rest.split(" from ", 1)
                events.append({
                    "ts": time.time(),
                    "query": qname.strip(),
                    "type": qtype.strip(),
                    "src": src.strip(),
                })
            except Exception:
                continue
    return events
