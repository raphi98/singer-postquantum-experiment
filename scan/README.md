# Teil B: Feldstudie

**Forschungsfrage:** Wie verbreitet ist Post-Quanten-TLS auf österreichischen Websites, und hängt
das eher von der Branche oder vom Hosting/CDN ab?

**H3:** Die Branche spielt wenig Rolle, der CDN-Anbieter eine große.

## Aufbau

Der Scanner läuft im Container mit derselben OpenSSL-Version wie das Labor. Pro Host löst er den
Namen auf (zuerst `www.`, sonst ohne), bestimmt das autonome System der Adresse und führt vier
Handshakes gegen dieselbe IP aus:

| Probe | Angebot | Frage |
|---|---|---|
| `kontrolle` | Standardeinstellungen | Ist der Host erreichbar, welche TLS-Version? |
| `nur_hybrid` | TLS 1.3, nur X25519MLKEM768 | Wird der Hybrid unterstützt? |
| `hybrid_zuerst` | TLS 1.3, Key-Shares für beide, Hybrid vorne | Was wählt der Server? |
| `klassisch_zuerst` | TLS 1.3, Key-Shares für beide, X25519 vorne | Was wählt der Server? |

Ergebnis pro Host: `ja`, `nein`, `nein_nur_tls12`, `nein_abbruch` (nur der große ClientHello
scheitert), `unklar`, `nicht_erreichbar` oder `dns_fehler`. Die Präferenz ist `server_waehlt_pq`,
`folgt_client`, `server_waehlt_klassisch` oder `keine_pq`.

## Versionen

| Komponente | Stand |
|---|---|
| Basis-Image | `debian:13-slim` (Debian 13.7) per Digest fixiert, Paketquelle Snapshot 20261029T000000Z |
| OpenSSL | 3.5.7 |
| dig | 9.20.30 |
| ASN-Daten | Team Cymru (DNS-Abfrage zum Scan-Zeitpunkt) |
| Tranco-Liste | `PYK6J`, erstellt am 29.10.2026, Fenster 30.09. bis 29.10.2026, Top 1 Mio. |

Jeder Scan hält die Stände zusätzlich in `manifest.json` fest. Hardware spielt keine Rolle, weil
keine Zeiten ausgewertet werden. Anders als die Labormessung kann der Scan laufen, während am
Rechner gearbeitet wird.

## Stichprobe

**Status: Rahmen eingefroren und Stichprobe gezogen am 30.10.2026 (`scan/sites.csv`, 122 Hosts).
Die Prüfung in Schritt 3 hat nicht stattgefunden, das Team hat den Entwurf direkt freigegeben.**

1. **Grundgesamtheit:** alle `.at`-Domains der Tranco-Liste `PYK6J`, 3.097 Stück in
   `scan/tranco_PYK6J_at.csv`. Die Liste ist öffentlich und unter ihrer ID dauerhaft abrufbar,
   die Auswahl lässt sich also exakt nachprüfen.
2. **Rahmen:** Jede Domain wird nach den Kriterien unten höchstens einer Kategorie zugeordnet.
   Das passiert vor dem Scan und ohne Kenntnis der Ergebnisse.
3. **Prüfung:** Beide Teammitglieder gehen `scan/frame.csv` unabhängig durch, klären Abweichungen
   und committen den Rahmen. Ab dann ist er eingefroren.
4. **Ziehung:** Pro Kategorie 25 Domains per Zufall mit Seed 20261111. Banken haben nur 22 Kandidaten
   und gehen vollständig ein.
5. **Keine Nachbesserung:** `scan/sites.csv` wird danach nicht mehr geändert. Hosts, die nicht
   erreichbar sind, bleiben mit ihrem Status drin und werden nicht ersetzt.

```bash
python3 scan/draw_sample.py --per-category 25 --seed 20261111 --out scan/sites.csv
```

**Warum Zufall statt Top 25?** Tests setzen eine Zufallsauswahl voraus. Mit den Top 25 gälten die
Aussagen nur für genau diese Seiten, und die Größten sind vermutlich öfter bei CDNs. Das
Popularitätsmerkmal bleibt trotzdem erhalten: Der Rahmen besteht nur aus Domains, die es in die
weltweiten Top 1 Mio. schaffen. Das ÖWA-Ranking taugt als Gegenprobe für Nachrichten, deckt aber
Banken, Behörden und Shops nicht ab.

