#!/usr/bin/env python3
"""Baut die Hostliste für den internationalen Vergleich (Teil B, Erweiterung).

Regel pro Region und Branche: die 10 Domains mit dem besten Rang in der Tranco-Liste PYK6J, die
das Kriterium der Branche erfüllen. Dieselbe Quelle wie für den österreichischen Rahmen, damit
die Auswahl nachprüfbar bleibt. Einschränkungen:

- höchstens eine Domain pro Marke und Region (amazon.de und amazon.fr sind derselbe Shop),
- höchstens 4 Domains pro Land und Zelle, sonst bestünde Europa nur aus GB und DE,
  Asien nur aus Indien und China,
- Domains ohne eigene Website und Domains, die das Kriterium nicht erfüllen, fallen mit
  Begründung heraus (AUSSCHLUSS unten).

Nachrichten, Onlineshops und Banken kommen aus dem Kandidatenpool
scan/international_kandidaten.csv (Rankings aus "Most websites.docx" plus Ergänzungen),
Behörden und Hochschulen aus Endungsregeln wie .gv.at in Österreich (REGELN unten).

Österreich: Top 10 je Branche aus scan/frame.csv nach demselben Prinzip. Dazu kommt die
Zufallsstichprobe aus scan/sites.csv, damit full-01 am selben Tag wiederholt wird.
Plattformen: globale Dienste, die in mindestens zwei Länderlisten der Recherche stehen, eine
Domain pro Konzern. Sie werden nur beschrieben und gehen in keinen Test ein.

Aufruf: python3 scan/build_international.py
Ergebnis: scan/sites_international.csv und scan/international_protokoll.csv
Braucht die vollständige Tranco-Liste, siehe scan/README.md.
"""
import collections
import csv
import pathlib
import re

SCAN_DIR = pathlib.Path(__file__).resolve().parent
REPO_DIR = SCAN_DIR.parent
TRANCO_LIST = "PYK6J"
TRANCO_FILE = REPO_DIR / "data" / "raw" / "scan" / "tranco" / TRANCO_LIST / "top1m.csv"
PER_CELL = 10
MAX_PER_COUNTRY = 4
RESERVE = 4
CATEGORIES = ["Nachrichten", "Onlineshops", "Banken", "Behörden", "Hochschulen"]
REGIONS = ["Europa", "Nordamerika", "Asien", "Südostasien"]

# Behörden und Hochschulen: Endungen bzw. Namen wie .gv.at in Österreich. Europa ohne Österreich,
# Asien ohne Südostasien, Südostasien sind die ASEAN-Länder mit eigener Endung.
REGELN = {
    ("Europa", "Behörden"): {
        r"(^|\.)gov\.uk$": "GB", r"(^|\.)nhs\.uk$": "GB", r"\.gouv\.fr$": "FR",
        r"^bund\.de$|^bundesregierung\.de$": "DE", r"(^|\.)admin\.ch$": "CH", r"\.gov\.it$": "IT",
        r"\.gob\.es$": "ES", r"(^|\.)gov\.pl$": "PL", r"^europa\.eu$": "EU",
        r"^rijksoverheid\.nl$|^overheid\.nl$": "NL", r"\.belgium\.be$": "BE", r"\.gov\.ie$": "IE",
        r"\.gov\.pt$": "PT"},
    ("Europa", "Hochschulen"): {
        r"\.ac\.uk$": "GB", r"^(ethz|epfl|unige|uzh|unibe|unibas)\.ch$": "CH",
        r"^(tum|lmu|uni-[a-z]+|hu-berlin|fu-berlin|tu-berlin|kit|rwth-aachen|tu-dresden|tu-darmstadt)\.de$": "DE",
        r"^(sorbonne-universite|universite-paris-saclay|u-paris|univ-[a-z-]+|psl|polytechnique)\.(fr|eu|edu)$": "FR",
        r"^(unibo|uniroma1|polimi|unimi|unipd|unito|unina|unifi|unipi)\.it$": "IT",
        r"^(uva|tudelft|uu|rug|leidenuniv|universiteitleiden|eur|vu|ru|tue|utwente|wur)\.nl$": "NL",
        r"^(ucm|ub|uab|uam|us|uv|ugr|upm|upc)\.(es|edu|cat)$": "ES",
        r"^(kuleuven|ugent|uantwerpen|ulb|uliege|uclouvain)\.be$": "BE",
        r"^(ku|au|dtu|sdu)\.dk$": "DK", r"^(kth|lu|uu|su|gu|chalmers|ki)\.se$": "SE",
        r"^(helsinki|aalto|tuni|utu|jyu|oulu)\.fi$": "FI", r"^(uio|ntnu|uib)\.no$": "NO",
        r"^(cuni|muni|cvut|vut)\.cz$": "CZ", r"^(uw|uj|pw)\.edu\.pl$": "PL", r"^(tcd|ucd)\.ie$": "IE",
        r"^(ulisboa|up|uc|uminho)\.pt$": "PT"},
    ("Nordamerika", "Behörden"): {r"\.gov$": "US", r"^canada\.ca$|\.gc\.ca$": "CA", r"(^|\.)gob\.mx$": "MX"},
    ("Nordamerika", "Hochschulen"): {
        r"\.edu$": "US",
        r"^(utoronto|ubc|mcgill|uwaterloo|ualberta|yorku|ucalgary|queensu|uottawa|umontreal|ulaval|mcmaster|uwo|sfu|concordia|dal|usask|umanitoba|torontomu|carleton)\.ca$": "CA",
        r"^(unam|ipn|tec|udg|uanl|buap|uv)\.mx$": "MX"},
    ("Asien", "Behörden"): {
        r"\.go\.jp$": "JP", r"\.go\.kr$": "KR", r"(^|\.)gov\.cn$": "CN", r"\.gov\.in$|\.nic\.in$": "IN",
        r"\.gov\.tw$": "TW", r"\.gov\.hk$": "HK", r"\.gov\.bd$": "BD", r"\.gov\.pk$": "PK"},
    ("Asien", "Hochschulen"): {
        r"\.ac\.jp$": "JP", r"\.edu\.cn$": "CN", r"\.ac\.kr$": "KR", r"\.ac\.in$|\.edu\.in$": "IN",
        r"\.edu\.tw$": "TW", r"\.edu\.hk$|^hku\.hk$": "HK", r"\.ac\.bd$|\.edu\.bd$": "BD", r"\.edu\.pk$": "PK"},
    ("Südostasien", "Behörden"): {
        r"\.go\.id$": "ID", r"\.gov\.vn$": "VN", r"\.go\.th$": "TH", r"\.gov\.my$": "MY",
        r"\.gov\.sg$": "SG", r"\.gov\.ph$": "PH"},
    ("Südostasien", "Hochschulen"): {
        r"\.ac\.id$": "ID", r"\.edu\.vn$": "VN", r"\.ac\.th$": "TH", r"\.edu\.my$|^(ukm|usm|utm|uum)\.my$": "MY",
        r"\.edu\.sg$": "SG", r"\.edu\.ph$|^ateneo\.edu$": "PH"},
}

