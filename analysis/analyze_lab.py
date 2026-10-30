#!/usr/bin/env python3
"""Wertet eine Messreihe von Teil A aus.

Aufruf: .venv/bin/python analysis/analyze_lab.py pilot-03
Ergebnis: data/processed/lab/<name>/ (summary.csv, tests.csv, h2_contrasts.csv, report.md)
          figures/<name>/ (PNG und SVG)

Die Auswertungsregeln stehen im README unter "Vorab festgelegte Auswertung" und sind vor der
Vollmessung fixiert worden.
"""
import json
import pathlib
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator, ScalarFormatter
import numpy as np
import pandas as pd
from scipy import stats

REPO_DIR = pathlib.Path(__file__).resolve().parent.parent
CLASSIC = "X25519"
HYBRID = "X25519MLKEM768"
SERVER_CURVE = {CLASSIC: "X25519", HYBRID: "0x11ec"}

BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_SEED = 20261111
H1_MARGIN_MS = 1.0          # kleinster praktisch relevanter Unterschied
DELAYED_FACTOR = 1.5        # verzögert = länger als 1,5 × Median von X25519
MIN_RTT_FOR_DELAY = 100     # darunter sind Wiederholungen nicht sauber abgrenzbar
PILOT_BELOW_N = 200

PROFILES = ["ideal", "europa", "uebersee", "kontrolle", "mobil", "extrem"]
LOSS_SERIES = ["kontrolle", "mobil", "extrem"]   # gleiche RTT, nur der Verlust ändert sich
DURATION_TICKS = [100, 200, 500, 1000, 2000, 5000]

# Farben: reference palette der dataviz-Vorgaben, geprüft mit validate_palette.js
COLOR_GROUP = {CLASSIC: "#2a78d6", HYBRID: "#eb6834"}
COLOR_METRIC = {"Median": "#008300", "Mittelwert": "#6250d6", "p95": "#e87ba4"}
INK = "#0b0b0b"
SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
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
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "xtick.color": SECONDARY,
    "ytick.color": SECONDARY,
    "text.color": INK,
    "legend.frameon": False,
})


def p95(values, axis=None):
    return np.percentile(values, 95, axis=axis)


STATISTICS = {"Median": np.median, "Mittelwert": np.mean, "p95": p95}


def load_run(name):
    raw = REPO_DIR / "data" / "raw" / "lab" / name
    handshakes = pd.read_csv(raw / "handshakes.csv")
    server_log = pd.read_csv(raw / "server_log.tsv", sep="\t", header=None,
                             names=["request_id", "msec", "protocol", "cipher", "curve", "reused"])
    checks = pd.read_csv(raw / "checks.csv").set_index("profile")
    manifest = json.loads((raw / "manifest.json").read_text(encoding="utf-8"))
    return handshakes, server_log, checks, manifest


def verify_groups(handshakes, server_log):
    """Bricht ab, wenn ein erfolgreicher Handshake nicht wie erzwungen verhandelt wurde."""
    done = handshakes[handshakes["success"] == 1].merge(server_log, on="request_id", how="left")
    wrong = done[done["curve"] != done["group"].map(SERVER_CURVE)]
    resumed = done[done["reused"] != "."]
    not_tls13 = done[done["protocol"] != "TLSv1.3"]
    if len(wrong) or len(resumed) or len(not_tls13):
        sys.exit(f"Ungültige Läufe: {len(wrong)} falsche Gruppe, {len(resumed)} wiederaufgenommen, "
                 f"{len(not_tls13)} nicht TLS 1.3")


def split_groups(measured, profile):
    cell = measured[measured["profile"] == profile]
    return (cell.loc[cell["group"] == HYBRID, "handshake_ms"].to_numpy(),
            cell.loc[cell["group"] == CLASSIC, "handshake_ms"].to_numpy())


def resample(values, rng):
    return rng.choice(values, size=(BOOTSTRAP_SAMPLES, len(values)))


def bootstrap_difference(hybrid, classic, statistic, rng):
    """95-%-Perzentil-Intervall der Differenz hybrid minus klassisch."""
    differences = statistic(resample(hybrid, rng), axis=1) - statistic(resample(classic, rng), axis=1)
    return np.percentile(differences, [2.5, 97.5])


