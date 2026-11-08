# Auswertung international-01

## Ergebnis pro Host und Region

| Region | dns_fehler | ja | nein | nein_abbruch | nein_nur_tls12 | nicht_erreichbar |
|---|---:|---:|---:|---:|---:|---:|
| Asien | 0 | 25 | 13 | 0 | 8 | 4 |
| Europa | 0 | 38 | 6 | 2 | 4 | 0 |
| Global | 0 | 7 | 1 | 0 | 0 | 0 |
| Nordamerika | 0 | 42 | 6 | 0 | 2 | 0 |
| Südostasien | 0 | 30 | 12 | 1 | 2 | 5 |
| Österreich | 1 | 71 | 49 | 1 | 9 | 0 |

DNS erst über den Rückfall-Resolver aufgelöst: unileoben.ac.at, gst.gov.in

## Anteile, Top 10 je Region und Branche

| Region | n | PQ | Anteil | 95-%-Intervall |
|---|---:|---:|---:|---:|
| Österreich | 50 | 27 | 54% | 40% bis 67% |
| Europa | 50 | 38 | 76% | 63% bis 86% |
| Nordamerika | 50 | 42 | 84% | 71% bis 92% |
| Asien | 46 | 25 | 54% | 40% bis 68% |
| Südostasien | 45 | 30 | 67% | 52% bis 79% |

Referenz: österreichische Zufallsstichprobe 55%.

| Region | Nachrichten | Onlineshops | Banken | Behörden | Hochschulen |
|---|---:|---:|---:|---:|---:|
| Österreich | 5/10 | 10/10 | 5/10 | 6/10 | 1/10 |
| Europa | 8/10 | 9/10 | 8/10 | 7/10 | 6/10 |
| Nordamerika | 10/10 | 10/10 | 10/10 | 6/10 | 6/10 |
| Asien | 7/10 | 7/10 | 4/9 | 2/7 | 5/10 |
| Südostasien | 6/10 | 5/8 | 10/10 | 4/7 | 5/10 |

## Hosting je Region (Top 10)

| Region | Cloudflare | Akamai | AWS | Andere CDN/Cloud | Sonstige/eigener Server |
|---|---:|---:|---:|---:|---:|
| Österreich | 8 | 7 | 2 | 4 | 29 |
| Europa | 6 | 18 | 5 | 8 | 13 |
| Nordamerika | 4 | 26 | 4 | 13 | 3 |
| Asien | 1 | 16 | 3 | 15 | 11 |
| Südostasien | 7 | 6 | 5 | 13 | 14 |

## H4: Hosting wirkt auch außerhalb Österreichs

Daten: 191 auswertbare Top-10-Hosts aus Europa, Nordamerika, Asien, Südostasien.

- CDN/Cloud: 128 von 150 (85%, 95-%-Intervall 79% bis 90%)
- Eigener/generischer Server: 7 von 41 (17%, 95-%-Intervall 9% bis 31%)

Geschichteter Permutationstest (Schicht Region × Branche): p = < 0.001. Mantel-Haenszel-Odds-Ratio: 86.5.

- Geschichteter Permutationstest p < 0,05: ja
- Mantel-Haenszel-Odds-Ratio > 1 (CDN/Cloud häufiger mit PQ): ja

**H4 bestätigt.**

## H5: Bei Akamai entscheidet der Client

| Hosting | server_waehlt_pq | folgt_client | server_waehlt_klassisch |
|---|---:|---:|---:|
| AWS | 16 | 0 | 0 |
| Akamai | 0 | 63 | 0 |
| Andere CDN/Cloud | 17 | 14 | 0 |
| Cloudflare | 18 | 0 | 0 |
| Sonstige/eigener Server | 6 | 1 | 0 |

Vierfeldertafel (Akamai/übrige × folgt Client ja/nein): [[63, 0], [15, 57]]. Fisher einseitig p = < 0.001. Akamai folgt dem Client: 100%. Übrige wählen den Hybrid selbst: 79%.

- Fisher-Test einseitig p < 0,05: ja
- Mehrheit der Akamai-Hosts folgt dem Client: ja
- Mehrheit der übrigen Hosts wählt den Hybrid selbst: ja

**H5 bestätigt.**

## Explorativ: Regionen (Top 10 inklusive Österreich)

Nicht vorab als Hypothese festgelegt.

| Test | p | Cramérs V |
|---|---:|---:|
| Region (Top 10) | 0.004 | 0.25 |
| Region bei festem Hosting (geschichtete Permutation) | 0.227 |  |
| Hosting bei fester Region (geschichtete Permutation) | < 0.001 |  |

## Wiederholung der österreichischen Zufallsstichprobe

121 von 122 Hosts mit gleichem Ergebnis wie in full-01.

| Domain | full-01 | jetzt | Hosting jetzt |
|---|---|---|---|
| fh-salzburg.ac.at | nein | ja | Sonstige/eigener Server |

## Plattformen (nur beschreibend)

| Domain | Ergebnis | Präferenz | Hosting |
|---|---|---|---|
| google.com | ja | server_waehlt_pq | Andere CDN/Cloud |
| facebook.com | ja | server_waehlt_pq | Sonstige/eigener Server |
| chatgpt.com | ja | server_waehlt_pq | Cloudflare |
| wikipedia.org | nein | keine_pq | Sonstige/eigener Server |
| reddit.com | ja | folgt_client | Andere CDN/Cloud |
| x.com | ja | server_waehlt_pq | Cloudflare |
| tiktok.com | ja | folgt_client | Akamai |
| yahoo.com | ja | server_waehlt_pq | Sonstige/eigener Server |
