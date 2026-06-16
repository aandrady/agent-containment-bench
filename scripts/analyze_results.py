"""Generate analysis artifacts from JSONL benchmark results."""

from __future__ import annotations

import itertools
import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import fisher_exact
from statsmodels.stats.proportion import proportion_confint

GROUP_COLS = ["model", "framework_id", "isolation_id", "scenario_id"]


def _load_jsonl(path: Path) -> pd.DataFrame:
    rows = []
    with path.open() as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on {path}:{line_no}") from exc
    if not rows:
        raise ValueError(f"no result rows found in {path}")
    df = pd.DataFrame(rows)
    df["escape_categories"] = df["escape_categories"].apply(
        lambda value: list(value) if value is not None else []
    )
    df["escaped"] = df["escaped"].astype(bool)
    return df


def _wilson(series: pd.Series) -> tuple[float, float, float]:
    successes = int(series.sum())
    n = len(series)
    if n == 0:
        return (np.nan, np.nan, np.nan)
    lo, hi = proportion_confint(successes, n, alpha=0.05, method="wilson")
    return (successes / n, lo, hi)


def _cell_summary(df: pd.DataFrame) -> pd.DataFrame:
    agg = (
        df.groupby(GROUP_COLS)["escaped"]
        .agg(
            rate=lambda series: _wilson(series)[0],
            lo=lambda series: _wilson(series)[1],
            hi=lambda series: _wilson(series)[2],
            n="count",
        )
        .reset_index()
    )
    cost_agg = df.groupby(GROUP_COLS)["cost_usd"].mean().reset_index()
    return agg.merge(cost_agg, on=GROUP_COLS).rename(columns={"cost_usd": "mean_cost"})


def _artifact_slug(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)


def _write_heatmaps(agg: pd.DataFrame, results_dir: Path) -> None:
    sns.set_theme(style="whitegrid", context="talk")
    for (model, framework_id), model_agg in agg.groupby(["model", "framework_id"]):
        sub = model_agg.pivot(
            index="isolation_id",
            columns="scenario_id",
            values="rate",
        )
        if sub.empty:
            continue
        fig, ax = plt.subplots(figsize=(12, 4))
        sns.heatmap(
            sub,
            annot=True,
            fmt=".0%",
            cmap="Reds",
            vmin=0,
            vmax=1,
            ax=ax,
            cbar_kws={"label": "Escape rate"},
        )
        ax.set_title(f"Escape rate - {framework_id} - {model}")
        plt.tight_layout()
        slug = _artifact_slug(f"{model}_{framework_id}")
        fig.savefig(results_dir / f"heatmap_{slug}.png", dpi=150, bbox_inches="tight")
        plt.close(fig)


def _write_cost_plot(agg: pd.DataFrame, results_dir: Path) -> None:
    for model, model_agg in agg.groupby("model"):
        fig, ax = plt.subplots(figsize=(12, 4))
        sns.barplot(
            data=model_agg,
            x="scenario_id",
            y="mean_cost",
            hue="isolation_id",
            ax=ax,
        )
        ax.set_ylabel("Mean cost per run (USD)")
        ax.set_title(f"Cost per run by isolation config - {model}")
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        fig.savefig(results_dir / f"cost_per_run_{_artifact_slug(model)}.png", dpi=150)
        plt.close(fig)


def _cost_per_escape(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(GROUP_COLS)
        .agg(
            escapes=("escaped", "sum"),
            total_cost=("cost_usd", "sum"),
            n=("escaped", "count"),
        )
        .assign(
            usd_per_escape=lambda data: np.where(
                data.escapes > 0,
                data.total_cost / data.escapes,
                np.nan,
            )
        )
        .reset_index()
    )


def _category_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    escaped = df[df.escaped].copy()
    escaped["cats_str"] = escaped["escape_categories"].apply(
        lambda categories: ",".join(categories) if categories else "none"
    )
    return escaped.groupby(GROUP_COLS + ["cats_str"]).size().reset_index(name="n")


def _significance_tests(df: pd.DataFrame) -> pd.DataFrame:
    results = []
    isolations = sorted(df.isolation_id.unique())
    for model in sorted(df.model.unique()):
        for framework_id in sorted(df.framework_id.unique()):
            for scenario_id in sorted(df.scenario_id.unique()):
                for iso_a, iso_b in itertools.combinations(isolations, 2):
                    a = df[
                        (df.model == model)
                        & (df.framework_id == framework_id)
                        & (df.isolation_id == iso_a)
                        & (df.scenario_id == scenario_id)
                    ]
                    b = df[
                        (df.model == model)
                        & (df.framework_id == framework_id)
                        & (df.isolation_id == iso_b)
                        & (df.scenario_id == scenario_id)
                    ]
                    if a.empty or b.empty:
                        continue
                    a_success = int(a.escaped.sum())
                    b_success = int(b.escaped.sum())
                    _, p_value = fisher_exact(
                        [[a_success, len(a) - a_success], [b_success, len(b) - b_success]]
                    )
                    results.append(
                        {
                            "model": model,
                            "framework": framework_id,
                            "scenario": scenario_id,
                            "iso_a": iso_a,
                            "iso_b": iso_b,
                            "rate_a": a.escaped.mean(),
                            "rate_b": b.escaped.mean(),
                            "n_a": len(a),
                            "n_b": len(b),
                            "p_value": p_value,
                        }
                    )
    return pd.DataFrame(results)


def main() -> None:
    results_dir = Path(os.environ.get("RESULTS_DIR", "./results"))
    input_path = Path(os.environ.get("RESULTS_JSONL", results_dir / "matrix_runs.jsonl"))
    results_dir.mkdir(parents=True, exist_ok=True)

    df = _load_jsonl(input_path)
    df.to_parquet(results_dir / "matrix_runs.parquet", index=False)

    agg = _cell_summary(df)
    agg.to_csv(results_dir / "cell_summary.csv", index=False)
    _write_heatmaps(agg, results_dir)
    _write_cost_plot(agg, results_dir)
    _cost_per_escape(df).to_csv(results_dir / "cost_per_escape.csv", index=False)
    _category_breakdown(df).to_csv(results_dir / "category_breakdown.csv", index=False)
    _significance_tests(df).to_csv(results_dir / "significance_tests.csv", index=False)

    print(f"Rows: {len(df)}")
    print(f"Cells: {df.groupby(GROUP_COLS).ngroups}")
    print(f"Errors: {df['error'].notna().sum()}")
    print(f"Escapes: {int(df['escaped'].sum())}")
    print(f"Wrote artifacts to {results_dir}")


if __name__ == "__main__":
    main()
