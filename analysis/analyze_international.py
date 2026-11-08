#!/usr/bin/env python3
"""Wertet den internationalen Scan von Teil B aus (H4, H5 und Regionsvergleich).

Aufruf: .venv/bin/python analysis/analyze_international.py international-01
Ergebnis: data/processed/scan/<name>/ (hosts_classified.csv, shares.csv, tests.csv, report.md)
          figures/<name>/ (PNG und SVG)

Region, Land und Auswahl kommen aus der Hostliste, die im manifest.json des Scans steht.
Die Regeln für H4 und H5 stehen in scan/README.md und wurden vor dem Scan festgelegt.
Bestätigend getestet wird nur mit den Top-10-Hosts außerhalb Österreichs: Die Hypothesen
stammen aus full-01, die österreichischen Hosts wären also keine unabhängigen Daten.
"""
import json
import pathlib
import sys

import numpy as np
import pandas as pd
from scipy import stats

import analyze_scan as base
from analyze_scan import plt

REPO_DIR = base.REPO_DIR
REGIONS = ["Österreich", "Europa", "Nordamerika", "Asien", "Südostasien"]
INTERNATIONAL = REGIONS[1:]
CDN_CLASSES = ["Cloudflare", "Akamai", "AWS", "Andere CDN/Cloud"]
PREFERENCES = ["server_waehlt_pq", "folgt_client", "server_waehlt_klassisch"]
COLOR_CDN = "#2a78d6"
COLOR_OWN = "#eb6834"


def load(name):
    hosts = base.load_hosts(name)
    manifest = json.loads((REPO_DIR / "data" / "raw" / "scan" / name / "manifest.json").read_text())
    sites = pd.read_csv(REPO_DIR / manifest["sites_file"], dtype=str, keep_default_na=False)
    hosts = hosts.merge(sites[["domain", "region", "land", "auswahl", "tranco_rang"]], on="domain",
                        how="left", validate="one_to_one")
    if hosts["region"].eq("").any() or hosts["region"].isna().any():
        sys.exit("Hosts ohne Region: Hostliste und Scan passen nicht zusammen.")
    hosts["top10"] = hosts["auswahl"].str.contains("Top10")
    hosts["at_zufall"] = hosts["auswahl"].str.contains("AT-Zufall")
    hosts["cdn"] = hosts["hosting"].isin(CDN_CLASSES)
    hosts["zelle"] = hosts["region"] + "/" + hosts["kategorie"]
    return hosts, manifest


def answered(hosts):
    data = hosts[hosts["pq_result"].isin(base.ANSWERED)].copy()
    data["pq"] = data["pq_result"] == "ja"
    return data


def mantel_haenszel(data, factor, stratum):
    """Gepooltes Odds Ratio von factor auf pq über die Schichten."""
    numerator = denominator = 0.0
    for _, group in data.groupby(stratum):
        n = len(group)
        a = (group[factor] & group["pq"]).sum()
        b = (group[factor] & ~group["pq"]).sum()
        c = (~group[factor] & group["pq"]).sum()
        d = (~group[factor] & ~group["pq"]).sum()
        numerator += a * d / n
        denominator += b * c / n
    return numerator / denominator if denominator else np.inf


def test_h4(data, rng):
    """H4: CDN/Cloud gegen eigenen Server, Region und Branche festgehalten."""
    permutation = base.stratified_permutation(data, "cdn", "zelle", rng)
    odds = mantel_haenszel(data, "cdn", "zelle")
    shares = data.groupby("cdn")["pq"].agg(["sum", "count"])
    criteria = {
        "Geschichteter Permutationstest p < 0,05": permutation["p"] < base.ALPHA,
        "Mantel-Haenszel-Odds-Ratio > 1 (CDN/Cloud häufiger mit PQ)": odds > 1,
    }
    return permutation, odds, shares, criteria