# Mehrere Domains derselben Stelle. Gilt nur für Behörden und Hochschulen, im Kandidatenpool
# steht die Marke in der Spalte "marke".
MARKEN = {
    "www.gov.uk": "gds", "service.gov.uk": "gds", "account.gov.uk": "gds",
    "legislation.gov.uk": "tna", "nationalarchives.gov.uk": "tna",
    "beian.gov.cn": "miit", "miit.gov.cn": "miit", "miitbeian.gov.cn": "miit", "miibeian.gov.cn": "miit",
    "gst.gov.in": "gstn", "ewaybillgst.gov.in": "gstn",
    "digitallocker.gov.in": "digilocker", "digilocker.gov.in": "digilocker",
    "upd.edu.ph": "up", "up.edu.ph": "up", "upm.edu.ph": "up",
    "e-tesda.gov.ph": "tesda", "tesda.gov.ph": "tesda",
    "overheid.nl": "rijksoverheid", "rijksoverheid.nl": "rijksoverheid",
    "kemendikdasmen.go.id": "kemendik", "kemdikbud.go.id": "kemendik",
}

# Geprüft am 8.11.2026 per DNS und HTTPS-Aufruf vom Mac aus (nur für die Liste, nicht Teil des Scans).
AUSSCHLUSS = {
    "infobae.com": "Betreiber in Argentinien, nicht Nordamerika",
    "academia.edu": "Plattform, keine Hochschule",
    "si.edu": "Museum, keine Hochschule",
    "nii.ac.jp": "Forschungsinstitut, keine Hochschule",
    "samarth.edu.in": "Verwaltungsplattform, keine Hochschule",
    "sinica.edu.tw": "Akademie der Wissenschaften, keine Hochschule",
    "tyc.edu.tw": "Schulbehörde", "tp.edu.tw": "Schulbehörde", "tc.edu.tw": "Schulbehörde",
    "nptel.ac.in": "Kursplattform, keine Hochschule",
    "inflibnet.ac.in": "Bibliotheksnetz, keine Hochschule",
    "delima.edu.my": "Plattform des Bildungsministeriums",
    "a-star.edu.sg": "Forschungsagentur", "moe.edu.sg": "Ministerium",
    "time.edu.cn": "Zeitdienst, keine Hochschule",
    "service.gov.uk": "Sammeldomain ohne eigene Website",
    "account.gov.uk": "Login-Dienst von gov.uk",
    "beian.gov.cn": "www löst auf 127.0.0.1 auf, die Domain hat keine Adresse",
    "global.gc.ca": "kein DNS-Eintrag für www und Domain",
    "qoo10.sg": "kein DNS-Eintrag für www und Domain",
}

# Aktuelle Hauptadresse statt Altdomain, wie tuwien.at statt tuwien.ac.at. Der Scanner folgt
# keinen Weiterleitungen. Indische Banken sind 2025/26 auf .bank.in umgezogen.
HAUPTADRESSE = {"onlinesbi.sbi": "onlinesbi.sbi.bank.in"}

