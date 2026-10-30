#!/usr/bin/env python3
"""Prüft die Post-Quanten-Unterstützung der Hosts aus einer sites.csv (Teil B).

Läuft im Container über scan/run_scan.py. Nur TLS-Handshakes, kein HTTP, höchstens ein Host pro
Sekunde. Pro Host laufen vier Handshakes:

  kontrolle         Standardeinstellungen. Ist der Host erreichbar, welche TLS-Version?
  nur_hybrid        TLS 1.3, nur X25519MLKEM768. Wird der Hybrid unterstützt?
  hybrid_zuerst     TLS 1.3, Key-Shares für beide Gruppen, Hybrid an erster Stelle
  klassisch_zuerst  TLS 1.3, Key-Shares für beide Gruppen, X25519 an erster Stelle

Die letzten beiden zusammen trennen echte Serverpräferenz vom bloßen Folgen der Client-Reihenfolge.
Beide bieten Key-Shares für beide Gruppen an, damit der Server ohne Extra-Runde frei wählen kann.

Bewertet wird immer die tatsächlich verhandelte Gruppe, nie der Exit-Code: Ohne -tls1_3 baut
openssl mit nur_hybrid auch klassische TLS-1.2-Verbindungen auf und meldet Erfolg.
"""
import argparse
import csv
import datetime as dt
import json
import pathlib
import platform
import re
import subprocess
import sys
import time

HYBRID = "X25519MLKEM768"
CLASSIC = "X25519"
HANDSHAKE_TIMEOUT_S = 12
DNS_TIMEOUT_S = 15
MIN_SECONDS_PER_HOST = 1.0
RETRY_PAUSE_S = 2.0
# Diese Ergebnisse könnten vorübergehend sein und werden genau einmal wiederholt.
RETRY_STATUSES = {"timeout", "unklar", "verbindung_abgebrochen"}

PROBES = {
    "kontrolle": [],
    "nur_hybrid": ["-tls1_3", "-groups", HYBRID],
    "hybrid_zuerst": ["-tls1_3", "-groups", f"*{HYBRID}:*{CLASSIC}"],
    "klassisch_zuerst": ["-tls1_3", "-groups", f"*{CLASSIC}:*{HYBRID}"],
}

HOST_FIELDS = [
    "started_utc", "domain", "kategorie", "quelle", "scanned_host", "www_fallback", "ip", "addresses",
    "cnames", "asn", "as_prefix", "as_country", "as_name", "tls_version", "pq_result", "preference",
    "cert_verified", "inconsistent",
]
PROBE_FIELDS = [
    "timestamp_utc", "domain", "host", "ip", "probe", "attempt", "status", "protocol", "group",
    "cipher", "cert_verified", "alert", "duration_ms", "output_tail",
]


def now_utc():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def run(command, timeout):
    """Gibt (Exit-Code, Ausgabe) zurück, bei Zeitüberschreitung (None, "")."""
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                errors="replace", timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return None, ""
    return result.returncode, result.stdout + result.stderr


def resolve(host):
    """Löst einen Namen auf und gibt die CNAME-Kette und die IPv4-Adressen zurück."""
    _, output = run(["dig", "+noall", "+answer", "+time=3", "+tries=2", "A", host], DNS_TIMEOUT_S)
    cnames, addresses = [], []
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 5 and fields[3] == "CNAME":
            cnames.append(fields[4].rstrip("."))
        elif len(fields) >= 5 and fields[3] == "A":
            addresses.append(fields[4])
    return cnames, addresses


def txt_record(name):
    _, output = run(["dig", "+short", "+time=3", "+tries=2", "TXT", name], DNS_TIMEOUT_S)
    return output.strip().strip('"')


def lookup_asn(ip):
    """Ordnet eine IP über den Dienst von Team Cymru ihrem autonomen System zu."""
    reversed_ip = ".".join(reversed(ip.split(".")))
    origin = [part.strip() for part in txt_record(f"{reversed_ip}.origin.asn.cymru.com").split("|")]
    if len(origin) < 3 or not origin[0]:
        return {"asn": "", "as_prefix": "", "as_country": "", "as_name": ""}
    asn = origin[0].split()[0]
    details = txt_record(f"AS{asn}.asn.cymru.com").split("|")
    return {"asn": asn, "as_prefix": origin[1], "as_country": origin[2],
            "as_name": details[-1].strip() if len(details) >= 5 else ""}


