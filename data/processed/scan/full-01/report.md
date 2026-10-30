# Auswertung full-01

## Ergebnis pro Host

| Ergebnis | Anzahl |
|---|---:|
| ja | 66 |
| nein | 48 |
| nein_nur_tls12 | 6 |
| dns_fehler | 1 |
| nein_abbruch | 1 |

In die Auswertung gehen 121 von 122 Hosts ein.
Mit Post-Quanten-TLS: 66 (54.5%, 95-%-Intervall 45.7% bis 63.1%).

Widersprüchliche Hosts: keine

## Anteile

| Merkmal | Wert | n | PQ | Anteil | 95-%-Intervall |
|---|---|---:|---:|---:|---:|
| kategorie | Nachrichten | 25 | 14 | 56% | 37% bis 73% |
| kategorie | Onlineshops | 25 | 22 | 88% | 70% bis 96% |
| kategorie | Banken | 22 | 9 | 41% | 23% bis 61% |
| kategorie | Behörden | 24 | 14 | 58% | 39% bis 76% |
| kategorie | Hochschulen | 25 | 7 | 28% | 14% bis 48% |
| hosting | Cloudflare | 19 | 18 | 95% | 75% bis 99% |
| hosting | Akamai | 7 | 7 | 100% | 65% bis 100% |
| hosting | AWS | 3 | 3 | 100% | 44% bis 100% |
| hosting | Andere CDN/Cloud | 16 | 12 | 75% | 51% bis 90% |
| hosting | Sonstige/eigener Server | 76 | 26 | 34% | 25% bis 45% |

## Präferenz der Hosts mit Unterstützung

| Hosting | folgt_client | server_waehlt_klassisch | server_waehlt_pq |
|---|---:|---:|---:|
| AWS | 0 | 0 | 3 |
| Akamai | 7 | 0 | 0 |
| Andere CDN/Cloud | 4 | 0 | 8 |
| Cloudflare | 0 | 0 | 18 |
| Sonstige/eigener Server | 0 | 1 | 25 |

## Tests

| Merkmal | Test | p | Cramérs V |
|---|---|---:|---:|
| kategorie | Chi-Quadrat | < 0.001 | 0.41 |
| hosting | Fisher-Freeman-Halton | < 0.001 | 0.55 |

## Geschichteter Permutationstest

| Geprüft | Festgehalten | p |
|---|---|---:|
| kategorie | hosting | 0.012 |
| hosting | kategorie | < 0.001 |

## H3

- Hosting wirkt bei fester Branche (p < 0,05): ja
- Branche wirkt bei festem Hosting nicht (p ≥ 0,05): nein
- Cramérs V von Hosting größer als von Branche: ja

## Sensitivität: Betreiber statt Hosts (explorativ)

Jedes autonome System zählt pro Branche einmal, zusammen 69 Einheiten. Diese Analyse wurde nach dem Scan ergänzt und entscheidet nicht über H3.

| Geprüft | Festgehalten | p |
|---|---|---:|
| kategorie | hosting | 0.319 |
| hosting | kategorie | 0.018 |
