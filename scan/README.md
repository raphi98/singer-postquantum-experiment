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

## Offen

- Optionale Gegenprobe mit Cloudflare Radar. Sie braucht einen API-Token des Teams und ist nicht
  umgesetzt.
