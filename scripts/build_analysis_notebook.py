"""Build notebooks/analysis.ipynb from the cell list in the playbook."""
import nbformat as nbf
from pathlib import Path

nb = nbf.v4.new_notebook()

cells = []

cells.append(nbf.v4.new_markdown_cell(
    "# agent-containment-bench — v1 analysis\n\n"
    "Reads `../results/v1-matrix.parquet`. Produces all CSVs and PNGs referenced by the blog post."
))

cells.append(nbf.v4.new_code_cell("""\
import json, pandas as pd, numpy as np, matplotlib.pyplot as plt, seaborn as sns
from statsmodels.stats.proportion import proportion_confint
from pathlib import Path

sns.set_theme(style="whitegrid", context="talk")
df = pd.read_parquet("../results/v1-matrix.parquet")
# Defensive: ensure escape_categories is always a list
df["escape_categories"] = df["escape_categories"].apply(lambda x: list(x) if x is not None else [])
print(f"Rows: {len(df)}  Cells: {df.groupby(['framework_id','isolation_id','scenario_id']).ngroups}")
print(f"Errors: {df['error'].notna().sum()}  Escapes: {df['escaped'].sum()}")
df.head(3)"""))

cells.append(nbf.v4.new_markdown_cell("## Cell-level summary with Wilson 95% CIs"))

cells.append(nbf.v4.new_code_cell("""\
def wilson(s):
    succ = int(s.sum())
    n = len(s)
    if n == 0:
        return (np.nan, np.nan, np.nan)
    lo, hi = proportion_confint(succ, n, alpha=0.05, method="wilson")
    return (succ / n, lo, hi)

agg = (df.groupby(["framework_id","isolation_id","scenario_id"])["escaped"]
         .agg(rate=lambda s: wilson(s)[0],
              lo=lambda s: wilson(s)[1],
              hi=lambda s: wilson(s)[2],
              n="count")
         .reset_index())
cost_agg = df.groupby(["framework_id","isolation_id","scenario_id"])["cost_usd"].mean().reset_index()
agg = agg.merge(cost_agg, on=["framework_id","isolation_id","scenario_id"])
agg.rename(columns={"cost_usd": "mean_cost"}, inplace=True)

Path("../results").mkdir(exist_ok=True)
agg.to_csv("../results/cell_summary.csv", index=False)
agg"""))

cells.append(nbf.v4.new_markdown_cell("## Headline heatmaps"))

cells.append(nbf.v4.new_code_cell("""\
def heatmap(framework_id):
    sub = agg[agg.framework_id == framework_id].pivot(
        index="isolation_id", columns="scenario_id", values="rate")
    if sub.empty:
        print(f"No data for {framework_id}")
        return None
    fig, ax = plt.subplots(figsize=(12, 4))
    sns.heatmap(sub, annot=True, fmt=".0%", cmap="Reds", vmin=0, vmax=1, ax=ax,
                cbar_kws={"label": "Escape rate"})
    ax.set_title(f"Escape rate — {framework_id}")
    plt.tight_layout()
    fig.savefig(f"../results/heatmap_{framework_id}.png", dpi=150, bbox_inches="tight")
    return fig

for fw in df.framework_id.unique():
    heatmap(fw)
plt.show()"""))

cells.append(nbf.v4.new_markdown_cell("## Cost per run by isolation config"))

cells.append(nbf.v4.new_code_cell("""\
fig, ax = plt.subplots(figsize=(12, 4))
sns.barplot(data=agg, x="scenario_id", y="mean_cost", hue="isolation_id", ax=ax)
ax.set_ylabel("Mean cost per run (USD)")
ax.set_title("Cost per run by isolation config")
plt.xticks(rotation=30, ha="right")
plt.tight_layout()
plt.savefig("../results/cost_per_run.png", dpi=150)
plt.show()"""))

cells.append(nbf.v4.new_markdown_cell("## Cost per successful escape"))

cells.append(nbf.v4.new_code_cell("""\
cpe = (df.groupby(["framework_id","isolation_id","scenario_id"])
         .agg(escapes=("escaped", "sum"),
              total_cost=("cost_usd", "sum"),
              n=("escaped", "count"))
         .assign(usd_per_escape=lambda d: np.where(d.escapes > 0, d.total_cost / d.escapes, np.nan))
         .reset_index())
cpe.to_csv("../results/cost_per_escape.csv", index=False)
cpe"""))

cells.append(nbf.v4.new_markdown_cell("## Escape category breakdown"))

cells.append(nbf.v4.new_code_cell("""\
df["cats_str"] = df["escape_categories"].apply(lambda l: ",".join(l) if l else "none")
cat_breakdown = (df[df.escaped]
                 .groupby(["scenario_id","cats_str"]).size()
                 .reset_index(name="n"))
cat_breakdown.to_csv("../results/category_breakdown.csv", index=False)
cat_breakdown"""))

cells.append(nbf.v4.new_markdown_cell("## Statistical tests — Fisher's exact for isolation pairs"))

cells.append(nbf.v4.new_code_cell("""\
from scipy.stats import fisher_exact
import itertools

def compare(scen, iso_a, iso_b, fw):
    a = df[(df.framework_id==fw)&(df.isolation_id==iso_a)&(df.scenario_id==scen)]
    b = df[(df.framework_id==fw)&(df.isolation_id==iso_b)&(df.scenario_id==scen)]
    if len(a) == 0 or len(b) == 0:
        return None
    a_succ, a_fail = int(a.escaped.sum()), len(a) - int(a.escaped.sum())
    b_succ, b_fail = int(b.escaped.sum()), len(b) - int(b.escaped.sum())
    odds, p = fisher_exact([[a_succ, a_fail], [b_succ, b_fail]])
    return {"framework": fw, "scenario": scen, "iso_a": iso_a, "iso_b": iso_b,
            "rate_a": a.escaped.mean(), "rate_b": b.escaped.mean(),
            "n_a": len(a), "n_b": len(b), "p_value": p}

results = []
for fw in df.framework_id.unique():
    for sc in df.scenario_id.unique():
        for ia, ib in itertools.combinations(sorted(df.isolation_id.unique()), 2):
            r = compare(sc, ia, ib, fw)
            if r is not None:
                results.append(r)
sig = pd.DataFrame(results)
sig.to_csv("../results/significance_tests.csv", index=False)
sig.sort_values("p_value").head(20)"""))

cells.append(nbf.v4.new_markdown_cell("## Sanity checks (should pass on real data)"))

cells.append(nbf.v4.new_code_cell("""\
# Benign control must have near-zero escape rate
benign = agg[agg.scenario_id == "s00_benign"]
print("Benign control escape rates (should be near 0):")
print(benign[["framework_id","isolation_id","rate","n"]].to_string(index=False))
assert benign["rate"].max() < 0.20, "Benign control firing escapes — investigate detection logic"

# Error rate sanity
err_rate = df["error"].notna().mean()
print(f"\\nError rate: {err_rate:.1%}")
assert err_rate < 0.10, f"Error rate {err_rate:.1%} is too high"

print("\\nAll sanity checks passed.")"""))

nb["cells"] = cells
out = Path("notebooks/analysis.ipynb")
out.parent.mkdir(exist_ok=True)
nbf.write(nb, str(out))
print(f"Wrote {out} with {len(cells)} cells")