| Kategorie | Kandidaten | Kriterium |
|---|---:|---|
| Nachrichten | 42 | Redaktionelles Angebot mit aktueller allgemeiner, regionaler oder Wirtschaftsberichterstattung. Keine reinen Sport-, Lifestyle-, TV- oder Fachmedien und keine Presseportale. |
| Onlineshops | 94 | Verkauf an Privatkundinnen und -kunden mit eigenem Warenkorb unter der `.at`-Domain. Keine Kleinanzeigen, C2C-Marktplätze, Preisvergleiche oder B2B-Shops. Auch ausländische Betreiber zählen. |
| Banken | 22 | Kreditinstitut laut FMA-Unternehmensdatenbank. Eigene Online-Banking-Domains zählen separat. Keine Versicherungen, keine Zentralbank. Nicht gegen die FMA-Datenbank geprüft, siehe Limitationen. |
| Behörden | 40 | Regel: alle `.gv.at` aus der Liste, ohne Aliasse (`magwien`, `parlinkom`, `noel`, `land-oberoesterreich`). |
| Hochschulen | 48 | Universität, Fachhochschule, Privatuniversität oder Pädagogische Hochschule. Pro Einrichtung eine Domain, und zwar die aktuelle Hauptadresse statt Altdomains (`tuwien.at` statt `tuwien.ac.at`). |

## Reproduzieren

Voraussetzungen: Docker und Python 3. Das Netz darf TLS nicht aufbrechen, die Vorabprüfung bricht
sonst ab. Am besten aus einem normalen österreichischen Heimnetz scannen, ohne VPN.

```bash
python3 scan/run_scan.py --name full-01 --sites scan/sites.csv
```

```bash
.venv/bin/python analysis/analyze_scan.py full-01
```

Der Scan dauert rund 4 Minuten. Die vollständige Tranco-Liste (22 MB) liegt nicht im Repo:

```bash
curl -sSL -o data/raw/scan/tranco/PYK6J/top1m.csv https://tranco-list.eu/download/PYK6J/1000000
```

## Messentscheidungen

| Entscheidung | Begründung |
|---|---|
| Bewertet wird die verhandelte Gruppe, nie der Exit-Code | `www.orf.at` „besteht“ den reinen Hybrid-Test ohne `-tls1_3` mit Exit-Code 0, verhandelt aber TLS 1.2 mit DHE. Ein Prüfen auf Erfolg ergäbe ein falsches „ja“. |
| TLS 1.3 wird in allen Gruppentests erzwungen | Der Hybrid existiert nur in TLS 1.3. |
| Kontroll-Handshake vor jedem Test | „Nein“ ist nur gültig, wenn der Host sonst nachweislich antwortet. Eine Zeitüberschreitung ist etwas anderes als fehlende Unterstützung. |
| Präferenz in beiden Reihenfolgen, je mit Key-Shares für beide Gruppen | Sonst ist Serverpräferenz nicht von bloßem Folgen des Clients zu trennen. Im Pilot folgten Akamai und Fastly dem Client, ein Einzeltest hätte eine Präferenz vorgetäuscht. Key-Shares für beide ersparen dem Server die Extra-Runde, er kann also frei wählen. |
| Unklare Ergebnisse werden einmal wiederholt | Im Pilot brach `akbild.ac.at` beim ersten Versuch ab und unterstützte den Hybrid beim zweiten. Eine leere Ausgabe zählt nie als „nein“. |
| Zweiter Durchgang am Ende für `dns_fehler`, `nicht_erreichbar`, `unklar` und `nein_abbruch` | Diese Ergebnisse kann auch ein Netz-Aussetzer erzeugen, ein `nein` ist dagegen eine Antwort des Servers. Der erste Vollscan scheiterte an einem solchen Aussetzer. Die Regel steht vor dem ersten Ergebnis fest, gilt für alle Hosts gleich, und es zählt der letzte Durchgang. |
| Alle Handshakes eines Hosts gegen dieselbe IP | Die Hosting-Zuordnung gehört dann sicher zum getesteten Server. |
| `www.` zuerst, sonst ohne | Dort landen Besucher. HTTP-Weiterleitungen dürfen wegen der Vorgabe „nur Handshakes“ nicht verfolgt werden, deshalb stehen im Rahmen die aktuellen Hauptadressen. |
| Hosting aus CNAME und ASN, CNAME zuerst | Ein Akamai-Knoten im Netz eines Providers trägt dessen ASN. Die Zuordnung entsteht erst in der Auswertung aus `scan/hosting_rules.csv`, geänderte Regeln brauchen keinen neuen Scan. |
| Zusätzliche Klasse „Andere CDN/Cloud“ | **Ergänzung zur Vorgabe.** Sie umfasst CDNs und Hyperscaler, die TLS selbst beenden: Fastly, Microsoft, Google, Vercel, Imperva, Link11. In „Sonstige“ würden sie die Aussage zu H3 verwässern. Generische Hoster wie Hetzner, IONOS, OVH oder Exoscale bleiben bei „Sonstige“. Link11 kam nach dem Vollscan dazu, aber vor der Kreuztabelle mit den Ergebnissen. |
| Vorabprüfung gegen `pq.cloudflareresearch.com` | Sie weist nach, dass der Scanner funktioniert. Eine TLS-Inspektion im Netz fiele auf, weil die Zertifikatsprüfung gegen den CA-Store des Containers scheitert. |
| Höchstens ein Host pro Sekunde, 12 s Zeitlimit, kein HTTP | Der Scan belastet die Hosts nicht stärker als ein einzelner Seitenaufruf. Es werden nur öffentlich sichtbare Verbindungsparameter erhoben. |