def test_h5(data):
    """H5: Akamai folgt der Client-Reihenfolge, die übrigen Anbieter wählen den Hybrid selbst."""
    supported = data[data["pq"] & data["preference"].isin(PREFERENCES)].copy()
    supported["akamai"] = supported["hosting"] == "Akamai"
    supported["folgt"] = supported["preference"] == "folgt_client"
    table = [[int((supported["akamai"] & supported["folgt"]).sum()), int((supported["akamai"] & ~supported["folgt"]).sum())],
             [int((~supported["akamai"] & supported["folgt"]).sum()), int((~supported["akamai"] & ~supported["folgt"]).sum())]]
    p = stats.fisher_exact(table, alternative="greater").pvalue
    akamai = supported[supported["akamai"]]
    others = supported[~supported["akamai"]]
    akamai_follow = akamai["folgt"].mean() if len(akamai) else np.nan
    others_server = (others["preference"] == "server_waehlt_pq").mean() if len(others) else np.nan
    criteria = {
        "Fisher-Test einseitig p < 0,05": p < base.ALPHA,
        "Mehrheit der Akamai-Hosts folgt dem Client": akamai_follow > 0.5,
        "Mehrheit der übrigen Hosts wählt den Hybrid selbst": others_server > 0.5,
    }
    return supported, table, p, akamai_follow, others_server, criteria


def retest(hosts):
    """Vergleicht die österreichische Zufallsstichprobe mit full-01."""
    old = pd.read_csv(REPO_DIR / "data" / "processed" / "scan" / "full-01" / "hosts_classified.csv",
                      dtype=str, keep_default_na=False)[["domain", "pq_result", "hosting"]]
    new = hosts[hosts["at_zufall"]][["domain", "pq_result", "hosting"]]
    return old.merge(new, on="domain", suffixes=("_alt", "_neu"))


def plot_region_shares(top, reference, out_dir):
    rows = [(region, *base.wilson(group["pq"].sum(), len(group)), group["pq"].mean(), len(group))
            for region, group in top.groupby("region")]
    rows = sorted(rows, key=lambda row: row[3])
    figure, axis = plt.subplots(figsize=(10, 4.6))
    positions = np.arange(len(rows))
    values = np.array([row[3] for row in rows]) * 100
    errors = [values - np.array([row[1] for row in rows]) * 100, np.array([row[2] for row in rows]) * 100 - values]
    axis.errorbar(values, positions, xerr=errors, fmt="o", color=base.COLOR_SHARE, markersize=9,
                  markeredgecolor=base.SURFACE, markeredgewidth=2, elinewidth=1.4, capsize=4)
    for y, value in zip(positions, values):
        axis.text(value, y + 0.22, f"{value:.0f} %", ha="center", va="bottom", color=base.INK, fontsize=12)
    if not np.isnan(reference):
        axis.axvline(reference * 100, color=base.BASELINE, linewidth=1.4, linestyle="--")
        axis.text(reference * 100, len(rows) - 0.45, f" Österreich, Zufallsstichprobe: {reference:.0%}",
                  color=base.SECONDARY, fontsize=12, va="bottom")
    axis.set_yticks(positions, [f"{row[0]} (n = {row[4]})" for row in rows])
    axis.set_xlim(-3, 103)
    axis.set_ylim(-0.6, len(rows) - 0.1)
    axis.grid(axis="x")
    axis.tick_params(axis="y", length=0)
    axis.set_xlabel("Websites mit X25519MLKEM768 in %")
    axis.set_title("Post-Quanten-TLS auf den meistbesuchten Websites je Region", loc="left", fontweight="bold")
    figure.text(0.125, -0.06, "Top 10 je Region und Branche nach Tranco. Fehlerbalken: 95-%-Wilson-Intervall.",
                color=base.SECONDARY, fontsize=12)
    base.save_figure(figure, out_dir, "scan_int_pq_region")