def parse_output(returncode, output):
    """Liest aus der Ausgabe von s_client, was wirklich verhandelt wurde."""
    protocol = re.search(r"^Protocol version: (TLSv[\d.]+)", output, re.M)
    group = re.search(r"^Negotiated TLS1\.3 group: (\S+)", output, re.M)
    temp_key = re.search(r"^Peer Temp Key: ([^,\s]+)", output, re.M)
    cipher = re.search(r"^Ciphersuite: (\S+)", output, re.M)
    alert = re.search(r"SSL alert number (\d+)", output)
    if returncode is None:
        status = "timeout"
    elif protocol:
        status = "handshake_ok"
    elif alert:
        status = "tls_alert"
    elif re.search(r"Connection refused|Connection timed out|No route to host|Network is unreachable",
                   output):
        status = "verbindung_fehlgeschlagen"
    elif re.search(r"unexpected eof|Connection reset|errno=104|errno=32|syscall failure", output):
        status = "verbindung_abgebrochen"
    else:
        # Auch eine leere Ausgabe landet hier und zählt nie als "nicht unterstützt".
        status = "unklar"
    return {
        "status": status,
        "protocol": protocol.group(1) if protocol else "",
        "group": group.group(1) if group else (temp_key.group(1) if temp_key else ""),
        "cipher": cipher.group(1) if cipher else "",
        "cert_verified": int("Verification: OK" in output),
        "alert": alert.group(1) if alert else "",
    }


def probe(domain, host, ip, name, writer):
    """Führt einen Handshake aus, bei unklarem Ausgang einmal wiederholt."""
    command = ["openssl", "s_client", "-connect", f"{ip}:443", "-servername", host, "-brief",
               "-verify_hostname", host, *PROBES[name]]
    for attempt in (1, 2):
        started = time.monotonic()
        returncode, output = run(command, HANDSHAKE_TIMEOUT_S)
        duration_ms = (time.monotonic() - started) * 1000
        parsed = parse_output(returncode, output)
        writer.writerow({
            "timestamp_utc": now_utc(), "domain": domain, "host": host, "ip": ip, "probe": name,
            "attempt": attempt, **parsed, "duration_ms": f"{duration_ms:.0f}",
            "output_tail": " | ".join(output.strip().splitlines()[-2:])[:300],
        })
        if parsed["status"] not in RETRY_STATUSES:
            break
        time.sleep(RETRY_PAUSE_S)
    return parsed


def choose_host(domain):
    """Bevorzugt www, weil Besucher dort landen. Die Domain ohne www ist die Rückfallebene."""
    for host in (f"www.{domain}", domain):
        cnames, addresses = resolve(host)
        if addresses:
            return host, cnames, addresses
    return None, [], []


def judge_support(control, hybrid):
    """Wird nur aufgerufen, wenn die Kontrolle klappte: "nein" setzt Erreichbarkeit voraus."""
    if hybrid["status"] == "handshake_ok":
        return "ja" if hybrid["group"] == HYBRID else "unklar"
    if control["protocol"] != "TLSv1.3":
        return "nein_nur_tls12"
    if hybrid["status"] == "tls_alert":
        return "nein"
    # Kontrolle klappt, nur der große ClientHello scheitert: Das ist selbst ein Befund.
    return "nein_abbruch"


def judge_preference(support, hybrid_first, classic_first):
    if support != "ja":
        return "keine_pq"
    groups = (hybrid_first["group"], classic_first["group"])
    if groups == (HYBRID, HYBRID):
        return "server_waehlt_pq"
    if groups == (HYBRID, CLASSIC):
        return "folgt_client"
    if groups == (CLASSIC, CLASSIC):
        return "server_waehlt_klassisch"
    return "unklar"


