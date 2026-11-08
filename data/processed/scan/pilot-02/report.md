# Auswertung pilot-02

**Pilot mit n = 17. Zahlen dienen nur der Funktionsprüfung.**

## Ergebnis pro Host und Region

| Region | ja | nein | nein_nur_tls12 |
|---|---:|---:|---:|
| Asien | 2 | 0 | 2 |
| Europa | 3 | 1 | 0 |
| Nordamerika | 1 | 1 | 2 |
| Südostasien | 3 | 0 | 2 |

DNS erst über den Rückfall-Resolver aufgelöst: keine

## Anteile, Top 10 je Region und Branche

| Region | n | PQ | Anteil | 95-%-Intervall |
|---|---:|---:|---:|---:|
| Europa | 4 | 3 | 75% | 30% bis 95% |
| Nordamerika | 4 | 1 | 25% | 5% bis 70% |
| Asien | 4 | 2 | 50% | 15% bis 85% |
| Südostasien | 5 | 3 | 60% | 23% bis 88% |

Referenz: österreichische Zufallsstichprobe nan%.

| Region | Nachrichten | Onlineshops | Banken | Behörden | Hochschulen |
|---|---:|---:|---:|---:|---:|
| Österreich | – | – | – | – | – |
| Europa | 1/1 | – | 1/1 | 1/1 | 0/1 |
| Nordamerika | 1/1 | – | 0/1 | 0/1 | 0/1 |
| Asien | 0/1 | 1/1 | – | 0/1 | 1/1 |
| Südostasien | 1/1 | 1/1 | 1/1 | 0/1 | 0/1 |

## Hosting je Region (Top 10)

| Region | Cloudflare | Akamai | AWS | Andere CDN/Cloud | Sonstige/eigener Server |
|---|---:|---:|---:|---:|---:|
| Österreich | 0 | 0 | 0 | 0 | 0 |
| Europa | 1 | 1 | 1 | 0 | 1 |
| Nordamerika | 0 | 2 | 0 | 0 | 2 |
| Asien | 1 | 1 | 1 | 1 | 0 |
| Südostasien | 1 | 1 | 0 | 1 | 2 |

## H4: Hosting wirkt auch außerhalb Österreichs

Daten: 17 auswertbare Top-10-Hosts aus Europa, Nordamerika, Asien, Südostasien.

- CDN/Cloud: 9 von 12 (75%, 95-%-Intervall 47% bis 91%)
- Eigener/generischer Server: 0 von 5 (0%, 95-%-Intervall 0% bis 43%)

Geschichteter Permutationstest (Schicht Region × Branche): p = 1.000. Mantel-Haenszel-Odds-Ratio: inf.

- Geschichteter Permutationstest p < 0,05: nein
- Mantel-Haenszel-Odds-Ratio > 1 (CDN/Cloud häufiger mit PQ): ja

**H4 nicht bestätigt.**

## H5: Bei Akamai entscheidet der Client

| Hosting | server_waehlt_pq | folgt_client | server_waehlt_klassisch |
|---|---:|---:|---:|
| AWS | 2 | 0 | 0 |
| Akamai | 0 | 3 | 0 |
| Andere CDN/Cloud | 1 | 0 | 0 |
| Cloudflare | 3 | 0 | 0 |

Vierfeldertafel (Akamai/übrige × folgt Client ja/nein): [[3, 0], [0, 6]]. Fisher einseitig p = 0.012. Akamai folgt dem Client: 100%. Übrige wählen den Hybrid selbst: 100%.

- Fisher-Test einseitig p < 0,05: ja
- Mehrheit der Akamai-Hosts folgt dem Client: ja
- Mehrheit der übrigen Hosts wählt den Hybrid selbst: ja

**H5 bestätigt.**

## Explorativ: Regionen (Top 10 inklusive Österreich)

Nicht vorab als Hypothese festgelegt.

| Test | p | Cramérs V |
|---|---:|---:|
| Region (Top 10) | 0.744 | 0.36 |
| Region bei festem Hosting (geschichtete Permutation) | 1.000 |  |
| Hosting bei fester Region (geschichtete Permutation) | 0.404 |  |

## Wiederholung der österreichischen Zufallsstichprobe

0 von 0 Hosts mit gleichem Ergebnis wie in full-01.


## Plattformen (nur beschreibend)

| Domain | Ergebnis | Präferenz | Hosting |
|---|---|---|---|
