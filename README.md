# Klassisches vs. Post-Quanten-TLS

Experiment für die LV „Wissenschaftliches Arbeiten“ (Master IT Architecture, FH JOANNEUM).
Präsentation am 11.11.2026.

## Ziel

| Teil | Forschungsfrage | Hypothesen |
|---|---|---|
| A, Labor | Wie stark erhöht die hybride Schlüsselvereinbarung X25519MLKEM768 Handshake-Dauer und Datenmenge gegenüber X25519, besonders bei schlechtem Netz? | **H1:** Unter guten Bedingungen ist der Zeitaufwand kaum messbar, nur die Datenmenge steigt. **H2:** Bei Paketverlust wächst der Nachteil, weil der Handshake mehr Pakete braucht. |
| B, Feldstudie | Wie verbreitet ist Post-Quanten-TLS auf österreichischen Websites, und hängt das eher von der Branche oder vom Hosting/CDN ab? | **H3:** Die Branche spielt wenig Rolle, der CDN-Anbieter eine große. |

## Repo-Struktur

| Ordner | Inhalt |
|---|---|
| `lab/` | Teil A: docker-compose, Configs, Zertifikate, Messskripte |
| `scan/` | Teil B: Scanner (noch offen) |
| `analysis/` | Auswertung, `requirements.txt` |
| `data/raw/lab/<messreihe>/` | Rohdaten, werden nie überschrieben |
| `data/processed/lab/<messreihe>/` | aufbereitete Tabellen und Bericht |
| `figures/<messreihe>/` | Diagramme als PNG und SVG |

Teil A liegt auf dem Branch `teil-a-labor`. Teil B bekommt einen eigenen Branch von `main`, die
beiden Teile berühren keine gemeinsamen Dateien außer diesem README.

## Teil A: Labor

### Aufbau

```
client (curl, OpenSSL)  <-- Docker-Bridge, MTU 1500 -->  server (nginx, OpenSSL)
172.30.0.20                                              172.30.0.10
netem auf eth0: RTT/2, Verlust p                         netem auf eth0: RTT/2, Verlust p
```

Pro Handshake läuft ein neuer curl-Prozess. Die Dauer ist `time_appconnect − time_connect`.
Der dritte Dienst `tools` (tshark) läuft nur bei der pcap-Auswertung, nie während einer Messung.

Netzprofile (`lab/profiles.csv`):

| Profil | RTT | Verlust je Richtung | Herkunft |
|---|---:|---:|---|
| Ideal | 0 ms | 0 % | Vorgabe |
| Europa | 20 ms | 0 % | Vorgabe |
| Übersee | 150 ms | 0 % | Vorgabe |
| Kontrolle | 100 ms | 0 % | **Ergänzung**, siehe Messentscheidungen |
| Mobil schlecht | 100 ms | 2 % | Vorgabe |
| Extrem | 100 ms | 5 % | Vorgabe |

### Versionen und Hardware

Geprüft am 30.10.2026, jede Messreihe hält die Stände zusätzlich in `manifest.json` fest.

| Komponente | Stand |
|---|---|
| Host | Apple M4 Pro (14 Kerne), 48 GB RAM, macOS 26.6.2 |
| Docker | Desktop, Client 29.7.2, Server 29.9.2, Compose 5.6.1 |
| VM-Kernel | 7.0.14-linuxkit, aarch64, 14 vCPUs, 7,7 GB RAM |
| Basis-Image | `debian:13-slim` (Debian 13.7) per Digest fixiert |
| Paketquelle | Debian-Snapshot 20261029T000000Z |
| OpenSSL | 3.5.7 (Debian 3.5.7-1~deb13u3), beide Container |
| curl | 8.14.1 gegen OpenSSL 3.5.7 |
| nginx | 1.26.3 |
| iproute2 | 6.15.0 |
| tshark | 4.4.19 |
| TCP | cubic, Initial-Window 10 Segmente, MSS 1448 Byte Nutzdaten |
| Python (Auswertung) | 3.14.7, Pakete in `analysis/requirements.txt` |

