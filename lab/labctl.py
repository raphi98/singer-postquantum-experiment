"""Gemeinsame Helfer der Laborskripte. Laufen auf dem Host, nur Standardbibliothek."""
import csv
import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import sys

LAB_DIR = pathlib.Path(__file__).resolve().parent
REPO_DIR = LAB_DIR.parent
RAW_DIR = REPO_DIR / "data" / "raw" / "lab"
COMPOSE = ["docker", "compose", "-f", str(LAB_DIR / "docker-compose.yml")]
SERVICES = ("server", "client")
SERVER_IP = "172.30.0.10"
IFACE = "eth0"
SERVER_LOG = "/var/log/lab/access.tsv"

OFFLOADS = {
    "tso": "tcp-segmentation-offload",
    "gso": "generic-segmentation-offload",
    "gro": "generic-receive-offload",
}
TCP_COUNTERS = [
    "TcpOutSegs", "TcpRetransSegs", "TcpExtTCPLossProbes", "TcpExtTCPTimeouts",
    "TcpExtTCPSynRetrans",
]


def load_profiles():
    with open(LAB_DIR / "profiles.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        row["rtt_ms"] = float(row["rtt_ms"])
        row["loss_pct"] = float(row["loss_pct"])
    return rows


def select_profiles(names):
    profiles = load_profiles()
    if not names:
        return profiles
    wanted = names.split(",")
    return [p for p in profiles if p["name"] in wanted]


def in_container(service, command):
    """Führt einen Befehl im Container aus und gibt stdout zurück."""
    result = subprocess.run(
        [*COMPOSE, "exec", "-T", service, "sh", "-c", command],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        sys.exit(f"Fehler in {service}: {command}\n{result.stdout}{result.stderr}")
    return result.stdout.strip()


def start_testbed():
    """Startet die Container und schaltet die Offloads ab.

    Ohne das fasst der Kernel Segmente zu Sammelpaketen zusammen: netem verwirft dann mehrere
    Segmente auf einmal und tcpdump zeigt Pakete, die es so nie gäbe.
    """
    subprocess.run([*COMPOSE, "up", "-d", "--build"], check=True, capture_output=True)
    for service in SERVICES:
        in_container(service, f"ethtool -K {IFACE} tso off gso off gro off")
    verify_testbed()


def verify_testbed():
    """Bricht ab, wenn eine Voraussetzung der Messung nicht erfüllt ist."""
    for service in SERVICES:
        mtu = in_container(service, f"cat /sys/class/net/{IFACE}/mtu")
        if mtu != "1500":
            sys.exit(f"{service}: MTU ist {mtu} statt 1500")
        features = in_container(service, f"ethtool -k {IFACE}")
        for name in OFFLOADS.values():
            if f"{name}: off" not in features:
                sys.exit(f"{service}: {name} ist nicht abgeschaltet")
        if in_container(service, "cat /proc/sys/net/ipv4/tcp_no_metrics_save") != "1":
            sys.exit(f"{service}: tcp_no_metrics_save ist nicht gesetzt")


def apply_profile(profile):
    """Setzt netem auf beiden Seiten.

    Jede Richtung bekommt die halbe RTT, zusammen ergibt das die Soll-RTT. Die Verlustrate gilt
    pro Paket in jeder Richtung, wie auf einer echten Strecke.
    """
    delay = profile["rtt_ms"] / 2
    loss = profile["loss_pct"]
    for service in SERVICES:
        in_container(service, f"tc qdisc replace dev {IFACE} root netem delay {delay:g}ms loss {loss:g}%")


def ping_check(count=300):
    """Prüft die eingestellte RTT und den Verlust unabhängig von TLS."""
    out = in_container("client", f"ping -q -n -c {count} -i 0.02 -w 30 {SERVER_IP} || true")
    sent, received = re.search(r"(\d+) packets transmitted, (\d+) received", out).groups()
    rtt = re.search(r"= [\d.]+/([\d.]+)/[\d.]+/([\d.]+) ms", out)
    return {
        "ping_sent": int(sent),
        "ping_received": int(received),
        "ping_rtt_ms": float(rtt.group(1)) if rtt else "",
        "ping_mdev_ms": float(rtt.group(2)) if rtt else "",
    }


def read_counters():
    """Liest netem- und TCP-Zähler beider Container."""
    counters = {}
    for service in SERVICES:
        qdisc = in_container(service, f"tc -s qdisc show dev {IFACE}")
        sent, dropped = re.search(r"Sent \d+ bytes (\d+) pkt \(dropped (\d+)", qdisc).groups()
        counters[f"{service}_netem_sent"] = int(sent)
        counters[f"{service}_netem_dropped"] = int(dropped)
        nstat = in_container(service, "nstat -asz")
        for name in TCP_COUNTERS:
            match = re.search(rf"^{name}\s+(\d+)", nstat, re.M)
            counters[f"{service}_{name}"] = int(match.group(1)) if match else 0
    return counters


def counter_delta(before, after):
    return {key: after[key] - before[key] for key in before}


def collect_versions():
    """Hält Software- und Hardwarestände für das Manifest fest."""
    packages = {
        "server": "nginx openssl libssl3t64 iproute2",
        "client": "curl libcurl4t64 openssl libssl3t64 iproute2 tcpdump",
    }
    versions = {
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "docker": subprocess.run(
                ["docker", "version", "--format", "{{.Client.Version}} / {{.Server.Version}}"],
                capture_output=True, text=True, check=False,
            ).stdout.strip(),
        },
    }
    if shutil.which("sysctl") and platform.system() == "Darwin":
        cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                             capture_output=True, text=True, check=False)
        versions["host"]["cpu"] = cpu.stdout.strip()
    for service in SERVICES:
        query = "dpkg-query -W -f '${Package}=${Version}\\n' " + packages[service]
        versions[service] = {
            "kernel": in_container(service, "uname -r"),
            "openssl": in_container(service, "openssl version"),
            "packages": in_container(service, query).splitlines(),
            "congestion_control": in_container(
                service, "cat /proc/sys/net/ipv4/tcp_congestion_control"),
        }
    versions["client"]["curl"] = in_container("client", "curl --version").splitlines()[0]
    versions["server"]["nginx"] = in_container("server", "nginx -v 2>&1")
    return versions


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def keep_awake():
    """Verhindert den Ruhezustand des Macs, solange dieser Prozess läuft."""
    if shutil.which("caffeinate"):
        subprocess.Popen(["caffeinate", "-ims", "-w", str(os.getpid())])