def holm(p_values):
    """Holm-Korrektur für mehrere Tests."""
    p_values = np.asarray(p_values, dtype=float)
    order = np.argsort(p_values)
    adjusted = np.empty(len(p_values))
    running_max = 0.0
    for rank, index in enumerate(order):
        running_max = max(running_max, (len(p_values) - rank) * p_values[index])
        adjusted[index] = min(running_max, 1.0)
    return adjusted


def summarize(handshakes):
    """Median, p95 und Erfolgsquote pro Profil und Gruppe."""
    runs = handshakes[handshakes["phase"] == "measure"]
    rows = []
    for (profile, group), cell in runs.groupby(["profile", "group"]):
        done = cell.loc[cell["success"] == 1, "handshake_ms"]
        rows.append({
            "profile": profile, "group": group, "n": len(cell), "success_rate": cell["success"].mean(),
            "median_ms": done.median(), "p95_ms": done.quantile(0.95), "p99_ms": done.quantile(0.99),
            "mean_ms": done.mean(), "min_ms": done.min(), "max_ms": done.max(),
        })
    return pd.DataFrame(rows)


def compare_groups(measured, checks, rng):
    """Mann-Whitney-U, Effektstärke und Differenzen mit Bootstrap-Intervall pro Profil."""
    rows = []
    for profile in PROFILES:
        if profile not in checks.index:
            continue
        hybrid, classic = split_groups(measured, profile)
        u_stat, p_value = stats.mannwhitneyu(hybrid, classic, alternative="two-sided")
        row = {
            "profile": profile, "p_mwu": p_value,
            # Rangbiseriale Korrelation, identisch mit Cliffs Delta. Positiv: hybrid langsamer.
            "rank_biserial": 2 * u_stat / (len(hybrid) * len(classic)) - 1,
        }
        for label, statistic in STATISTICS.items():
            low, high = bootstrap_difference(hybrid, classic, statistic, rng)
            row[f"delta_{label}_ms"] = statistic(hybrid) - statistic(classic)
            row[f"delta_{label}_low"] = low
            row[f"delta_{label}_high"] = high
        if checks.loc[profile, "loss_target_pct"] == 0:
            row["h1_within_margin"] = (row["delta_Median_low"] >= -H1_MARGIN_MS
                                       and row["delta_Median_high"] <= H1_MARGIN_MS)
        if checks.loc[profile, "rtt_target_ms"] >= MIN_RTT_FOR_DELAY:
            threshold = DELAYED_FACTOR * np.median(classic)
            slow_hybrid, slow_classic = (hybrid > threshold).sum(), (classic > threshold).sum()
            table = [[slow_hybrid, len(hybrid) - slow_hybrid], [slow_classic, len(classic) - slow_classic]]
            row["delayed_share_hybrid"] = slow_hybrid / len(hybrid)
            row["delayed_share_classic"] = slow_classic / len(classic)
            row["p_fisher_delayed"] = stats.fisher_exact(table)[1]
        rows.append(row)
    tests = pd.DataFrame(rows)
    tests["p_mwu_holm"] = holm(tests["p_mwu"])
    return tests


def h2_contrasts(measured, rng):
    """Differenz der Differenzen: Wächst der Nachteil mit dem Verlust gegenüber der Kontrolle?"""
    control_hybrid, control_classic = split_groups(measured, "kontrolle")
    rows = []
    for profile in ["mobil", "extrem"]:
        hybrid, classic = split_groups(measured, profile)
        for label, statistic in STATISTICS.items():
            point = (statistic(hybrid) - statistic(classic)
                     - statistic(control_hybrid) + statistic(control_classic))
            contrast = (statistic(resample(hybrid, rng), axis=1) - statistic(resample(classic, rng), axis=1)
                        - statistic(resample(control_hybrid, rng), axis=1)
                        + statistic(resample(control_classic, rng), axis=1))
            low, high = np.percentile(contrast, [2.5, 97.5])
            rows.append({"profile": profile, "metric": label, "contrast_ms": point,
                         "ci_low": low, "ci_high": high})
    return pd.DataFrame(rows)


def save_figure(figure, out_dir, stem):
    figure.savefig(out_dir / f"{stem}.png", dpi=200, bbox_inches="tight")
    figure.savefig(out_dir / f"{stem}.svg", bbox_inches="tight")
    plt.close(figure)


def sample_note(n):
    return f"Pilot mit n = {n} je Zelle, nicht belastbar" if n < PILOT_BELOW_N else f"n = {n} je Zelle"