## Vorab festgelegte Auswertung

Diese Regeln stehen vor dem Vollscan fest.

- **Unterstützt** heißt `pq_result = ja`. Alle `nein*`-Fälle zählen als nicht unterstützt.
  `unklar`, `nicht_erreichbar` und `dns_fehler` fallen aus der Auswertung und werden berichtet.
- **Anteile** pro Kategorie und Hosting-Klasse mit 95-%-Wilson-Intervall.
- **Tests:** Chi-Quadrat, wenn alle erwarteten Häufigkeiten mindestens 5 sind, sonst
  Fisher-Freeman-Halton. Effektstärke ist Cramérs V. SciPy rechnet Fisher-Freeman-Halton als
  Monte-Carlo-Test mit 9.999 Ziehungen. Den Seed 20261111 dafür gibt es erst seit dem 3.11.2026,
  vorher schwankte der p-Wert im Pilot in der zweiten Nachkommastelle. `full-01` ändert sich
  dadurch nicht.
- **Trennung der Merkmale:** Branche und Hosting hängen zusammen, Shops liegen öfter bei CDNs.
  Deshalb prüft ein geschichteter Permutationstest jedes Merkmal, während das andere festgehalten
  wird (10.000 Permutationen).
- **H3 gilt**, wenn alle drei Bedingungen erfüllt sind: Hosting wirkt bei fester Branche
  (p < 0,05), Branche wirkt bei festem Hosting nicht (p ≥ 0,05), und Cramérs V von Hosting ist
  größer als das der Branche. Ein p ≥ 0,05 belegt nicht, dass die Branche keine Rolle spielt. Es
  zeigt nur, dass diese Stichprobe keinen Effekt nachweist.

## Ergebnis des Vollscans `full-01`

Scan am 30.10.2026, 121 von 122 Hosts auswertbar (`register.gv.at` ohne DNS-Eintrag). Der
vollständige Bericht steht in `data/processed/scan/full-01/report.md`.

**66 von 121 Hosts (54,5 %, 95-%-Intervall 45,7 % bis 63,1 %) unterstützen X25519MLKEM768.**

| Branche | Anteil | | Hosting | Anteil |
|---|---:|---|---|---:|
| Onlineshops | 22 von 25 (88 %) | | Akamai | 7 von 7 (100 %) |
| Behörden | 14 von 24 (58 %) | | AWS | 3 von 3 (100 %) |
| Nachrichten | 14 von 25 (56 %) | | Cloudflare | 18 von 19 (95 %) |
| Banken | 9 von 22 (41 %) | | Andere CDN/Cloud | 12 von 16 (75 %) |
| Hochschulen | 7 von 25 (28 %) | | Sonstige/eigener Server | 26 von 76 (34 %) |

**H3 ist nach der festgelegten Regel nicht bestätigt, weil eine von drei Bedingungen fehlt.**

| Bedingung | Ergebnis | Erfüllt |
|---|---|---|
| Hosting wirkt bei fester Branche | p < 0,001 | ja |
| Branche wirkt bei festem Hosting nicht | p = 0,012 | **nein** |
| Cramérs V von Hosting größer als von Branche | 0,55 gegen 0,41 | ja |

Hosting ist der stärkere Faktor, die Branche hat aber einen eigenen Zusammenhang mit der
Verbreitung.

**Explorativ, nach dem Scan ergänzt und ohne Einfluss auf das Urteil:** Zählt jedes autonome System
pro Branche nur einmal (69 Einheiten), verschwindet der Branchen-Effekt (p = 0,319), der
Hosting-Effekt bleibt (p = 0,018). Das deutet darauf hin, dass der Branchen-Effekt an wenigen
Betreibern hängt, etwa am BRZ mit 6 von 6 Behörden-Seiten. Belegt ist das damit nicht.

**Weitere Befunde**

- Präferenz: 54 von 66 Hosts wählen den Hybrid unabhängig von der Client-Reihenfolge, 11 folgen dem
  Client, darunter alle 7 Akamai-Hosts. `edm.gv.at` unterstützt den Hybrid, wählt aber X25519.
- Cloudflare wirkt nicht automatisch: `hunkemoller.at` liegt dort, spricht aber nur TLS 1.2.
- 6 von 121 Hosts sprechen nur TLS 1.2.
- `modul.ac.at` beantwortet den Kontroll-Handshake, bricht bei nur_hybrid aber in beiden Durchgängen
  ab. `kontrast.at` hat ein Zertifikat, das die Prüfung nicht besteht.

## Störfaktoren und Limitationen

Laufende Liste, wird bei jedem Scan ergänzt.

**Aussagekraft**

- „Quantensicher“ gilt nur für die Schlüsselvereinbarung und schützt vor „jetzt speichern, später
  entschlüsseln“. Die Zertifikate bleiben klassisch.