Das macOS-curl (LibreSSL) kann kein ML-KEM. Deshalb laufen curl, OpenSSL und tshark nur in
Containern, auf dem Host wird nichts systemweit installiert.

### Reproduzieren

Voraussetzungen: Docker und Python 3. Die Messskripte brauchen nur die Standardbibliothek und
laufen damit auch unter Windows.

Auswertungsumgebung einrichten:

```bash
python3 -m venv .venv
```

```bash
.venv/bin/pip install -r analysis/requirements.txt
```

Messung (Pilot: `--runs 20 --warmup 5`, Vollmessung samt pcaps knapp 2 Stunden):

```bash
python3 lab/run_experiment.py --name full-01 --runs 1000 --warmup 50
```

```bash
python3 lab/capture_pcaps.py --name full-01 --per-group 100
```

Auswertung:

```bash
.venv/bin/python analysis/extract_pcaps.py full-01
```

```bash
.venv/bin/python analysis/analyze_lab.py full-01
```

Während der Messung den Mac am Netzteil lassen und nichts Rechenintensives starten. Der
Ruhezustand wird automatisch verhindert. Die Skripte brechen ab, wenn MTU, Offloads oder
TCP-Einstellungen nicht passen, und überschreiben keine vorhandenen Rohdaten.

Die Testkette in `lab/certs/` liegt bewusst im Repo, damit Größen exakt gleich bleiben. Der
private Schlüssel ist nur für dieses Labor gedacht.

### Messentscheidungen

| Entscheidung | Begründung |
|---|---|
| RTT symmetrisch: je Richtung die halbe RTT auf `eth0` beider Container | netem wirkt nur auf ausgehende Pakete. Zweimal das volle Delay ergäbe die doppelte RTT. |
| Delay wird pro Profil per Ping kalibriert (`netem_delay_ms` in `checks.csv`) | In der VM wachen die netem-Timer rund 1,2 ms pro Richtung zu spät auf. Unkalibriert lag Europa 13 % über dem Soll. |
| Verlust gilt pro Paket in jeder Richtung | Das entspricht einer echten Strecke. Ein Ping-Umlauf verliert darum rund 3,96 % bzw. 9,75 %. |
| Kontrollprofil 100 ms / 0 % ergänzt | Alle Verlustprofile haben 100 ms RTT. Ohne Kontrolle wären RTT- und Verlusteffekt in „Mehraufwand vs. Verlust“ vermischt. |
| MTU 1500 fest im Compose-File | Docker Desktop setzt 65535. Ein ClientHello zerfiele nie in zwei Pakete, und der Mechanismus aus H2 könnte gar nicht auftreten. |
| TSO, GSO und GRO aus | Sonst verwirft netem Sammelpakete als Ganzes, und tcpdump zeigt Pakete, die es so nie gäbe. |
| `tcp_no_metrics_save=1` | Linux merkt sich sonst RTT und ssthresh pro Ziel, die Läufe wären nicht unabhängig. |
| Feste ARP-Einträge | ARP liefe sonst selbst durch netem und könnte einzelne Läufe verzögern. |
| Kein `--tlsv1.3` am Client, TLS 1.3 erzwingt der Server | Mit `--tlsv1.3` fallen TLS-1.2-Cipher und Extensions weg. Der hybride ClientHello passte dann mit 12 Byte Luft in ein Paket, echte Clients brauchen zwei. |
| 200 ms Pause vor jedem Handshake | Ohne Pause läuft das Ideal-Profil auf heißer CPU (2,6 ms), mit 50–1000 ms Pause sind es rund 5,8 ms (`data/raw/lab/aux-idle-*`). Sonst wäre das Profil nicht mit den anderen vergleichbar. |
| Zertifikatskette nach dem Vorbild von letsencrypt.org | Am 30.10.2026 gemessen: 4 Zertifikate, 3576 Byte, Leaf ECDSA P-256. Die Kette (3556 Byte) bestimmt die Paketzahl des Server-Flights. |
| Neuer curl-Prozess, `--no-sessionid`, Server ohne Cache und Tickets | Jeder Handshake ist vollständig. Kontrolle über `$ssl_session_reused` im Serverlog. |
| Gruppe wird im Serverlog gegengeprüft (`$ssl_curve`) | Die Kontrolle kommt nicht aus demselben Werkzeug wie die Messung. `0x11ec` ist der IANA-Code von X25519MLKEM768. Die Auswertung bricht bei Abweichungen ab. |
| `--cacert` mit nur einer Wurzel, `--resolve` statt DNS | Der System-CA-Store und DNS lägen sonst im oder nahe am Messpfad. |
| Handshakes strikt seriell | Parallele Läufe würden sich CPU und Warteschlangen teilen. |
| Gruppen balanciert zufällig verschachtelt, Profilreihenfolge zufällig, Seed 20261111 | Drift durch Wärme oder Hintergrundlast trifft beide Gruppen gleich. Die Reihenfolge ist wiederholbar. |
| Aufwärmläufe bleiben in der CSV (`phase=warmup`) | Sie werden erst in der Auswertung verworfen, der Ausschluss bleibt nachvollziehbar. |
| pcaps in eigenen Läufen | tcpdump kostet CPU und soll die Zeitmessung nicht beeinflussen. |
| Vollmessung nur am Netzteil, Stromquelle pro Block in `checks.csv` | Akkubetrieb ändert das Energieprofil der CPU, und ein Wechsel mitten im Lauf träfe die Profile ungleich. Das Skript verweigert den Start auf Akku. |