def plot_overhead(tests, checks, n, out_dir):
    """Mehraufwand gegen Verlustrate bei fester RTT."""
    data = tests.set_index("profile").loc[LOSS_SERIES]
    loss = checks.loc[LOSS_SERIES, "loss_target_pct"].to_numpy()
    figure, axis = plt.subplots(figsize=(10, 5.6))
    axis.axhline(0, color=MUTED, linewidth=1)
    for offset, label in zip([-0.07, 0, 0.07], STATISTICS):
        values = data[f"delta_{label}_ms"].to_numpy()
        errors = [values - data[f"delta_{label}_low"].to_numpy(),
                  data[f"delta_{label}_high"].to_numpy() - values]
        axis.errorbar(loss + offset, values, yerr=errors, color=COLOR_METRIC[label], linewidth=2,
                      elinewidth=1.2, capsize=4, marker="o", markersize=8,
                      markeredgecolor=SURFACE, markeredgewidth=2, label=label)
        # Label rechts neben allen Fehlerbalken
        axis.annotate(label, (loss[-1] + 0.25, values[-1]), va="center", color=SECONDARY)
    axis.set_xticks(loss, [f"{value:g} %" for value in loss])
    axis.set_xlim(-0.4, loss[-1] + 1.1)
    axis.set_xlabel("Paketverlust je Richtung")
    axis.set_ylabel("Mehraufwand X25519MLKEM768 in ms")
    axis.legend(loc="lower left", bbox_to_anchor=(0, 1), ncols=3, borderaxespad=0.2)
    axis.set_title("Mehraufwand gegenüber X25519 bei 100 ms RTT", loc="left", fontweight="bold", pad=38)
    figure.text(0.125, -0.05, f"Fehlerbalken: 95-%-Bootstrap-Intervall. {sample_note(n)}.",
                color=SECONDARY, fontsize=12)
    save_figure(figure, out_dir, "lab_mehraufwand_verlust")


def plot_distribution(measured, checks, n, out_dir):
    """Verteilungen zeigen die Stufen durch Wiederholungen, die der Median verdeckt."""
    figure, axes = plt.subplots(1, len(LOSS_SERIES), figsize=(13, 5), sharex=True, sharey=True)
    for axis, profile in zip(axes, LOSS_SERIES):
        cell = measured[measured["profile"] == profile]
        for group, color in COLOR_GROUP.items():
            values = np.sort(cell.loc[cell["group"] == group, "handshake_ms"].to_numpy())
            values = np.insert(values, 0, values[0])
            share = np.arange(len(values)) / (len(values) - 1) * 100
            axis.step(values, share, where="post", color=color, linewidth=2, label=group)
        axis.set_xscale("log")
        axis.set_title(f"{checks.loc[profile, 'loss_target_pct']:g} % Verlust", loc="left",
                       fontsize=14, color=SECONDARY)
    longest = measured.loc[measured["profile"].isin(LOSS_SERIES), "handshake_ms"].max()
    axes[0].set_xlim(90, longest * 1.15)
    axes[0].set_xticks([tick for tick in DURATION_TICKS if tick <= longest * 1.15])
    axes[0].xaxis.set_major_formatter(ScalarFormatter())
    axes[0].xaxis.set_minor_locator(NullLocator())
    axes[0].set_ylabel("Anteil der Handshakes in %")
    axes[0].set_ylim(0, 101)
    axes[-1].legend(loc="lower right")
    figure.supxlabel("Handshake-Dauer in ms (logarithmische Skala)", y=-0.02, color=SECONDARY, fontsize=14)
    figure.suptitle("Verteilung der Handshake-Dauer bei 100 ms RTT", x=0.125, ha="left",
                    fontweight="bold", fontsize=14)
    figure.text(0.125, -0.08, f"{sample_note(n)}.", color=SECONDARY, fontsize=12)
    save_figure(figure, out_dir, "lab_verteilung_verlust")


