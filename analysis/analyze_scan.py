#!/usr/bin/env python3
"""Wertet einen Scan von Teil B aus.

Aufruf: .venv/bin/python analysis/analyze_scan.py pilot-01
Ergebnis: data/processed/scan/<name>/ (hosts_classified.csv, shares.csv, tests.csv, report.md)
          figures/<name>/ (PNG und SVG)

Die Hosting-Klasse entsteht erst hier aus den Rohdaten und scan/hosting_rules.csv, damit eine
geänderte Regel keinen neuen Scan braucht. Die Regeln für H3 stehen in scan/README.md.
"""
import pathlib
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd
from scipy import stats

REPO_DIR = pathlib.Path(__file__).resolve().parent.parent

CATEGORIES = ["Nachrichten", "Onlineshops", "Banken", "Behörden", "Hochschulen"]
HOSTING = ["Cloudflare", "Akamai", "AWS", "Andere CDN/Cloud", "Sonstige/eigener Server"]
DEFAULT_HOSTING = "Sonstige/eigener Server"
ANSWERED = ["ja", "nein", "nein_nur_tls12", "nein_abbruch"]

ALPHA = 0.05
PERMUTATIONS = 10_000
PERMUTATION_SEED = 20261111
PILOT_BELOW_N = 60

# Farben: reference palette der dataviz-Vorgaben, geprüft mit validate_palette.js
COLOR_HOSTING = dict(zip(HOSTING, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#6250d6"]))
COLOR_SHARE = "#2a78d6"
SECONDARY = "#52514e"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
INK = "#0b0b0b"
SURFACE = "#fcfcfb"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
    "font.size": 14,
    "svg.fonttype": "none",
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": BASELINE,
    "axes.labelcolor": SECONDARY,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.axisbelow": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "xtick.color": SECONDARY,
    "ytick.color": SECONDARY,
    "text.color": INK,
    "legend.frameon": False,
})


def load_rules():
    return pd.read_csv(REPO_DIR / "scan" / "hosting_rules.csv", dtype=str).to_dict("records")


def classify_hosting(row, rules):
    """CNAMEs gehen vor: Ein Akamai-Knoten im Netz eines Providers hat dessen ASN."""
    for rule in rules:
        if rule["typ"] == "cname" and any(name.endswith(rule["muster"]) for name in row["cnames"].split()):
            return rule["klasse"]
    for rule in rules:
        if rule["typ"] == "asn" and row["asn"] == rule["muster"]:
            return rule["klasse"]
    return DEFAULT_HOSTING


def load_hosts(name):
    hosts = pd.read_csv(REPO_DIR / "data" / "raw" / "scan" / name / "hosts.csv", dtype=str,
                        keep_default_na=False)
    # Bei zwei Durchgängen zählt der letzte, die Zeile davor bleibt in den Rohdaten.
    hosts = hosts.drop_duplicates("domain", keep="last").reset_index(drop=True)
    rules = load_rules()
    hosts["hosting"] = [classify_hosting(row, rules) for row in hosts.to_dict("records")]
    return hosts


def wilson(successes, total):
    interval = stats.binomtest(int(successes), int(total)).proportion_ci(method="wilson")
    return interval.low, interval.high


def shares(data, column, order):
    """Post-Quanten-Anteil mit Wilson-Intervall pro Ausprägung."""
    rows = []
    for value in order:
        group = data[data[column] == value]
        if group.empty:
            continue
        low, high = wilson(group["pq"].sum(), len(group))
        rows.append({"gruppe": column, "wert": value, "n": len(group), "pq_ja": int(group["pq"].sum()),
                     "anteil": group["pq"].mean(), "ci_low": low, "ci_high": high})
    return rows


def association(data, column):
    """Chi-Quadrat nur, wenn alle erwarteten Häufigkeiten mindestens 5 sind, sonst Fisher."""
    table = pd.crosstab(data[column], data["pq"])
    table = table.loc[table.sum(axis=1) > 0]
    if table.shape[1] < 2 or table.shape[0] < 2:
        return {"merkmal": column, "test": "nicht möglich", "p": np.nan, "cramers_v": np.nan}
    chi2, chi2_p, dof, expected = stats.chi2_contingency(table, correction=False)
    cramers_v = np.sqrt(chi2 / (table.to_numpy().sum() * min(table.shape[0] - 1, table.shape[1] - 1)))
    if expected.min() >= 5:
        return {"merkmal": column, "test": "Chi-Quadrat", "p": chi2_p, "cramers_v": cramers_v}
    return {"merkmal": column, "test": "Fisher-Freeman-Halton",
            "p": stats.fisher_exact(table.to_numpy()).pvalue, "cramers_v": cramers_v}