- Es wird nur X25519MLKEM768 geprüft, nicht SecP256r1MLKEM768 oder ältere Kyber-Entwürfe.
- Der Scan ist eine Momentaufnahme. Anbieter stellen laufend um.

**Stichprobe**

- Der Rahmen `scan/frame.csv` beruht auf einer einzigen Zuordnung anhand der Domainnamen, ohne
  Prüfung durch eine zweite Person und ohne Abgleich mit der FMA-Datenbank. Nur die Behörden folgen
  einer festen Regel. Einzelne Zuordnungen können falsch sein, die Spalte `pruefung` weist sie als
  `entwurf` aus.
- Tranco bildet weltweite Popularität ab, nicht österreichische Nutzung.
- Der `.at`-Filter schließt österreichische Angebote unter anderen Endungen aus, etwa
  `erstegroup.com` oder `tt.com`, und nimmt ausländische Betreiber mit `.at` auf.
- Nur 22 Banken-Kandidaten. Einige Banken stehen in Tranco nicht unter `.at`.
- Die Hosts sind nicht unabhängig: Viele liegen beim selben Anbieter (BRZ, interneX, Russmedia).
  Die p-Werte fallen dadurch eher zu klein aus.
- Bei n ≈ 120 bleiben kleine Klassen dünn besetzt (AWS 3, Akamai 7), ihre Intervalle sind breit.
- Branche und Hosting überlappen kaum: Alle 24 Behörden und alle 25 Hochschulen liegen bei
  „Sonstige“, bei den Onlineshops nur eine Seite. Der Hosting-Effekt lässt sich daher nur bei
  Banken, Nachrichten und Shops innerhalb der Branche prüfen. Beide Merkmale sind nicht sauber
  trennbar, und kausale Aussagen sind mit diesem Design nicht möglich.

**Messung**

- Nur eine IPv4-Adresse pro Host und ein Standort. CDNs können je nach Region anders antworten.
- Eine `www`-Adresse kann auf anderen Servern liegen als die Hauptseite.
- Ohne HTTP sind Weiterleitungen unsichtbar, bei Altdomains misst man womöglich nur den Umleiter.
- Eine Web Application Firewall kann `openssl` anders behandeln als einen Browser.
- ASN und CNAME zeigen nicht jede Konstellation, etwa CDN hinter CDN oder Reverse-Proxies vor
  eigenen Servern. Vercel läuft auf AWS, beendet TLS aber selbst und zählt zu „Andere CDN/Cloud“.

## Verlauf der Scans

| Scan | Zweck | Status |
|---|---|---|
| `pilot-01` | 20 Hosts, 4 je Kategorie, Seed 1 | gültig, dient nur der Funktionsprüfung. Gezogen vor der Korrektur der Altdomains, enthält daher `tuwien.ac.at`. Auswertung am 3.11.2026 mit dem aktuellen Skript neu erzeugt. |
| `full-01` | 122 Hosts aus `scan/sites.csv`, Commit `79fbc8e` | gültig, 2 Hosts im zweiten Durchgang (`register.gv.at`, `modul.ac.at`), beide ohne Änderung. |
| `aborted-full-01` | erster Start des Vollscans | an der Vorabprüfung gescheitert: zwei Zeitüberschreitungen gegen `pq.cloudflareresearch.com` um 10:03. Kein Host wurde gescannt. Danach 12 von 12 Handshakes erfolgreich, die Ursache blieb ungeklärt. |
| `pilot-02` | 17 Reserve-Hosts aus dem Protokoll, nicht Teil der Liste, `scan/sites_international_pilot.csv` | gültig, dient nur der Funktionsprüfung von DNS-Rückfall, neuem Feld `dns_resolver` und Auswertung. 24 s für 17 Hosts, kein zweiter Durchgang. |
| `international-01` | Erweiterung, 339 Hosts aus `scan/sites_international.csv`, Commit `0a0977d` | gültig. Scan am 8.11.2026, 02:07 bis 02:31 Uhr, 24 Minuten. 14 Hosts im zweiten Durchgang, keiner mit geändertem Ergebnis. |

## Erweiterung: Internationaler Vergleich (`international-01`)

**Stand: vorab festgelegt am 8.11.2026, vor dem Scan (Commit `0a0977d`).** Bis einschließlich
„Limitationen der Erweiterung“ wurde nach dem Scan nichts geändert, außer der tatsächlichen
Scandauer. Das Ergebnis steht im eigenen Abschnitt danach.

**Forschungsfrage:** Wie verbreitet ist Post-Quanten-TLS auf den meistbesuchten Websites in
Europa, Nordamerika, Asien und Südostasien, und gilt der Hosting-Effekt aus Österreich auch dort?