def plot_hosting_by_region(top, out_dir):
    counts = pd.crosstab(top["region"], top["hosting"]).reindex(index=REGIONS, columns=base.HOSTING, fill_value=0)
    figure, axis = plt.subplots(figsize=(11, 5.4))
    positions = np.arange(len(REGIONS))[::-1]
    left = np.zeros(len(REGIONS))
    for hosting in base.HOSTING:
        values = counts[hosting].to_numpy()
        axis.barh(positions, values, left=left, height=0.56, color=base.COLOR_HOSTING[hosting],
                  edgecolor=base.SURFACE, linewidth=2, label=hosting)
        for y, value, start in zip(positions, values, left):
            if value >= 2:
                color = base.INK if hosting in ("AWS", "Andere CDN/Cloud") else "#ffffff"
                axis.text(start + value / 2, y, str(value), ha="center", va="center", color=color, fontsize=13)
        left += values
    axis.set_yticks(positions, REGIONS)
    axis.set_xlabel("Anzahl der Websites")
    axis.grid(axis="x")
    axis.tick_params(axis="y", length=0)
    axis.legend(loc="lower left", bbox_to_anchor=(0, 1), ncols=3, borderaxespad=0.2, fontsize=13)
    axis.set_title("Hosting der meistbesuchten Websites je Region", loc="left", fontweight="bold", pad=66)
    figure.text(0.125, -0.04, "Top 10 je Region und Branche, nur auswertbare Hosts. Klassen aus CNAME und ASN.",
                color=base.SECONDARY, fontsize=12)
    base.save_figure(figure, out_dir, "scan_int_hosting_region")


def plot_h4(top, out_dir):
    """Je Region der PQ-Anteil bei CDN/Cloud und bei eigenem Server, verbunden."""
    figure, axis = plt.subplots(figsize=(10, 5.6))
    positions = np.arange(len(REGIONS))[::-1]
    labelled = set()
    for y, region in zip(positions, REGIONS):
        group = top[top["region"] == region]
        points = []
        # CDN-Beschriftung über, die andere unter dem Punkt, damit nahe Werte nicht kollidieren.
        for flag, color, label, offset, align in ((True, COLOR_CDN, "CDN/Cloud", 0.2, "bottom"),
                                                  (False, COLOR_OWN, "Eigener/generischer Server", -0.2, "top")):
            subset = group[group["cdn"] == flag]
            if subset.empty:
                continue
            value = subset["pq"].mean() * 100
            points.append(value)
            axis.scatter(value, y, s=110, color=color, edgecolor=base.SURFACE, linewidth=2, zorder=3,
                         label=None if label in labelled else label)
            labelled.add(label)
            axis.text(value, y + offset, f"{value:.0f} % (n = {len(subset)})", ha="center", va=align,
                      color=base.SECONDARY, fontsize=11)
        if len(points) == 2:
            axis.plot(points, [y, y], color=base.BASELINE, linewidth=2, zorder=1)
    axis.set_yticks(positions, REGIONS)
    axis.set_xlim(-3, 108)
    axis.set_ylim(-0.7, len(REGIONS) - 0.3)
    axis.grid(axis="x")
    axis.tick_params(axis="y", length=0)
    axis.set_xlabel("Websites mit X25519MLKEM768 in %")
    axis.legend(loc="lower left", bbox_to_anchor=(0, 1), ncols=2, borderaxespad=0.2, fontsize=13)
    axis.set_title("Post-Quanten-TLS nach Hosting je Region (H4)", loc="left", fontweight="bold", pad=40)
    figure.text(0.125, -0.06, "Top 10 je Region und Branche. Getestet wird nur außerhalb Österreichs.",
                color=base.SECONDARY, fontsize=12)
    base.save_figure(figure, out_dir, "scan_int_h4_hosting")


