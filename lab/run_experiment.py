#!/usr/bin/env python3
"""Misst Handshake-Dauern für alle Netzprofile (Teil A).

Beispiel Pilot:  python3 lab/run_experiment.py --name pilot-02 --runs 20 --warmup 5
Beispiel voll:   python3 lab/run_experiment.py --name full-01 --runs 1000 --warmup 50

Ergebnis in data/raw/lab/<name>/: handshakes.csv, server_log.tsv, checks.csv, manifest.json
"""
import argparse
import csv
import datetime as dt
import random
import subprocess
import sys

import labctl

FULL_RUN_MIN_RUNS = 200


def run_block(profile, args, run_dir):
    """Misst ein Profil und gibt die Kontrollwerte des Blocks zurück."""
    delay = labctl.apply_profile(profile)
    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    ping = labctl.ping_check()
    labctl.in_container("server", f"truncate -s 0 {labctl.SERVER_LOG}")
    before = labctl.read_counters()

    result = subprocess.run(
        [*labctl.COMPOSE, "exec", "-T", "client", "python3", "/lab/measure.py",
         "--profile", profile["name"], "--runs", str(args.runs), "--warmup", str(args.warmup),
         "--seed", str(args.seed), "--pause-ms", str(args.pause_ms),
         "--out", f"/data/{args.name}/handshakes.csv"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        sys.exit(f"Messblock {profile['name']} fehlgeschlagen:\n{result.stderr}")

    delta = labctl.counter_delta(before, labctl.read_counters())
    log = labctl.in_container("server", f"cat {labctl.SERVER_LOG}")
    with open(run_dir / "server_log.tsv", "a", encoding="utf-8") as fh:
        fh.write(log + "\n")

    finished = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    print(f"{profile['name']}: fertig ({started} bis {finished})", flush=True)
    return {"profile": profile["name"], "started_utc": started, "finished_utc": finished,
            "rtt_target_ms": profile["rtt_ms"], "loss_target_pct": profile["loss_pct"],
            "netem_delay_ms": round(delay, 2), "power_source": labctl.power_source(),
            **ping, **delta}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--runs", type=int, required=True, help="Messläufe pro Profil und Gruppe")
    parser.add_argument("--warmup", type=int, required=True, help="Aufwärmläufe pro Profil und Gruppe")
    parser.add_argument("--seed", type=int, default=20261111)
    parser.add_argument("--profiles", help="Komma-Liste, Standard: alle")
    parser.add_argument("--pause-ms", type=int, default=200,
                        help="Pause vor jedem Handshake, damit die CPU in allen Profilen gleich startet")
    args = parser.parse_args()

    run_dir = labctl.RAW_DIR / args.name
    if run_dir.exists():
        sys.exit(f"{run_dir} existiert schon. Rohdaten werden nicht überschrieben.")
    if args.runs >= FULL_RUN_MIN_RUNS and labctl.power_source() == "Akku":
        sys.exit("Vollmessung nur am Netzteil: Akkubetrieb ändert das Energieprofil der CPU.")

    labctl.keep_awake()
    labctl.start_testbed()
    run_dir.mkdir(parents=True)

    profiles = labctl.select_profiles(args.profiles)
    random.Random(f"{args.seed}:order").shuffle(profiles)
    print("Reihenfolge:", ", ".join(p["name"] for p in profiles), flush=True)

    manifest = {
        "name": args.name,
        "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "runs_per_cell": args.runs,
        "warmup_per_cell": args.warmup,
        "git_commit": labctl.git_commit(),
        "seed": args.seed,
        "pause_ms": args.pause_ms,
        "profile_order": [p["name"] for p in profiles],
        "versions": labctl.collect_versions(),
    }
    labctl.write_json(run_dir / "manifest.json", manifest)

    checks = []
    for profile in profiles:
        labctl.verify_testbed()
        checks.append(run_block(profile, args, run_dir))

    with open(run_dir / "checks.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(checks[0]))
        writer.writeheader()
        writer.writerows(checks)

    manifest["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    labctl.write_json(run_dir / "manifest.json", manifest)


if __name__ == "__main__":
    main()
