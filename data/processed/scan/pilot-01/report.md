# Auswertung pilot-01

**Pilot mit n = 20. Zahlen dienen nur der Funktionsprüfung.**

## Ergebnis pro Host

| Ergebnis | Anzahl |
|---|---:|
| ja | 12 |
| nein | 7 |
| nein_nur_tls12 | 1 |

In die Auswertung gehen 20 von 20 Hosts ein.

Widersprüchliche Hosts: keine

## Anteile

| Merkmal | Wert | n | PQ | Anteil | 95-%-Intervall |
|---|---|---:|---:|---:|---:|
| kategorie | Nachrichten | 4 | 3 | 75% | 30% bis 95% |
| kategorie | Onlineshops | 4 | 4 | 100% | 51% bis 100% |
| kategorie | Banken | 4 | 2 | 50% | 15% bis 85% |
| kategorie | Behörden | 4 | 1 | 25% | 5% bis 70% |
| kategorie | Hochschulen | 4 | 2 | 50% | 15% bis 85% |
| hosting | Cloudflare | 2 | 2 | 100% | 34% bis 100% |
| hosting | Akamai | 1 | 1 | 100% | 21% bis 100% |
| hosting | AWS | 1 | 1 | 100% | 21% bis 100% |
| hosting | Andere CDN/Cloud | 3 | 2 | 67% | 21% bis 94% |
| hosting | Sonstige/eigener Server | 13 | 6 | 46% | 23% bis 71% |

## Präferenz der Hosts mit Unterstützung

| Hosting | folgt_client | server_waehlt_pq |
|---|---:|---:|
| AWS | 0 | 1 |
| Akamai | 1 | 0 |
| Andere CDN/Cloud | 1 | 1 |
| Cloudflare | 0 | 2 |
| Sonstige/eigener Server | 0 | 6 |

## Tests

| Merkmal | Test | p | Cramérs V |
|---|---|---:|---:|
| kategorie | Fisher-Freeman-Halton | 0.421 | 0.52 |
| hosting | Fisher-Freeman-Halton | 0.729 | 0.43 |

## Geschichteter Permutationstest

| Geprüft | Festgehalten | p |
|---|---|---:|
| kategorie | hosting | 0.874 |
| hosting | kategorie | 1.000 |

## H3

- Hosting wirkt bei fester Branche (p < 0,05): nein
- Branche wirkt bei festem Hosting nicht (p ≥ 0,05): ja
- Cramérs V von Hosting größer als von Branche: nein