| | Hypothese | Herkunft |
|---|---|---|
| **H4** | Auch außerhalb Österreichs unterstützen Websites hinter einem CDN- oder Cloud-Anbieter X25519MLKEM768 häufiger als Websites auf eigenen oder generischen Servern, und zwar bei gleicher Region und Branche. | `full-01`: 40 von 45 gegen 26 von 76. |
| **H5** | Ob der Hybrid zustande kommt, entscheidet bei Akamai der Client, bei den übrigen Anbietern der Server: Akamai-Hosts übernehmen die Gruppenreihenfolge des Clients, die übrigen Hosts mit Unterstützung wählen den Hybrid auch dann, wenn der Client X25519 zuerst nennt. | `full-01`: 7 von 7 Akamai-Hosts folgen dem Client, 54 von 59 übrigen wählen selbst. |

Beide Hypothesen stammen aus `full-01`. Bestätigend geprüft werden sie deshalb nur mit neuen,
davon unabhängigen Daten: den 200 Top-10-Hosts außerhalb Österreichs.

### Hostliste

```bash
python3 scan/build_international.py
```

Das Skript erzeugt `scan/sites_international.csv` (Scanliste) und `scan/international_protokoll.csv`
(jeder geprüfte Kandidat mit Rang und Entscheidung). Es ist deterministisch, braucht nur die
Tranco-Liste und schreibt bei gleichem Stand dieselbe Datei.

| Teil | Hosts | Regel |
|---|---:|---|
| Top 10 international | 200 | 4 Regionen × 5 Branchen × 10 Domains, jeweils die besten Ränge in Tranco `PYK6J`. |
| Top 10 Österreich | 50 | dieselbe Regel auf `scan/frame.csv`. 41 davon stehen schon in `scan/sites.csv`. |
| Zufallsstichprobe Österreich | 122 | `scan/sites.csv` unverändert, Wiederholung von `full-01` am selben Tag. |
| Plattformen | 8 | globale Dienste, die in mindestens zwei Länderlisten der Recherche stehen, eine Domain pro Konzern. Nur beschreibend. |

Zusammen 339 verschiedene Hosts. Jede Domain steht nur einmal in der Liste, die Spalte `auswahl`
zeigt, zu welchen Teilen sie gehört.

- **Regionen:** Europa ohne Österreich (EU/EWR, GB, CH), Nordamerika (US, CA, MX), Asien (Ost- und
  Südasien), Südostasien (ASEAN). Zugeordnet wird nach dem Markt der Domain, wie beim
  `.at`-Rahmen: `amazon.co.uk` gehört zu Europa, `amazon.com` zu Nordamerika.
- **Branchenkriterien** wie im österreichischen Rahmen. Behörden und Hochschulen über Endungen
  (`.gov`, `.gov.uk`, `.gouv.fr`, `.go.jp`, `.ac.uk`, `.edu`, `.edu.cn` usw., Liste in
  `build_international.py`), Nachrichten, Onlineshops und Banken aus dem Kandidatenpool
  `scan/international_kandidaten.csv`.
- **Höchstens eine Domain pro Marke und Region** (`amazon.de`/`amazon.fr`, `shopee.*`,
  `bbc.com`/`bbc.co.uk`). Eigene Online-Banking-Domains zählen separat, wie in Österreich.
- **Höchstens 4 Domains pro Land und Zelle.** Ohne diese Grenze bestünde Europa fast nur aus GB und
  DE, Asien aus Indien und China, Nordamerika nur aus den USA.
- **Ausschlüsse mit Begründung** stehen in `AUSSCHLUSS` im Skript und im Protokoll, etwa
  `academia.edu` (keine Hochschule) oder `beian.gov.cn` (keine öffentliche Adresse).
- **Hauptadresse:** `onlinesbi.sbi` leitet auf `onlinesbi.sbi.bank.in` um, gescannt wird die neue
  Adresse. Indische Banken sind auf `.bank.in` umgezogen.

**Warum Top 10 statt Zufall?** Für die anderen Regionen gibt es keinen geprüften Rahmen wie
`scan/frame.csv`, und das Team hat keine Zeit, Tausende Domains pro Land zu kategorisieren. Die
Top 10 sind eine feste, nachprüfbare Regel. Die Aussagen gelten damit für die meistbesuchten
Websites, nicht für alle Websites einer Region. Deshalb wird Österreich für den Regionsvergleich
mit derselben Regel ausgewählt und nicht mit der Zufallsstichprobe verglichen.

### Prüfung der Liste aus „Most websites.docx“

Die Recherche ist die Grundlage des Kandidatenpools. Für den Scan wurde sie so angepasst:

| Problem | Beispiele | Lösung |
|---|---|---|
| Keine Branche, sondern Behörde oder Portal | `acesso.gov.br`, `turkiye.gov.tr` und `mynet.com` unter Banken | entfernt |
| Kein Kreditinstitut | `finanzen.net`, `gold.de`, `durchblicker.at`, `wise.com`, `cash.app` | entfernt, Kriterium wie in Österreich |
| Falsche Region | `wise.com` unter Südostasien, `turkiye.gov.tr` unter Europa, `walmart.com` und `ozon.ru` unter Europa | nach Markt zugeordnet bzw. entfernt |
| Dieselbe Website in mehreren Regionen | `kompas.com`, `vnexpress.net`, `nus.edu.sg`, `amazon.com`, `temu.com` | je einmal. `temu.com` fehlt ganz, der Betreiber sitzt je nach Lesart in China, Irland oder den USA. |
| Keine Hauptadresse | `news.yahoo.co.jp` (Subdomain), `franceinfo.fr` (leitet auf `francetvinfo.fr`), `california.gov` (→ `ca.gov`), `threads.net` | Hauptadresse bzw. Endungsregel |
| Kein B2C-Shop nach dem Kriterium aus Österreich | `leboncoin.fr`, `willhaben.at`, `idealo.at`, `geizhals.at`, `ebay.*` | entfernt |
| Ungleich viele Einträge pro Zelle | Europa/Banken 4, Südostasien/Banken 1, Afrika nur Behörden | feste Regel mit 10 pro Zelle |
| Länderliste Russland | `gosuslugi.ru`, `ozon.ru` | nicht aufgenommen, liegt außerhalb der Regionen und ist aus der EU teils gesperrt |
| Afrika | nur 5 Behörden-Portale, ohne Rangquelle | nicht aufgenommen, siehe Limitationen |

Die Rangfolgen aus Similarweb und Semrush sind nicht frei abrufbar und stammen aus verschiedenen
Monaten. Sortiert wird deshalb nach Tranco, wie in Österreich.

### Messentscheidungen

| Entscheidung | Begründung |
|---|---|
| Rückfall-Resolver `1.1.1.1`, nur wenn der Resolver des Systems keine Adresse liefert | Der Provider-Resolver antwortete am 8.11.2026 bei `gst.gov.in` und `moe.gov.my` mit SERVFAIL, `1.1.1.1` löste beide auf. Ohne Rückfall wären das Messfehler des Heimnetzes. Wer geantwortet hat, steht in `hosts.csv` (`dns_resolver`). Für alle anderen Hosts ändert sich nichts gegenüber `full-01`. |
| Hosting-Regeln vor dem Scan ergänzt | Internationale CDNs wie Wangsu, Alibaba, Baishan, EdgeNext, CDN77, Sucuri, Automattic VIP und Netlify. Grundlage waren nur DNS und ASN der Liste, keine Scan-Ergebnisse. `full-01` und `pilot-01` ändern sich dadurch nicht (geprüft). |
| Österreichische Zufallsstichprobe wird mitgescannt | Gleicher Tag wie die übrigen Hosts, und der Abgleich mit `full-01` zeigt, wie stabil die Ergebnisse nach neun Tagen sind. |
| Gescannt wird aus Österreich | CDNs antworten vom nächsten Standort. Gemessen wird also, was ein Besucher aus Österreich bekommt. |

### Reproduzieren

```bash
python3 scan/run_scan.py --name international-01 --sites scan/sites_international.csv
```

```bash
.venv/bin/python analysis/analyze_international.py international-01
```

Der Scan dauerte 24 Minuten, vor allem wegen der Zeitüberschreitungen bei nicht erreichbaren
Hosts in Asien (rund eine Minute pro Host, zweimal). Er misst
keine Zeiten und darf laufen, während am Rechner gearbeitet wird. Heimnetz ohne VPN, wie bei
`full-01`.

### Vorab festgelegte Auswertung

- **Gültige Hosts** wie bisher: `ja` gegen alle `nein*`. `unklar`, `nicht_erreichbar` und
  `dns_fehler` fallen heraus und werden pro Region berichtet.
- **CDN/Cloud** heißt Hosting-Klasse Cloudflare, Akamai, AWS oder Andere CDN/Cloud.
- **H4 gilt**, wenn bei den Top-10-Hosts außerhalb Österreichs (a) der geschichtete
  Permutationstest für CDN/Cloud mit der Schicht Region × Branche p < 0,05 ergibt (10.000
  Permutationen, Seed 20261111) und (b) das gepoolte Mantel-Haenszel-Odds-Ratio größer als 1 ist.
  Die Schicht Region × Branche verhindert, dass ein Branchen- oder Regionseffekt als
  Hosting-Effekt erscheint, das Problem aus H3.
- **H5 gilt**, wenn bei den Top-10-Hosts außerhalb Österreichs mit Unterstützung und eindeutiger
  Präferenz (a) der einseitige exakte Fisher-Test „Akamai folgt häufiger dem Client als die
  übrigen“ p < 0,05 ergibt, (b) mehr als die Hälfte der Akamai-Hosts dem Client folgt und (c) mehr
  als die Hälfte der übrigen Hosts den Hybrid selbst wählt.
- **Explorativ, ohne Hypothese:** PQ-Anteile je Region mit Wilson-Intervall, Österreich mit den
  eigenen Top 10. Test der Region (Chi-Quadrat bzw. Fisher-Freeman-Halton) und geschichtete
  Permutation Region bei festem Hosting. Dazu die Plattformen und der Abgleich mit `full-01`.
