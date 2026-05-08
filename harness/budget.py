"""Hard budget guard — refuses to run if any cap would be exceeded."""
from __future__ import annotations
import json
import os
from pathlib import Path
from threading import Lock

LEDGER_PATH = Path(os.environ.get("RESULTS_DIR", "./results")) / "_budget_ledger.json"
_LOCK = Lock()


class BudgetExceeded(RuntimeError):
    pass


def _load() -> dict:
    if LEDGER_PATH.exists():
        return json.loads(LEDGER_PATH.read_text())
    return {"total_usd": 0.0, "current_campaign_usd": 0.0, "campaign_id": None}


def _save(d: dict) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(d, indent=2))


def check_can_spend(estimated_usd: float, campaign_id: str) -> None:
    max_run = float(os.environ.get("MAX_USD_PER_RUN", "2.00"))
    max_campaign = float(os.environ.get("MAX_USD_PER_CAMPAIGN", "200.00"))
    max_total = float(os.environ.get("MAX_USD_TOTAL", "2000.00"))
    if estimated_usd > max_run:
        raise BudgetExceeded(f"single-run cap ${max_run} would be exceeded by ${estimated_usd:.2f}")
    with _LOCK:
        d = _load()
        if d.get("campaign_id") != campaign_id:
            d = {"total_usd": d.get("total_usd", 0.0), "current_campaign_usd": 0.0, "campaign_id": campaign_id}
            _save(d)
        if d["current_campaign_usd"] + estimated_usd > max_campaign:
            raise BudgetExceeded(f"campaign cap ${max_campaign} would be exceeded")
        if d["total_usd"] + estimated_usd > max_total:
            raise BudgetExceeded(f"total cap ${max_total} would be exceeded")


def record_spend(actual_usd: float, campaign_id: str) -> None:
    with _LOCK:
        d = _load()
        if d.get("campaign_id") != campaign_id:
            d = {"total_usd": d.get("total_usd", 0.0), "current_campaign_usd": 0.0, "campaign_id": campaign_id}
        d["current_campaign_usd"] += actual_usd
        d["total_usd"] += actual_usd
        _save(d)
