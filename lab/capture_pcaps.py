#!/usr/bin/env python3
"""Zeichnet eine Stichprobe von Handshakes als pcap auf (Teil A, Datenmenge).

Bewusst getrennt von run_experiment.py: tcpdump kostet CPU und soll die Zeitmessung nicht
beeinflussen. Beispiel: python3 lab/capture_pcaps.py --name pilot-01 --per-group 20
"""
import argparse
import subprocess
import sys
import time

import labctl

GROUPS = ["X25519", "X25519MLKEM768"]
PID_FILE = "/tmp/tcpdump.pid"


def capture(profile, group, args, pcap_dir):
    labctl.in_container("client", f"mkdir -p {pcap_dir}")
    pcap = f"{pcap_dir}/{profile['name']}_{group}.pcap"
    labctl.in_container(
        "client",
        f"nohup tcpdump -i {labctl.IFACE} -Z root -U -s 0 -w {pcap} 'tcp port 443' "
        f">/dev/null 2>&1 & echo $! > {PID_FILE}",
    )
    time.sleep(1)
    result = subprocess.run(
        [*labctl.COMPOSE, "exec", "-T", "client", "python3", "/lab/measure.py",
         "--profile", profile["name"], "--runs", str(args.per_group), "--warmup", "0",
         "--seed", str(args.seed), "--groups", group,
         "--out", f"{pcap_dir}/capture_log.csv"],
        capture_output=True, text=True, check=False,
    )
    time.sleep(1)
    labctl.in_container("client", f"kill -INT $(cat {PID_FILE})")
    time.sleep(1)
    if result.returncode != 0:
        sys.exit(f"Aufzeichnung {profile['name']}/{group} fehlgeschlagen:\n{result.stderr}")
    print(f"{profile['name']}/{group}: {args.per_group} Handshakes aufgezeichnet", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Messreihe, zu der die pcaps gehören")
    parser.add_argument("--per-group", type=int, required=True)
    parser.add_argument("--seed", type=int, default=20261111)
    parser.add_argument("--profiles", help="Komma-Liste, Standard: alle")
    args = parser.parse_args()

    if (labctl.RAW_DIR / args.name / "pcap").exists():
        sys.exit("pcap-Ordner existiert schon. Rohdaten werden nicht überschrieben.")

    labctl.keep_awake()
    labctl.start_testbed()
    for profile in labctl.select_profiles(args.profiles):
        labctl.apply_profile(profile)
        for group in GROUPS:
            capture(profile, group, args, f"/data/{args.name}/pcap")


if __name__ == "__main__":
    main()
