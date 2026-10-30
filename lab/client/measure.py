#!/usr/bin/env python3
"""Führt einen Messblock (ein Netzprofil) im Client-Container aus.

Jeder Handshake ist ein eigener curl-Prozess, also frisch und ohne Wiederaufnahme.
Die Reihenfolge der Gruppen ist balanciert und zufällig, damit Drift (Wärme, Hintergrundlast
in der VM) beide Gruppen gleich trifft. Aufwärmläufe bleiben in der CSV und werden über
phase=warmup erst in der Auswertung verworfen.
"""
import argparse
import csv
import datetime as dt
import os
import random
import subprocess

GROUPS = ["X25519", "X25519MLKEM768"]
SERVER_NAME = "lab-server"
SERVER_IP = "172.30.0.10"

CURL_FIELDS = [
    ("time_namelookup_s", "%{time_namelookup}"),
    ("time_connect_s", "%{time_connect}"),
    ("time_appconnect_s", "%{time_appconnect}"),
    ("time_starttransfer_s", "%{time_starttransfer}"),
    ("time_total_s", "%{time_total}"),
    ("http_code", "%{http_code}"),
    ("curl_exit", "%{exitcode}"),
    ("error", "%{errormsg}"),
]
WRITE_OUT = "\t".join(fmt for _, fmt in CURL_FIELDS)

CSV_FIELDS = [
    "timestamp_utc", "request_id", "profile", "group", "phase", "run", "seq",
    *[name for name, _ in CURL_FIELDS],
    "handshake_ms", "success",
]


def curl_command(group, request_id):
    return [
        "curl", "-q", "--silent", "--output", "/dev/null",
        "--http1.1", "--tlsv1.3", "--tls-max", "1.3",
        "--curves", group,
        "--cacert", "/certs/root.pem",   # nur eine Wurzel: der System-Store würde mitgemessen
        "--no-sessionid", "--no-keepalive",
        "--resolve", f"{SERVER_NAME}:443:{SERVER_IP}",   # kein DNS im Messpfad
        "--connect-timeout", "20", "--max-time", "30",
        "--write-out", WRITE_OUT,
        f"https://{SERVER_NAME}/?id={request_id}",
    ]


def measure(args):
    rng = random.Random(f"{args.seed}:{args.profile}")
    groups = args.groups.split(",")
    warmup = groups * args.warmup
    runs = groups * args.runs
    rng.shuffle(warmup)
    rng.shuffle(runs)
    plan = [("warmup", g) for g in warmup] + [("measure", g) for g in runs]

    new_file = not os.path.exists(args.out)
    counters = {}
    with open(args.out, "a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        if new_file:
            writer.writeheader()
        for seq, (phase, group) in enumerate(plan, start=1):
            run = counters[(phase, group)] = counters.get((phase, group), 0) + 1
            request_id = f"{args.profile}-{seq}"
            stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")
            result = subprocess.run(
                curl_command(group, request_id), capture_output=True, text=True, check=False
            )
            values = result.stdout.split("\t")
            row = dict(zip([name for name, _ in CURL_FIELDS], values))
            connect = float(row.get("time_connect_s") or 0)
            appconnect = float(row.get("time_appconnect_s") or 0)
            ok = row.get("curl_exit") == "0" and row.get("http_code") == "200" and appconnect > 0
            row.update(
                timestamp_utc=stamp, request_id=request_id, profile=args.profile, group=group,
                phase=phase, run=run, seq=seq,
                handshake_ms=f"{(appconnect - connect) * 1000:.3f}" if ok else "",
                success=int(ok),
                error=row.get("error", "") or result.stderr.strip(),
            )
            writer.writerow(row)
    print(f"{args.profile}: {len(plan)} Handshakes geschrieben")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--runs", type=int, required=True, help="Messläufe pro Gruppe")
    parser.add_argument("--warmup", type=int, required=True, help="Aufwärmläufe pro Gruppe")
    parser.add_argument("--seed", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--groups", default=",".join(GROUPS))
    measure(parser.parse_args())


if __name__ == "__main__":
    main()