- **Erwartete Trennschärfe:** Simuliert mit den Anteilen aus `full-01` und dem Hosting-Mix der
  Liste (nur DNS/ASN, 3.000 Durchgänge). H4 wird dann in praktisch allen Durchgängen bestätigt,
  auch wenn Akamai nur zu 60 % unterstützt und eigene Server halb so oft wie in Österreich. Ein
  Regionsunterschied wäre nur in rund 35 bis 55 % der Durchgänge nachweisbar, deshalb ist er keine
  Hypothese. Eine Hypothese „Server wählt meist selbst“ wurde verworfen: Rund ein Drittel der
  Liste liegt bei Akamai, das dem Client folgt.

### Limitationen der Erweiterung

- Top 10 statt Zufallsauswahl: Die Tests behandeln die Hosts wie eine Stichprobe, die Liste ist
  aber eine bewusste Auswahl der populärsten Websites.
- Tranco misst weltweite Popularität. Regionale Favoriten mit wenig internationalem Verkehr fehlen,
  globale Konzerne sind überrepräsentiert.
- Der Kandidatenpool für Nachrichten, Shops und Banken ist von Hand zusammengestellt. Was nicht im
  Pool steht, kann nicht gewählt werden. Behörden und Hochschulen folgen Endungsregeln, die nicht
  jedes Land gleich gut abdecken (deutsche Bundesbehörden nutzen oft `.de`).
- Tranco bewertet auch eingebettete Domains hoch, etwa `nist.gov` (Zeitdienst) oder `miit.gov.cn`
  (ICP-Registrierung im Fuß jeder chinesischen Website).
- Dieselben Konzerne tauchen in mehreren Regionen auf (`amazon.com`, `amazon.co.uk`,
  `amazon.co.jp`). Ihre Hosts sind nicht unabhängig.
- Einige Hosts in Asien antworteten am 8.11.2026 aus Österreich nicht (Zeitüberschreitung). Sie
  bleiben in der Liste und erscheinen als `nicht_erreichbar`.
- Afrika und Südamerika fehlen.

## Ergebnis des Scans `international-01`

**Nach dem Scan ergänzt.** Scan am 8.11.2026, 02:07 bis 02:31 Uhr, aus einem österreichischen
Heimnetz. Der vollständige Bericht steht in `data/processed/scan/international-01/report.md`.

### Überblick

**135 von 191 auswertbaren internationalen Top-10-Hosts (70,7 %, 95-%-Intervall 63,9 % bis 76,7 %)
unterstützen X25519MLKEM768.** 9 der 200 Hosts waren nicht auswertbar, alle in Asien und
Südostasien.

| Region (Top 10) | Anteil | 95-%-Intervall | CDN/Cloud |
|---|---:|---:|---:|
| Nordamerika | 42 von 50 (84 %) | 71 % bis 92 % | 47 von 50 |
| Europa | 38 von 50 (76 %) | 63 % bis 86 % | 37 von 50 |
| Südostasien | 30 von 45 (67 %) | 52 % bis 79 % | 31 von 45 |
| Asien | 25 von 46 (54 %) | 40 % bis 68 % | 35 von 46 |
| Österreich | 27 von 50 (54 %) | 40 % bis 67 % | 21 von 50 |

Zum Vergleich die österreichische Zufallsstichprobe am selben Tag: 67 von 121 (55 %). In
Österreich unterscheiden sich die meistbesuchten Websites also nicht von einer Zufallsauswahl.

| Branche (Top 10, alle Regionen) | Anteil |
|---|---:|
| Onlineshops | 41 von 48 (85 %) |
| Banken | 37 von 49 (76 %) |
| Nachrichten | 36 von 50 (72 %) |
| Behörden | 25 von 44 (57 %) |
| Hochschulen | 23 von 50 (46 %) |

### H4: bestätigt

| | Anteil | 95-%-Intervall |
|---|---:|---:|
| CDN/Cloud | 128 von 150 (85 %) | 79 % bis 90 % |
| Eigener/generischer Server | 7 von 41 (17 %) | 9 % bis 31 % |

| Bedingung | Ergebnis | Erfüllt |
|---|---|---|
| Geschichteter Permutationstest, Schicht Region × Branche | p < 0,001 | ja |
| Mantel-Haenszel-Odds-Ratio > 1 | 86,5 | ja |

In jeder Region liegt CDN/Cloud vorn (Abbildung `figures/international-01/scan_int_h4_hosting`).
Das Odds Ratio ist wegen vieler kleiner Schichten mit Nullzellen sehr unsicher, die Richtung ist
eindeutig, die Höhe nicht interpretierbar. Aussagekräftiger sind die Anteile oben.

Die 22 CDN-Hosts ohne Hybrid haben drei Ursachen:

- **Nur TLS 1.2 eingeschaltet (6):** `elpais.com` und `lemonde.fr` bei Fastly, `mit.edu` und
  `rakuten-bank.co.jp` bei Akamai, `stps.gob.mx` bei Microsoft, `xinhuanet.com` bei Baishan. Der
  Anbieter könnte den Hybrid, der Kunde hat TLS 1.3 nicht aktiviert.