def stratum_statistic(codes, outcome, levels):
    """Chi-Quadrat einer Schicht. Ohne Streuung im Ergebnis trägt sie nichts bei."""
    mean = outcome.mean()
    if mean in (0, 1):
        return 0.0
    totals = np.bincount(codes, minlength=levels)
    hits = np.bincount(codes, weights=outcome, minlength=levels)
    used = totals > 0
    return np.sum((hits[used] - totals[used] * mean) ** 2 / (totals[used] * mean * (1 - mean)))


def stratified_permutation(data, factor, stratum, rng):
    """Prüft den Einfluss von factor, wenn stratum festgehalten wird.

    Das Ergebnis wird nur innerhalb der Schichten permutiert. So bleibt ein Zusammenhang zwischen
    Branche und Hosting erhalten, der sonst als Effekt des jeweils anderen Merkmals erschiene.
    """
    codes = data[factor].astype("category").cat.codes.to_numpy()
    outcome = data["pq"].to_numpy(dtype=float)
    levels = codes.max() + 1
    strata = [np.flatnonzero(data[stratum].to_numpy() == value) for value in data[stratum].unique()]
    observed = sum(stratum_statistic(codes[i], outcome[i], levels) for i in strata)
    at_least = 0
    for _ in range(PERMUTATIONS):
        permuted = sum(stratum_statistic(codes[i], rng.permutation(outcome[i]), levels) for i in strata)
        at_least += permuted >= observed - 1e-12
    return {"merkmal": factor, "gehalten": stratum, "statistik": observed,
            "p": (at_least + 1) / (PERMUTATIONS + 1)}


def judge_h3(associations, conditional):
    hosting = associations.set_index("merkmal").loc["hosting"]
    category = associations.set_index("merkmal").loc["kategorie"]
    hosting_p = conditional.set_index("merkmal").loc["hosting", "p"]
    category_p = conditional.set_index("merkmal").loc["kategorie", "p"]
    criteria = {
        "Hosting wirkt bei fester Branche (p < 0,05)": hosting_p < ALPHA,
        "Branche wirkt bei festem Hosting nicht (p ≥ 0,05)": category_p >= ALPHA,
        "Cramérs V von Hosting größer als von Branche": hosting["cramers_v"] > category["cramers_v"],
    }
    return criteria


def save_figure(figure, out_dir, stem):
    figure.savefig(out_dir / f"{stem}.png", dpi=200, bbox_inches="tight")
    figure.savefig(out_dir / f"{stem}.svg", bbox_inches="tight")
    plt.close(figure)


def sample_note(n):
    return f"Pilot mit n = {n}, nicht belastbar" if n < PILOT_BELOW_N else f"n = {n}"


def plot_hosting_by_category(data, out_dir):
    """Gestapelte Balken: Wer hostet die Seiten einer Kategorie?"""
    counts = pd.crosstab(data["kategorie"], data["hosting"]).reindex(index=CATEGORIES, columns=HOSTING,
                                                                      fill_value=0)
    figure, axis = plt.subplots(figsize=(11, 5.4))
    positions = np.arange(len(CATEGORIES))[::-1]
    left = np.zeros(len(CATEGORIES))
    for hosting in HOSTING:
        values = counts[hosting].to_numpy()
        axis.barh(positions, values, left=left, height=0.56, color=COLOR_HOSTING[hosting],
                  edgecolor=SURFACE, linewidth=2, label=hosting)
        for y, value, start in zip(positions, values, left):
            if value:
                color = INK if hosting == "AWS" or hosting == "Andere CDN/Cloud" else "#ffffff"
                axis.text(start + value / 2, y, str(value), ha="center", va="center", color=color, fontsize=13)
        left += values
    axis.set_yticks(positions, CATEGORIES)
    axis.set_xlabel("Anzahl der Websites")
    axis.xaxis.set_major_locator(MaxNLocator(integer=True))
    axis.grid(axis="x")
    axis.tick_params(axis="y", length=0)
    axis.legend(loc="lower left", bbox_to_anchor=(0, 1), ncols=3, borderaxespad=0.2, fontsize=13)
    axis.set_title("Hosting der Websites nach Branche", loc="left", fontweight="bold", pad=66)
    figure.text(0.125, -0.04, f"{sample_note(len(data))}. Klassen aus CNAME und ASN.", color=SECONDARY, fontsize=12)
    save_figure(figure, out_dir, "scan_hosting_je_kategorie")