def scan_host(site, writer):
    domain = site["domain"]
    result = {"started_utc": now_utc(), "domain": domain, "kategorie": site["kategorie"],
              "quelle": site["quelle"]}
    host, cnames, addresses = choose_host(domain)
    if host is None:
        return {**result, "pq_result": "dns_fehler"}

    ip = addresses[0]
    control = probe(domain, host, ip, "kontrolle", writer)
    if control["status"] != "handshake_ok" and host.startswith("www."):
        # www existiert, antwortet aber nicht: Die Domain ohne www bekommt eine zweite Chance.
        apex_cnames, apex_addresses = resolve(domain)
        if apex_addresses:
            fallback = probe(domain, domain, apex_addresses[0], "kontrolle", writer)
            if fallback["status"] == "handshake_ok":
                host, cnames, addresses = domain, apex_cnames, apex_addresses
                ip, control = addresses[0], fallback

    support = "nicht_erreichbar"
    hybrid_first = classic_first = {"group": ""}
    if control["status"] == "handshake_ok":
        hybrid = probe(domain, host, ip, "nur_hybrid", writer)
        support = judge_support(control, hybrid)
        if control["protocol"] == "TLSv1.3":
            hybrid_first = probe(domain, host, ip, "hybrid_zuerst", writer)
            classic_first = probe(domain, host, ip, "klassisch_zuerst", writer)

    # Widerspruch deutet auf uneinheitliche Server hinter derselben Adresse hin.
    chose_hybrid = HYBRID in (hybrid_first["group"], classic_first["group"])
    return {
        **result, "scanned_host": host, "www_fallback": int(host == domain), "ip": ip,
        "addresses": " ".join(addresses), "cnames": " ".join(cnames), **lookup_asn(ip),
        "tls_version": control.get("protocol", ""), "pq_result": support,
        "preference": judge_preference(support, hybrid_first, classic_first),
        "cert_verified": control.get("cert_verified", 0),
        "inconsistent": int(chose_hybrid and support != "ja"),
    }


def preflight(writer):
    """Prüft das Messwerkzeug an einem bekannten Post-Quanten-Host.

    Eine TLS-Inspektion im eigenen Netz würde hier auffallen: Sie ersetzt das Zertifikat, und die
    Prüfung gegen den CA-Store des Containers schlägt fehl.
    """
    host = "pq.cloudflareresearch.com"
    _, addresses = resolve(host)
    if not addresses:
        sys.exit(f"Vorabprüfung: {host} nicht auflösbar. Stimmt die Netzverbindung?")
    hybrid = probe("vorabpruefung", host, addresses[0], "nur_hybrid", writer)
    if hybrid["group"] != HYBRID or not hybrid["cert_verified"]:
        sys.exit(f"Vorabprüfung fehlgeschlagen ({hybrid}). Scan abgebrochen: "
                 "Das Netz verfälscht TLS oder der Scanner arbeitet nicht korrekt.")
    print(f"Vorabprüfung bestanden: {host} verhandelt {hybrid['group']}", flush=True)


def tool_versions():
    return {
        "openssl": run(["openssl", "version"], 10)[1].strip(),
        "dig": run(["dig", "-v"], 10)[1].strip(),
        "python": platform.python_version(),
        "debian": pathlib.Path("/etc/debian_version").read_text(encoding="utf-8").strip(),
        "kernel": platform.release(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--sites", required=True)
    parser.add_argument("--git-commit", default="")
    args = parser.parse_args()

    out_dir = pathlib.Path("data/raw/scan") / args.name
    out_dir.mkdir(parents=True)
    with open(args.sites, newline="", encoding="utf-8") as fh:
        sites = list(csv.DictReader(fh))

    manifest = {"name": args.name, "sites_file": args.sites, "git_commit": args.git_commit,
                "started_utc": now_utc(), "hosts": len(sites), "probes": PROBES,
                "handshake_timeout_s": HANDSHAKE_TIMEOUT_S,
                "min_seconds_per_host": MIN_SECONDS_PER_HOST, "versions": tool_versions()}

    with open(out_dir / "probes.csv", "w", newline="", encoding="utf-8") as probes_file, \
            open(out_dir / "hosts.csv", "w", newline="", encoding="utf-8") as hosts_file:
        probe_writer = csv.DictWriter(probes_file, fieldnames=PROBE_FIELDS)
        host_writer = csv.DictWriter(hosts_file, fieldnames=HOST_FIELDS)
        probe_writer.writeheader()
        host_writer.writeheader()
        preflight(probe_writer)
        for position, site in enumerate(sites, start=1):
            started = time.monotonic()
            result = scan_host(site, probe_writer)
            host_writer.writerow(result)
            hosts_file.flush()
            probes_file.flush()
            print(f"{position}/{len(sites)} {site['domain']}: {result['pq_result']}", flush=True)
            time.sleep(max(0, MIN_SECONDS_PER_HOST - (time.monotonic() - started)))

    manifest["finished_utc"] = now_utc()
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                           encoding="utf-8")


if __name__ == "__main__":
    main()