### Vorab festgelegte Auswertung

Diese Regeln stehen vor der Vollmessung fest, damit sie nicht an die Ergebnisse angepasst werden.

- **Kennzahlen:** Median, p95, p99 und Mittelwert pro Profil und Gruppe.
- **Test:** Mann-Whitney-U, zweiseitig, Holm-Korrektur über alle Profile. Effektstärke ist die
  rangbiseriale Korrelation (identisch mit Cliffs Delta). Dazu Differenzen mit 95-%-Bootstrap-Intervall.
- **H1 gilt** für die verlustfreien Profile, wenn das 95-%-Intervall von Δ Median ganz in ±1 ms
  liegt. Die Grenze liegt im Bereich des Timer-Jitters der VM und weit unter jeder Wahrnehmung.
  Ein signifikanter p-Wert widerlegt H1 nicht: Bei n = 1000 und schmaler Verteilung wird auch
  ein praktisch bedeutungsloser Unterschied signifikant, und die Rang-Effektstärke kann groß sein.
- **H2 gilt**, wenn der Mehraufwand im Mittelwert oder der Anteil verzögerter Handshakes bei
  Verlust stärker ausfällt als in der Kontrolle (Differenz der Differenzen, Intervall ohne 0).
  Der Median allein taugt hier nicht: Die meisten Handshakes verlieren nichts, der Effekt liegt
  im Tail. Verzögert heißt länger als 1,5 × Median von X25519 im selben Profil.
- **Erwartete Trennschärfe bei n = 1000:** Trifft jeder Paketverlust den Handshake, sind 7,8 %
  gegen 11,4 % der Handshakes bei 2 % Verlust betroffen (4 gegen 6 Pakete) und 18,5 % gegen
  26,5 % bei 5 %. Das ergibt rund 78 % Power bei 2 % und rund 99 % bei 5 % Verlust (α = 0,05,
  zweiseitig). Ein Null-Ergebnis bei 2 % ist also weniger aussagekräftig als eines bei 5 %.

### Störfaktoren und Limitationen

Laufende Liste, wird bei jeder Messreihe ergänzt.

**Testumgebung**

- Beide Container laufen in einer VM auf demselben Host. Es gibt keine echte Leitung, kein
  Bandbreitenlimit und keine Warteschlangen im Netz.
