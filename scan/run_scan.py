#!/usr/bin/env python3
"""Startet den Scanner im Container (Teil B). Läuft auf dem Host, nur Standardbibliothek.

Beispiel: python3 scan/run_scan.py --name pilot-01 --sites scan/sites_pilot.csv
Ergebnis in data/raw/scan/<name>/: hosts.csv, probes.csv, manifest.json
"""
import argparse
import pathlib
import subprocess
import sys

REPO_DIR = pathlib.Path(__file__).resolve().parent.parent
COMPOSE = ["docker", "compose", "-f", str(REPO_DIR / "scan" / "docker-compose.yml")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--sites", required=True)
    args = parser.parse_args()

    if (REPO_DIR / "data" / "raw" / "scan" / args.name).exists():
        sys.exit(f"Messreihe {args.name} existiert schon. Rohdaten werden nicht überschrieben.")

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_DIR,
                            capture_output=True, text=True, check=False).stdout.strip()
    subprocess.run([*COMPOSE, "build", "--quiet"], check=True)
    subprocess.run(
        [*COMPOSE, "run", "--rm", "-T", "scanner", "python3", "scan/scan_tls.py",
         "--name", args.name, "--sites", args.sites, "--git-commit", commit],
        check=True,
    )


if __name__ == "__main__":
    main()