PLATTFORMEN = [("google.com", "US"), ("facebook.com", "US"), ("chatgpt.com", "US"),
               ("wikipedia.org", "US"), ("reddit.com", "US"), ("x.com", "US"),
               ("tiktok.com", "SG"), ("yahoo.com", "US")]

FIELDS = ["domain", "kategorie", "quelle", "region", "land", "auswahl", "tranco_rang"]


def load_tranco():
    ranks = {}
    with open(TRANCO_FILE, encoding="utf-8") as fh:
        for line in fh:
            rank, domain = line.strip().split(",")
            ranks[domain] = int(rank)
    return ranks


def candidates(ranks):
    """Alle Kandidaten pro Zelle als (rang, domain, land, marke)."""
    cells = collections.defaultdict(list)
    with open(SCAN_DIR / "international_kandidaten.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["domain"] in ranks:
                cells[(row["region"], row["kategorie"])].append(
                    (ranks[row["domain"]], row["domain"], row["land"], row["marke"] or row["domain"]))
            else:
                print(f"nicht in Tranco: {row['domain']}")
    for cell, rules in REGELN.items():
        for domain, rank in ranks.items():
            for pattern, country in rules.items():
                if re.search(pattern, domain):
                    cells[cell].append((rank, domain, country, MARKEN.get(domain, domain)))
                    break
    return cells


def select(rows):
    """Wendet die Regeln an und gibt Auswahl und Protokoll zurück."""
    chosen, log, brands, countries = [], [], set(), collections.Counter()
    for rank, domain, country, brand in sorted(rows):
        if len(chosen) >= PER_CELL + RESERVE:
            break
        if domain in AUSSCHLUSS:
            status = f"ausgeschlossen: {AUSSCHLUSS[domain]}"
        elif brand in brands:
            status = f"ausgeschlossen: Marke schon vertreten ({brand})"
        elif countries[country] >= MAX_PER_COUNTRY:
            status = f"übersprungen: schon {MAX_PER_COUNTRY} aus {country}"
        else:
            status = "gewählt" if len(chosen) < PER_CELL else "Reserve"
            chosen.append((rank, domain, country))
            brands.add(brand)
            countries[country] += 1
        log.append((rank, domain, country, status))
    return chosen[:PER_CELL], log


def host_name(domain):
    domain = HAUPTADRESSE.get(domain, domain)
    return domain[4:] if domain.startswith("www.") else domain


def main():
    ranks = load_tranco()
    out, protocol = {}, []

    def add(domain, kategorie, rank, region, country, auswahl):
        if domain in out:
            out[domain]["auswahl"] += "+" + auswahl
            return
        out[domain] = {"domain": domain, "kategorie": kategorie, "region": region, "land": country,
                       "auswahl": auswahl, "tranco_rang": rank,
                       "quelle": f"Tranco {TRANCO_LIST}, Rang {rank}" if rank else "Recherche Kollegin/Kollege"}

    with open(SCAN_DIR / "frame.csv", newline="", encoding="utf-8") as fh:
        frame = list(csv.DictReader(fh))
    for kategorie in CATEGORIES:
        rows = sorted((r for r in frame if r["kategorie"] == kategorie), key=lambda r: int(r["tranco_rang"]))
        for row in rows[:PER_CELL]:
            add(row["domain"], kategorie, int(row["tranco_rang"]), "Österreich", "AT", "Top10")
            protocol.append(("Österreich", kategorie, row["tranco_rang"], row["domain"], "AT", "gewählt"))

    cells = candidates(ranks)
    for region in REGIONS:
        for kategorie in CATEGORIES:
            chosen, log = select(cells[(region, kategorie)])
            if len(chosen) < PER_CELL:
                print(f"Warnung: {region}/{kategorie} hat nur {len(chosen)} Domains")
            for rank, domain, country in chosen:
                add(host_name(domain), kategorie, rank, region, country, "Top10")
            protocol += [(region, kategorie, rank, domain, country, status) for rank, domain, country, status in log]

    with open(SCAN_DIR / "sites.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rank = int(re.search(r"Rang (\d+)", row["quelle"]).group(1))
            add(row["domain"], row["kategorie"], rank, "Österreich", "AT", "AT-Zufall")

    for domain, country in PLATTFORMEN:
        add(domain, "Plattformen", ranks.get(domain, ""), "Global", country, "Plattform")

    with open(SCAN_DIR / "sites_international.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(out.values())
    with open(SCAN_DIR / "international_protokoll.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["region", "kategorie", "tranco_rang", "domain", "land", "status"])
        writer.writerows(protocol)

    counts = collections.Counter((row["region"], row["auswahl"]) for row in out.values())
    for key, value in sorted(counts.items()):
        print(f"{key[0]:12} {key[1]:18} {value}")
    print(f"zusammen {len(out)} Hosts")


if __name__ == "__main__":
    main()