def format_report(name, hosts, top, intl, h4, h5, region_tests, merged, platforms, reference):
    permutation, odds, h4_shares, h4_criteria = h4
    supported, table, h5_p, akamai_follow, others_server, h5_criteria = h5
    fmt = base.format_p
    lines = [f"# Auswertung {name}", ""]
    if len(top) < base.PILOT_BELOW_N:
        lines += [f"**Pilot mit n = {len(top)}. Zahlen dienen nur der Funktionsprüfung.**", ""]
    lines += ["## Ergebnis pro Host und Region", "",
              "| Region | " + " | ".join(sorted(hosts["pq_result"].unique())) + " |",
              "|---|" + "---:|" * hosts["pq_result"].nunique()]
    counts = pd.crosstab(hosts["region"], hosts["pq_result"])
    for region, row in counts.iterrows():
        lines.append(f"| {region} | " + " | ".join(str(v) for v in row) + " |")
    fallback = hosts[hosts["dns_resolver"] == "1.1.1.1"]["domain"].tolist() if "dns_resolver" in hosts else []
    lines += ["", f"DNS erst über den Rückfall-Resolver aufgelöst: {', '.join(fallback) or 'keine'}", ""]

    lines += ["## Anteile, Top 10 je Region und Branche", "",
              "| Region | n | PQ | Anteil | 95-%-Intervall |", "|---|---:|---:|---:|---:|"]
    for region in REGIONS:
        group = top[top["region"] == region]
        if group.empty:
            continue
        low, high = base.wilson(group["pq"].sum(), len(group))
        lines.append(f"| {region} | {len(group)} | {group['pq'].sum()} | {group['pq'].mean():.0%} | "
                     f"{low:.0%} bis {high:.0%} |")
    lines += ["", f"Referenz: österreichische Zufallsstichprobe {reference:.0%}.", "",
              "| Region | " + " | ".join(base.CATEGORIES) + " |", "|---|" + "---:|" * len(base.CATEGORIES)]
    for region in REGIONS:
        cells = []
        for category in base.CATEGORIES:
            group = top[(top["region"] == region) & (top["kategorie"] == category)]
            cells.append(f"{group['pq'].sum()}/{len(group)}" if len(group) else "–")
        lines.append(f"| {region} | " + " | ".join(cells) + " |")

    lines += ["", "## Hosting je Region (Top 10)", "", "| Region | " + " | ".join(base.HOSTING) + " |",
              "|---|" + "---:|" * len(base.HOSTING)]
    hosting = pd.crosstab(top["region"], top["hosting"]).reindex(index=REGIONS, columns=base.HOSTING, fill_value=0)
    for region, row in hosting.iterrows():
        lines.append(f"| {region} | " + " | ".join(str(v) for v in row) + " |")

    lines += ["", "## H4: Hosting wirkt auch außerhalb Österreichs", "",
              f"Daten: {len(intl)} auswertbare Top-10-Hosts aus {', '.join(INTERNATIONAL)}.", ""]
    for flag, label in ((True, "CDN/Cloud"), (False, "Eigener/generischer Server")):
        if flag in h4_shares.index:
            hits, n = h4_shares.loc[flag]
            low, high = base.wilson(hits, n)
            lines.append(f"- {label}: {hits} von {n} ({hits / n:.0%}, 95-%-Intervall {low:.0%} bis {high:.0%})")
    lines += ["", f"Geschichteter Permutationstest (Schicht Region × Branche): p = {fmt(permutation['p'])}. "
              f"Mantel-Haenszel-Odds-Ratio: {odds:.1f}.", ""]
    lines += [f"- {text}: {'ja' if met else 'nein'}" for text, met in h4_criteria.items()]
    lines += ["", f"**H4 {'bestätigt' if all(h4_criteria.values()) else 'nicht bestätigt'}.**", ""]

    lines += ["## H5: Bei Akamai entscheidet der Client", "",
              "| Hosting | " + " | ".join(PREFERENCES) + " |", "|---|" + "---:|" * len(PREFERENCES)]
    preference = pd.crosstab(supported["hosting"], supported["preference"]).reindex(columns=PREFERENCES, fill_value=0)
    for hosting_class, row in preference.iterrows():
        lines.append(f"| {hosting_class} | " + " | ".join(str(v) for v in row) + " |")
    lines += ["", f"Vierfeldertafel (Akamai/übrige × folgt Client ja/nein): {table}. "
              f"Fisher einseitig p = {fmt(h5_p)}. Akamai folgt dem Client: {akamai_follow:.0%}. "
              f"Übrige wählen den Hybrid selbst: {others_server:.0%}.", ""]
    lines += [f"- {text}: {'ja' if met else 'nein'}" for text, met in h5_criteria.items()]
    lines += ["", f"**H5 {'bestätigt' if all(h5_criteria.values()) else 'nicht bestätigt'}.**", ""]

    lines += ["## Explorativ: Regionen (Top 10 inklusive Österreich)", "",
              "Nicht vorab als Hypothese festgelegt.", "", "| Test | p | Cramérs V |", "|---|---:|---:|"]
    for label, result in region_tests.items():
        cramers = result.get("cramers_v", np.nan)
        lines.append(f"| {label} | {fmt(result['p'])} | {'' if pd.isna(cramers) else f'{cramers:.2f}'} |")

    lines += ["", "## Wiederholung der österreichischen Zufallsstichprobe", ""]
    same = merged["pq_result_alt"] == merged["pq_result_neu"]
    lines += [f"{same.sum()} von {len(merged)} Hosts mit gleichem Ergebnis wie in full-01.", ""]
    changed = merged[~same]
    if not changed.empty:
        lines += ["| Domain | full-01 | jetzt | Hosting jetzt |", "|---|---|---|---|"]
        lines += [f"| {r.domain} | {r.pq_result_alt} | {r.pq_result_neu} | {r.hosting_neu} |"
                  for r in changed.itertuples()]
    lines += ["", "## Plattformen (nur beschreibend)", "", "| Domain | Ergebnis | Präferenz | Hosting |",
              "|---|---|---|---|"]
    lines += [f"| {r.domain} | {r.pq_result} | {r.preference} | {r.hosting} |" for r in platforms.itertuples()]
    return "\n".join(lines) + "\n"


