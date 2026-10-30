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
CLIENT_IP = "172.30.0.20"
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
    Segmente auf einmal und tcpdump zeigt Pakete, die es so nie gäbe. Die ARP-Einträge werden
    fest gesetzt, weil ARP sonst selbst durch netem läuft und einzelne Läufe verzögert.
    """
    subprocess.run([*COMPOSE, "up", "-d", "--build"], check=True, capture_output=True)
    macs = {}
    for service in SERVICES:
        in_container(service, f"ethtool -K {IFACE} tso off gso off gro off")
        macs[service] = in_container(service, f"cat /sys/class/net/{IFACE}/address")
    in_container("client", f"ip neigh replace {SERVER_IP} lladdr {macs['server']} dev {IFACE} nud permanent")
    in_container("server", f"ip neigh replace {CLIENT_IP} lladdr {macs['client']} dev {IFACE} nud permanent")
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


def set_netem(delay_ms, loss_pct):
    for service in SERVICES:
        in_container(service, f"tc qdisc replace dev {IFACE} root netem delay {delay_ms:.2f}ms loss {loss_pct:g}%")


def apply_profile(profile):
    """Setzt netem auf beiden Seiten und gibt das Delay pro Richtung zurück.

    Jede Richtung bekommt die halbe RTT. Die Verlustrate gilt pro Paket in jeder Richtung, wie
    auf einer echten Strecke. In der VM wachen die netem-Timer rund 1,2 ms zu spät auf, deshalb
    wird der Aufschlag verlustfrei per Ping gemessen und vom Delay abgezogen.
    """
    target = profile["rtt_ms"]
    delay = target / 2
    set_netem(delay, 0)
    if target > 0:
        overhead = ping_check()["ping_rtt_ms"] - target
        delay = max((target - overhead) / 2, 0)
    set_netem(delay, profile["loss_pct"])
    return delay


def ping_check(count=300):
    """Prüft die eingestellte RTT und den Verlust unabhängig von TLS."""
    out = in_container("client", f"ping -q -n -c {count} -i 0.02 -W 2 {SERVER_IP} || true")
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


def power_source():
    """Gibt die Stromquelle des Macs zurück, auf anderen Systemen "unbekannt"."""
    if platform.system() != "Darwin":
        return "unbekannt"
    result = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, check=False)
    return "Netzteil" if "AC Power" in result.stdout else "Akku"


def git_commit():
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_DIR,
                            capture_output=True, text=True, check=False)
    return result.stdout.strip()


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