def format_report(summary, tests, contrasts, checks, manifest):
    n = manifest["runs_per_cell"]
    lines = [f"# Auswertung {manifest['name']}", ""]
    if n < PILOT_BELOW_N:
        lines += [f"**Pilot mit n = {n} je Zelle. Zahlen dienen nur der Funktionsprüfung.**", ""]

    lines += ["## Manipulationskontrolle", "",
              "| Profil | RTT Soll | RTT Ping | Verlust Soll | Verlust real Client/Server |",
              "|---|---:|---:|---:|---:|"]
    for profile in PROFILES:
        if profile not in checks.index:
            continue
        row = checks.loc[profile]
        client = row["client_netem_dropped"] / max(row["client_netem_sent"] + row["client_netem_dropped"], 1)
        server = row["server_netem_dropped"] / max(row["server_netem_sent"] + row["server_netem_dropped"], 1)
        lines.append(f"| {profile} | {row['rtt_target_ms']:g} ms | {row['ping_rtt_ms']:.2f} ms | "
                     f"{row['loss_target_pct']:g} % | {client:.2%} / {server:.2%} |")

    lines += ["", "## Handshake-Dauer", "",
              "| Profil | Gruppe | n | Erfolg | Median | p95 | p99 | Mittelwert |",
              "|---|---|---:|---:|---:|---:|---:|---:|"]
    ordered = summary.assign(profile=pd.Categorical(summary["profile"], PROFILES)).sort_values(["profile", "group"])
    for row in ordered.itertuples():
        lines.append(f"| {row.profile} | {row.group} | {row.n} | {row.success_rate:.1%} | "
                     f"{row.median_ms:.2f} | {row.p95_ms:.2f} | {row.p99_ms:.2f} | {row.mean_ms:.2f} |")

    lines += ["", "## Gruppenvergleich (hybrid minus X25519, 95-%-Intervall)", "",
              "| Profil | Δ Median (ms) | Δ Mittelwert (ms) | Δ p95 (ms) | r_rb | p (Holm) |",
              "|---|---:|---:|---:|---:|---:|"]
    for row in tests.to_dict("records"):
        cells = [f"{row[f'delta_{label}_ms']:+.2f} [{row[f'delta_{label}_low']:+.2f}; {row[f'delta_{label}_high']:+.2f}]"
                 for label in STATISTICS]
        lines.append(f"| {row['profile']} | {' | '.join(cells)} | {row['rank_biserial']:+.2f} | "
                     f"{row['p_mwu_holm']:.3f} |")

    lines += ["", f"## H1: Liegt das Intervall von Δ Median ganz in ±{H1_MARGIN_MS:g} ms?", ""]
    for row in tests.dropna(subset=["h1_within_margin"]).itertuples():
        lines.append(f"- {row.profile}: {'ja' if row.h1_within_margin else 'nein'}")

    lines += ["", "## H2: Differenz der Differenzen gegenüber Kontrolle", "",
              "| Profil | Kennzahl | Kontrast (ms) | 95-%-Intervall |", "|---|---|---:|---:|"]
    for row in contrasts.itertuples():
        lines.append(f"| {row.profile} | {row.metric} | {row.contrast_ms:+.2f} | "
                     f"[{row.ci_low:+.2f}; {row.ci_high:+.2f}] |")

    delayed = tests.dropna(subset=["delayed_share_hybrid"])
    lines += ["", "## Anteil verzögerter Handshakes", "",
              f"Verzögert heißt länger als {DELAYED_FACTOR:g} × Median von X25519 im selben Profil.", "",
              "| Profil | X25519 | X25519MLKEM768 | p (Fisher) |", "|---|---:|---:|---:|"]
    for row in delayed.itertuples():
        lines.append(f"| {row.profile} | {row.delayed_share_classic:.1%} | "
                     f"{row.delayed_share_hybrid:.1%} | {row.p_fisher_delayed:.3f} |")
    return "\n".join(lines) + "\n"


def main():
    name = sys.argv[1]
    handshakes, server_log, checks, manifest = load_run(name)
    verify_groups(handshakes, server_log)

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    measured = handshakes[(handshakes["phase"] == "measure") & (handshakes["success"] == 1)]
    summary = summarize(handshakes)
    tests = compare_groups(measured, checks, rng)
    contrasts = h2_contrasts(measured, rng)

    out_dir = REPO_DIR / "data" / "processed" / "lab" / name
    figures_dir = REPO_DIR / "figures" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    summary.to_csv(out_dir / "summary.csv", index=False)
    tests.to_csv(out_dir / "tests.csv", index=False)
    contrasts.to_csv(out_dir / "h2_contrasts.csv", index=False)
    report = format_report(summary, tests, contrasts, checks, manifest)
    (out_dir / "report.md").write_text(report, encoding="utf-8")

    plot_overhead(tests, checks, manifest["runs_per_cell"], figures_dir)
    plot_distribution(measured, checks, manifest["runs_per_cell"], figures_dir)
    print(report)


if __name__ == "__main__":
    main()
