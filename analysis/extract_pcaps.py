#!/usr/bin/env python3
"""Liest die pcaps einer Messreihe mit tshark aus (Teil A, Datenmenge).

tshark läuft im tools-Container, damit lokal nichts installiert werden muss.
Aufruf: .venv/bin/python analysis/extract_pcaps.py pilot-02
Ergebnis in data/processed/lab/<name>/: pcap_connections.csv, handshake_sizes.csv, .md
"""
import io
import pathlib
import subprocess
import sys

import pandas as pd

REPO_DIR = pathlib.Path(__file__).resolve().parent.parent
COMPOSE = ["docker", "compose", "-f", str(REPO_DIR / "lab" / "docker-compose.yml")]
CLIENT_IP = "172.30.0.20"
GROUPS = ["X25519", "X25519MLKEM768"]

FIELDS = [
    "tcp.stream", "frame.time_epoch", "frame.len", "ip.src", "tcp.len", "tcp.flags.syn",
    "tcp.analysis.retransmission", "tcp.analysis.fast_retransmission",
    "tls.handshake.type", "tls.handshake.length",
]


def read_pcap(name, pcap):
    """Gibt eine Zeile pro Paket zurück."""
    command = [*COMPOSE, "run", "--rm", "-T", "--no-deps", "tools",
               "tshark", "-2", "-r", f"/repo/data/raw/lab/{name}/pcap/{pcap}",
               "-T", "fields", "-E", "header=y", "-E", "separator=/t",
               "-E", "occurrence=a", "-E", "aggregator=,"]
    for field in FIELDS:
        command += ["-e", field]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    packets = pd.read_csv(io.StringIO(result.stdout), sep="\t", dtype=str, keep_default_na=False)
    for field in ["frame.time_epoch", "frame.len", "tcp.len"]:
        packets[field] = pd.to_numeric(packets[field])
    packets["retrans"] = (packets["tcp.analysis.retransmission"] != "") | (
        packets["tcp.analysis.fast_retransmission"] != "")
    return packets


def hello_size(packets, message_type):
    """Größe einer Handshake-Nachricht inklusive 4 Byte Kopf."""
    for types, lengths in zip(packets["tls.handshake.type"], packets["tls.handshake.length"]):
        if message_type in types.split(","):
            return int(lengths.split(",")[types.split(",").index(message_type)]) + 4
    return None


def connection_metrics(packets):
    """Kennzahlen einer TCP-Verbindung.

    Der Handshake-Abschnitt endet mit dem ersten neuen Client-Paket nach Beginn der Serverantwort
    (Client-Finished). Am Client sind vom eigenen Sender verworfene Pakete nicht sichtbar, die
    Paketzahlen sind deshalb nur in verlustfreien Profilen exakt.
    """
    from_client = packets["ip.src"] == CLIENT_IP
    payload = packets["tcp.len"] > 0
    data = packets[payload]
    server_data = data[~from_client[payload]]
    if server_data.empty or not (from_client & payload).any():
        return None
    server_start = server_data["frame.time_epoch"].iloc[0]
    client_data = packets[from_client & payload & ~packets["retrans"]]
    client_hello = client_data[client_data["frame.time_epoch"] < server_start]
    finished = client_data[client_data["frame.time_epoch"] > server_start]
    if client_hello.empty or finished.empty:
        return None
    client_finished = finished["frame.time_epoch"].iloc[0]
    server_flight = server_data[server_data["frame.time_epoch"] < client_finished]
    server_new = server_flight[~server_flight["retrans"]]
    return {
        "client_hello_bytes": hello_size(packets, "1"),
        "server_hello_bytes": hello_size(packets, "2"),
        "client_flight_packets": len(client_hello),
        "client_flight_payload": int(client_hello["tcp.len"].sum()),
        "server_flight_packets": len(server_new),
        "server_flight_payload": int(server_new["tcp.len"].sum()),
        "connection_packets": len(packets),
        "connection_bytes": int(packets["frame.len"].sum()),
        "retransmissions": int(packets["retrans"].sum()),
        # Zeitabschnitte am Client-Interface, in ms
        "hello_to_server_ms": (server_start - client_hello["frame.time_epoch"].iloc[0]) * 1000,
        "server_span_ms": (server_flight["frame.time_epoch"].iloc[-1] - server_start) * 1000,
        "server_end_to_finished_ms": (client_finished - server_flight["frame.time_epoch"].iloc[-1]) * 1000,
    }


def main():
    name = sys.argv[1]
    out_dir = REPO_DIR / "data" / "processed" / "lab" / name
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for pcap in sorted((REPO_DIR / "data" / "raw" / "lab" / name / "pcap").glob("*.pcap")):
        profile, group = pcap.stem.split("_", 1)
        packets = read_pcap(name, pcap.name)
        for stream, connection in packets.groupby("tcp.stream", sort=False):
            metrics = connection_metrics(connection.reset_index(drop=True))
            if metrics:
                rows.append({"profile": profile, "group": group, "stream": stream, **metrics})
    connections = pd.DataFrame(rows)
    connections.to_csv(out_dir / "pcap_connections.csv", index=False)

    numeric = connections.columns.drop(["profile", "group", "stream"])
    sizes = connections.groupby(["profile", "group"])[list(numeric)].median().reset_index()
    sizes.insert(2, "n", connections.groupby(["profile", "group"]).size().values)
    sizes.to_csv(out_dir / "handshake_sizes.csv", index=False)

    ideal = sizes[sizes["profile"] == "ideal"].set_index("group")
    labels = {
        "client_hello_bytes": "ClientHello (Byte)",
        "server_hello_bytes": "ServerHello (Byte)",
        "client_flight_packets": "Pakete Client-Flight",
        "server_flight_packets": "Pakete Server-Flight",
        "client_flight_payload": "TCP-Nutzdaten Client-Flight (Byte)",
        "server_flight_payload": "TCP-Nutzdaten Server-Flight (Byte)",
        "connection_packets": "Pakete gesamte Verbindung",
        "connection_bytes": "Byte gesamte Verbindung (Frames)",
    }
    lines = ["| Kennzahl | X25519 | X25519MLKEM768 | Differenz |", "|---|---:|---:|---:|"]
    for column, label in labels.items():
        classic, hybrid = (int(ideal.loc[group, column]) for group in GROUPS)
        lines.append(f"| {label} | {classic} | {hybrid} | {hybrid - classic:+d} |")
    table = "\n".join(lines) + "\n"
    (out_dir / "handshake_sizes.md").write_text(table, encoding="utf-8")
    print(table)


if __name__ == "__main__":
    main()