- **Kalte CPU:** Nach einer Wartezeit dauert die Verarbeitung länger. Bei 100 ms RTT liegt der
  Handshake rund 12 ms über der RTT. Die pcaps zeigen, dass das CPU-Zeit ist (Server rund 4,5 ms
  statt 0,5 ms, Client rund 5,5 ms statt 2,6 ms), der Server-Flight kommt in unter 0,1 ms an
  einem Stück an. Das trifft beide Gruppen gleich, die absoluten Dauern sind aber zu hoch.
- netem-Timer haben auch nach der Kalibrierung rund 1–2 ms Streuung (Ping-mdev).
- Hintergrundlast auf dem Mac lässt sich nicht ganz ausschließen. Die zufällige Verschachtelung
  verteilt sie auf beide Gruppen.
- Die Ergebnisse gelten für ARM64 und diese OpenSSL-Version. Andere CPUs liefern andere
  Millisekunden, vor allem für den Rechenanteil.

**Netzmodell**

- Verlust ist unabhängig pro Paket. Echter Verlust kommt oft in Bursts.
- Kein Jitter und kein Reordering, wie in der Aufgabenstellung vorgegeben.
- Verlust entsteht lokal im Sender-Container. Die TCP-Zähler in `checks.csv` belegen, dass TCP
  ihn trotzdem per Timer erkennt (Timeouts, Loss Probes), und die Dauern zeigen die passenden
  Stufen.
- Nur IPv4. Bei IPv6 sinkt die MSS um 20 Byte.

**Messgröße**

- `time_appconnect − time_connect` enthält neben dem Protokoll auch curls TLS-Setup und die
  Zertifikatsprüfung, und es endet, bevor das Client-Finished beim Server ist.
- Verlust im TCP-Verbindungsaufbau zählt nicht zur Dauer, dieser Teil trifft beide Gruppen gleich.
- Am Client-Interface sind selbst verworfene Pakete unsichtbar, weil tcpdump nach netem mitliest.
  Paketzahlen sind deshalb nur in verlustfreien Profilen exakt.

**Übertragbarkeit**

- curl ist kein Browser. Der ClientHello liegt mit 1504 Byte nur 56 Byte über der MSS, die
  Paketzahl ist also robust gegen längere Hostnamen, aber nicht gegen kürzere Extensions-Listen.
- Der X25519-ClientHello wird von OpenSSL auf 512 Byte aufgefüllt. Der Zuwachs von 992 Byte ist
  darum kleiner als der reine Zuwachs des Key-Share.
- Die Paketzahl des Server-Flights hängt an der Zertifikatskette. Größere Ketten verschieben
  absolute Werte, der Zuwachs um ein Paket bleibt ähnlich.
- Nur TCP mit cubic. HTTP/3 (QUIC) ist nicht untersucht.
- Nur ein Server ohne Last. Der Rechenaufwand unter hoher Serverlast ist nicht Teil der Messung.

### Verlauf der Pilotläufe

| Messreihe | Zweck | Status |
|---|---|---|
| `pilot-01` | erster Lauf | ungültig: RTT 2,5 ms zu hoch, Ping-Kontrolle fehlerhaft |
| `aux-idle-pause*` | Einfluss der Pause im Ideal-Profil | Grundlage der 200-ms-Entscheidung |
| `pilot-02` | mit Kalibrierung, Pause, Kontrolle, pcaps | ungültig: hybrider ClientHello nur ein Paket |
| `aux-clienthello` | ClientHello ohne `--tlsv1.3` | zeigt 2 Pakete |
| `pilot-03` | aktueller Aufbau | gültiger Pilot, n = 20 je Zelle. Dient nur der Funktionsprüfung. In `extrem` zeigt er X25519 mit 25 % gegen 5 % verzögerten Handshakes im Nachteil, das ist Zufall bei n = 20 (Fisher p = 0,18). |

## Teil B: Feldstudie

Noch nicht begonnen.