def main():
    name = sys.argv[1]
    hosts, _ = load(name)
    data = answered(hosts)
    top = data[data["top10"]]
    intl = top[top["region"].isin(INTERNATIONAL)]
    at_random = data[data["at_zufall"]]
    reference = at_random["pq"].mean() if len(at_random) else np.nan

    rng = np.random.default_rng(base.PERMUTATION_SEED)
    h4 = test_h4(intl, rng)
    h5 = test_h5(intl)
    region_tests = {
        "Region (Top 10)": base.association(top, "region"),
        "Region bei festem Hosting (geschichtete Permutation)": base.stratified_permutation(top, "region", "hosting", rng),
        "Hosting bei fester Region (geschichtete Permutation)": base.stratified_permutation(top, "hosting", "region", rng),
    }
    merged = retest(hosts)
    platforms = hosts[hosts["region"] == "Global"]

    out_dir = REPO_DIR / "data" / "processed" / "scan" / name
    figures_dir = REPO_DIR / "figures" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    hosts.to_csv(out_dir / "hosts_classified.csv", index=False)
    shares = pd.DataFrame(base.shares(top, "region", REGIONS) + base.shares(top, "kategorie", base.CATEGORIES)
                          + base.shares(top, "hosting", base.HOSTING))
    shares.to_csv(out_dir / "shares.csv", index=False)
    tests = pd.DataFrame([{"test": "H4", "p": h4[0]["p"], "odds_ratio": h4[1]},
                          {"test": "H5", "p": h5[2], "akamai_folgt": h5[3], "uebrige_server": h5[4]}]
                         + [{"test": label, **result} for label, result in region_tests.items()])
    tests.to_csv(out_dir / "tests.csv", index=False)
    report = format_report(name, hosts, top, intl, h4, h5, region_tests, merged, platforms, reference)
    (out_dir / "report.md").write_text(report, encoding="utf-8")

    plot_region_shares(top, reference, figures_dir)
    plot_hosting_by_region(top, figures_dir)
    plot_h4(top, figures_dir)
    print(report)


if __name__ == "__main__":
    main()