- **TLS 1.3 ohne Hybrid (15):** vor allem chinesische Anbieter (Wangsu, Alibaba, Knownsec,
  EdgeNext) mit 10 Hosts, dazu Automattic VIP (`harvard.edu`, `nasa.gov`), Netlify
  (`stanford.edu`), `canada.ca` bei Akamai und `deped.gov.ph` bei Microsoft.
- **Abbruch (1):** `otto.de` bei AWS, siehe unten.

In Asien bringt „CDN“ deshalb weniger: 69 % gegen 87 bis 94 % in den anderen Regionen.

### H5: bestätigt, mit einer Einschränkung

| Anbieter | wählt den Hybrid selbst | folgt dem Client |
|---|---:|---:|
| Akamai | 0 | 63 |
| Fastly | 0 | 14 |
| Cloudflare | 18 | 0 |
| AWS | 16 | 0 |
| Imperva | 11 | 0 |
| Google, Microsoft, Sucuri | 6 | 0 |
| Eigener/generischer Server | 6 | 1 |

| Bedingung | Ergebnis | Erfüllt |
|---|---|---|
| Fisher einseitig, Akamai folgt häufiger dem Client | p < 0,001 | ja |
| Mehrheit der Akamai-Hosts folgt dem Client | 63 von 63 | ja |
| Mehrheit der übrigen wählt den Hybrid selbst | 57 von 72 (79 %) | ja |

**Einschränkung:** H5 nannte nur Akamai. Fastly verhält sich genauso, 14 von 14 Hosts folgen dem
Client. Das stand schon in `full-01`: Die 4 Hosts aus „Andere CDN/Cloud“, die dem Client folgten
(`wuestenrot.at`, `oe24.at`, `hornbach.at`, `myspreadshop.at`), liegen alle bei Fastly. Wir hatten
es beim Formulieren der Hypothese übersehen. Die korrekte Aussage lautet also: **Bei Akamai und
Fastly entscheidet der Client, bei allen anderen der Server.** Weil Browser den Hybrid zuerst
anbieten, bekommen Browser-Nutzer ihn trotzdem. Ein älterer Client, der X25519 zuerst nennt,
bekommt bei Akamai und Fastly dagegen klassisches TLS, obwohl der Server den Hybrid könnte. Das
betrifft 77 von 135 internationalen Hosts mit Unterstützung.

### Explorativ

- **Region:** Die Regionen unterscheiden sich (Chi-Quadrat p = 0,004, Cramérs V 0,25). Bei
  festgehaltenem Hosting verschwindet der Unterschied (geschichtete Permutation p = 0,227),
  Hosting bei fester Region bleibt (p < 0,001). Der Rückstand Asiens und Österreichs geht also auf
  den Hosting-Mix zurück, nicht auf die Region selbst. Belegt ist das nicht: Der Test war vorab nur
  als explorativ geplant, und Region und Hosting überlappen stark.
- **Wiederholung von `full-01`:** 121 von 122 Hosts haben nach neun Tagen dasselbe Ergebnis.
  `fh-salzburg.ac.at` hat den Hybrid inzwischen eingeschaltet. Die Messung ist damit sehr stabil.
- **Plattformen:** 7 von 8 unterstützen den Hybrid. Nur `wikipedia.org` nicht (TLS 1.3 ohne
  Hybrid). `facebook.com` und `yahoo.com` auf eigenen Servern wählen ihn selbst.
- **Großer ClientHello:** Die Kontrolle bietet wie ein Browser schon einen hybriden Key-Share an.
  Kein Host, der überhaupt antwortete, ist daran gescheitert. Die drei `nein_abbruch`-Hosts
  (`otto.de`, `ethz.ch`, `kku.ac.th`) akzeptieren diesen ClientHello und brechen nur ab, wenn
  ausschließlich der Hybrid angeboten wird, statt mit einem Alert zu antworten. Die 8 nicht
  erreichbaren Hosts scheitern schon beim TCP-Verbindungsaufbau (geprüft mit `nc` am 8.11.2026),
  `ccb.com` an fehlender sicherer Renegotiation.
- **Nur TLS 1.2:** 21 der 241 auswertbaren Top-10-Hosts, davon 8 in Asien.

### Ergänzende Limitationen nach dem Scan

- Die Klasse „Andere CDN/Cloud“ ist uneinheitlich: Imperva und Google wählen den Hybrid,
  Fastly folgt dem Client, chinesische CDNs bieten ihn nicht an.
- Die Hosting-Regeln für chinesische Anbieter beruhen auf CNAME-Mustern (`.365cyd.cn`,
  `.bsgslb.cn`), die nur für diese Liste geprüft wurden.

## Offen

- Optionale Gegenprobe mit Cloudflare Radar. Sie braucht einen API-Token des Teams und ist nicht
  umgesetzt.
