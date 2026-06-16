"""Build notebooks/analysis.ipynb from the JSONL analysis workflow."""

from pathlib import Path

import nbformat as nbf

nb = nbf.v4.new_notebook()

cells = []

cells.append(
    nbf.v4.new_markdown_cell(
        "# agent-containment-bench - v1 analysis\n\n"
        "Reads `../results/matrix_runs.jsonl`. Produces the CSV and PNG artifacts "
        "referenced by the docs and blog draft."
    )
)

cells.append(
    nbf.v4.new_code_cell(
        """\
import itertools
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import fisher_exact
from statsmodels.stats.proportion import proportion_confint

sns.set_theme(style="whitegrid", context="talk")
rows = [
    json.loads(line)
    for line in Path("../results/matrix_runs.jsonl").read_text().splitlines()
    if line
]
df = pd.DataFrame(rows)
df["escape_categories"] = df["escape_categories"].apply(
    lambda value: list(value) if value is not None else []
)
groups = ["model", "framework_id", "isolation_id", "scenario_id"]
print(f"Rows: {len(df)}  Cells: {df.groupby(groups).ngroups}")
print(f"Errors: {df['error'].notna().sum()}  Escapes: {df['escaped'].sum()}")
df.head(3)"""
    )
)

cells.append(nbf.v4.new_markdown_cell("## Cell-level summary with Wilson 95% CIs"))

cells.append(
    nbf.v4.new_code_cell(
        """\
def wilson(series):
    successes = int(series.sum())
    n = len(series)
    if n == 0:
        return (np.nan, np.nan, np.nan)
    lo, hi = proportion_confint(successes, n, alpha=0.05, method="wilson")
    return (successes / n, lo, hi)

agg = (
    df.groupby(groups)["escaped"]
    .agg(
        rate=lambda series: wilson(series)[0],
        lo=lambda series: wilson(series)[1],
        hi=lambda series: wilson(series)[2],
        n="count",
    )
    .reset_index()
)
cost_agg = df.groupby(groups)["cost_usd"].mean().reset_index()
agg = agg.merge(cost_agg, on=groups).rename(columns={"cost_usd": "mean_cost"})

Path("../results").mkdir(exist_ok=True)
agg.to_csv("../results/cell_summary.csv", index=False)
agg"""
    )
)

cells.append(nbf.v4.new_markdown_cell("## Headline heatmaps"))

cells.append(
    nbf.v4.new_code_cell(
        """\
def heatmap(model, framework_id):
    sub = agg[(agg.model == model) & (agg.framework_id == framework_id)].pivot(
        index="isolation_id",
        columns="scenario_id",
        values="rate",
    )
    if sub.empty:
        print(f"No data for {model}/{framework_id}")
        return None
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
    slug = f"{model}_{framework_id}".replace("/", "_")
    fig.savefig(f"../results/heatmap_{slug}.png", dpi=150, bbox_inches="tight")
    return fig

for model in df.model.unique():
    for fw in df.framework_id.unique():
        heatmap(model, fw)
plt.show()"""
    )
)

cells.append(nbf.v4.new_markdown_cell("## Cost per run by isolation config"))

cells.append(
    nbf.v4.new_code_cell(
        """\
for model, model_agg in agg.groupby("model"):
    fig, ax = plt.subplots(figsize=(12, 4))
    sns.barplot(data=model_agg, x="scenario_id", y="mean_cost", hue="isolation_id", ax=ax)
    ax.set_ylabel("Mean cost per run (USD)")
    ax.set_title(f"Cost per run by isolation config - {model}")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(f"../results/cost_per_run_{model}.png", dpi=150)
plt.show()"""
    )
)

cells.append(nbf.v4.new_markdown_cell("## Cost per successful escape"))

cells.append(
    nbf.v4.new_code_cell(
        """\
cpe = (
    df.groupby(groups)
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
cpe.to_csv("../results/cost_per_escape.csv", index=False)
cpe"""
    )
)

cells.append(nbf.v4.new_markdown_cell("## Escape category breakdown"))

cells.append(
    nbf.v4.new_code_cell(
        """\
df["cats_str"] = df["escape_categories"].apply(
    lambda categories: ",".join(categories) if categories else "none"
)
cat_breakdown = (
    df[df.escaped]
    .groupby(groups + ["cats_str"])
    .size()
    .reset_index(name="n")
)
cat_breakdown.to_csv("../results/category_breakdown.csv", index=False)
cat_breakdown"""
    )
)

cells.append(nbf.v4.new_markdown_cell("## Statistical tests - Fisher exact for isolation pairs"))

cells.append(
    nbf.v4.new_code_cell(
        """\
def compare(model, scenario_id, iso_a, iso_b, framework_id):
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
    if len(a) == 0 or len(b) == 0:
        return None
    a_success = int(a.escaped.sum())
    b_success = int(b.escaped.sum())
    _, p_value = fisher_exact(
        [[a_success, len(a) - a_success], [b_success, len(b) - b_success]]
    )
    return {
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

results = []
for model in df.model.unique():
    for fw in df.framework_id.unique():
        for scenario_id in df.scenario_id.unique():
            for iso_a, iso_b in itertools.combinations(sorted(df.isolation_id.unique()), 2):
                result = compare(model, scenario_id, iso_a, iso_b, fw)
                if result is not None:
                    results.append(result)
sig = pd.DataFrame(results)
sig.to_csv("../results/significance_tests.csv", index=False)
sig.sort_values("p_value").head(20)"""
    )
)

cells.append(nbf.v4.new_markdown_cell("## Sanity checks"))

cells.append(
    nbf.v4.new_code_cell(
        """\
benign = agg[agg.scenario_id == "s00_benign"]
assert (benign.rate < 0.05).all(), benign
assert df["error"].isna().mean() > 0.95
print("Sanity checks passed")"""
    )
)

nb["cells"] = cells
out = Path("notebooks/analysis.ipynb")
out.parent.mkdir(exist_ok=True)
nbf.write(nb, out)
print(f"Wrote {out}")
