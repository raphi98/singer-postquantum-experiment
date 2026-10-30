#!/usr/bin/env python3
"""Zieht aus scan/frame.csv eine geschichtete Zufallsstichprobe (Teil B).

Ist eine Kategorie kleiner als die gewünschte Anzahl, gehen alle ihre Domains ein (Vollerhebung).
Vor der Ziehung wird sortiert, damit das Ergebnis nur vom Inhalt des Rahmens und vom Seed abhängt.

Stichprobe: python3 scan/draw_sample.py --per-category 25 --seed 20261111 --out scan/sites.csv
Pilot:      python3 scan/draw_sample.py --per-category 4 --seed 1 --out scan/sites_pilot.csv
"""
import argparse
import csv
import pathlib
import random

SCAN_DIR = pathlib.Path(__file__).resolve().parent
TRANCO_LIST = "PYK6J"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-category", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    with open(SCAN_DIR / "frame.csv", newline="", encoding="utf-8") as fh:
        frame = list(csv.DictReader(fh))

    chosen = []
    for kategorie in sorted({row["kategorie"] for row in frame}):
        rows = sorted((r for r in frame if r["kategorie"] == kategorie), key=lambda r: r["domain"])
        rng = random.Random(f"{args.seed}:{kategorie}")
        sample = rng.sample(rows, min(args.per_category, len(rows)))
        print(f"{kategorie}: {len(sample)} von {len(rows)}")
        chosen += sorted(sample, key=lambda r: int(r["tranco_rang"]))

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["domain", "kategorie", "quelle"])
        for row in chosen:
            writer.writerow([row["domain"], row["kategorie"],
                             f"Tranco {TRANCO_LIST}, Rang {row['tranco_rang']}"])


if __name__ == "__main__":
    main()