def plot_shares(table, n, out_dir):
    """Anteile mit Intervall, damit die Unsicherheit bei wenigen Hosts sichtbar bleibt."""
    figure, axes = plt.subplots(1, 2, figsize=(13, 4.8), sharex=True)
    for axis, column, title in zip(axes, ["kategorie", "hosting"], ["Nach Branche", "Nach Hosting"]):
        rows = table[table["gruppe"] == column].sort_values("anteil")
        positions = np.arange(len(rows))
        values = rows["anteil"].to_numpy() * 100
        errors = [values - rows["ci_low"].to_numpy() * 100, rows["ci_high"].to_numpy() * 100 - values]
        axis.errorbar(values, positions, xerr=errors, fmt="o", color=COLOR_SHARE, markersize=9,
                      markeredgecolor=SURFACE, markeredgewidth=2, elinewidth=1.4, capsize=4)
        axis.set_yticks(positions, [f"{row.wert} (n = {row.n})" for row in rows.itertuples()])
        axis.set_xlim(-3, 103)
        axis.set_ylim(-0.6, len(rows) - 0.4)
        axis.grid(axis="x")
        axis.tick_params(axis="y", length=0)
        axis.set_title(title, loc="left", fontsize=14, color=SECONDARY)
        axis.set_xlabel("Websites mit X25519MLKEM768 in %")
    figure.suptitle("Verbreitung von Post-Quanten-TLS", x=0.065, ha="left", fontweight="bold", fontsize=14)
    figure.tight_layout()
    figure.text(0.065, -0.05, f"Fehlerbalken: 95-%-Wilson-Intervall. {sample_note(n)}.", color=SECONDARY, fontsize=12)
    save_figure(figure, out_dir, "scan_pq_anteil")


def format_report(name, hosts, data, table, associations, conditional, criteria):
    lines = [f"# Auswertung {name}", ""]
    if len(data) < PILOT_BELOW_N:
        lines += [f"**Pilot mit n = {len(data)}. Zahlen dienen nur der Funktionsprüfung.**", ""]

    lines += ["## Ergebnis pro Host", "", "| Ergebnis | Anzahl |", "|---|---:|"]
    lines += [f"| {key} | {value} |" for key, value in hosts["pq_result"].value_counts().items()]
    lines += ["", f"In die Auswertung gehen {len(data)} von {len(hosts)} Hosts ein.", ""]
    flagged = hosts[hosts["inconsistent"] == "1"]["domain"].tolist()
    lines += [f"Widersprüchliche Hosts: {', '.join(flagged) if flagged else 'keine'}", ""]

    lines += ["## Anteile", "", "| Merkmal | Wert | n | PQ | Anteil | 95-%-Intervall |",
              "|---|---|---:|---:|---:|---:|"]
    for row in table.itertuples():
        lines.append(f"| {row.gruppe} | {row.wert} | {row.n} | {row.pq_ja} | {row.anteil:.0%} | "
                     f"{row.ci_low:.0%} bis {row.ci_high:.0%} |")

    supported = data[data["pq"]]
    preference = pd.crosstab(supported["hosting"], supported["preference"])
    lines += ["", "## Präferenz der Hosts mit Unterstützung", "",
              "| Hosting | " + " | ".join(preference.columns) + " |",
              "|---|" + "---:|" * len(preference.columns)]
    for hosting, row in preference.iterrows():
        lines.append(f"| {hosting} | " + " | ".join(str(value) for value in row) + " |")

    lines += ["", "## Tests", "", "| Merkmal | Test | p | Cramérs V |", "|---|---|---:|---:|"]
    for row in associations.itertuples():
        lines.append(f"| {row.merkmal} | {row.test} | {row.p:.3f} | {row.cramers_v:.2f} |")

    lines += ["", "## Geschichteter Permutationstest", "", "| Geprüft | Festgehalten | p |", "|---|---|---:|"]
    for row in conditional.itertuples():
        lines.append(f"| {row.merkmal} | {row.gehalten} | {row.p:.3f} |")

    lines += ["", "## H3", ""]
    lines += [f"- {text}: {'ja' if met else 'nein'}" for text, met in criteria.items()]
    return "\n".join(lines) + "\n"


def main():
    name = sys.argv[1]
    hosts = load_hosts(name)
    data = hosts[hosts["pq_result"].isin(ANSWERED)].copy()
    data["pq"] = data["pq_result"] == "ja"

    rng = np.random.default_rng(PERMUTATION_SEED)
    table = pd.DataFrame(shares(data, "kategorie", CATEGORIES) + shares(data, "hosting", HOSTING))
    associations = pd.DataFrame([association(data, "kategorie"), association(data, "hosting")])
    conditional = pd.DataFrame([stratified_permutation(data, "kategorie", "hosting", rng),
                                stratified_permutation(data, "hosting", "kategorie", rng)])
    criteria = judge_h3(associations, conditional)

    out_dir = REPO_DIR / "data" / "processed" / "scan" / name
    figures_dir = REPO_DIR / "figures" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    hosts.to_csv(out_dir / "hosts_classified.csv", index=False)
    table.to_csv(out_dir / "shares.csv", index=False)
    pd.concat([associations, conditional]).to_csv(out_dir / "tests.csv", index=False)
    report = format_report(name, hosts, data, table, associations, conditional, criteria)
    (out_dir / "report.md").write_text(report, encoding="utf-8")

    plot_hosting_by_category(data, figures_dir)
    plot_shares(table, len(data), figures_dir)
    print(report)


if __name__ == "__main__":
    main()
