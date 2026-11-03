# Auswertung pilot-03

**Pilot mit n = 20 je Zelle. Zahlen dienen nur der Funktionsprüfung.**

## Manipulationskontrolle

| Profil | RTT Soll | RTT Ping | Verlust Soll | Verlust real Client/Server |
|---|---:|---:|---:|---:|
| ideal | 0 ms | 0.14 ms | 0 % | 0.00% / 0.00% |
| europa | 20 ms | 20.56 ms | 0 % | 0.00% / 0.00% |
| uebersee | 150 ms | 149.90 ms | 0 % | 0.00% / 0.00% |
| kontrolle | 100 ms | 100.72 ms | 0 % | 0.00% / 0.00% |
| mobil | 100 ms | 99.81 ms | 2 % | 1.25% / 1.38% |
| extrem | 100 ms | 99.39 ms | 5 % | 5.11% / 5.19% |

## Handshake-Dauer

| Profil | Gruppe | n | Erfolg | Median | p95 | p99 | Mittelwert |
|---|---|---:|---:|---:|---:|---:|---:|
| ideal | X25519 | 20 | 100.0% | 5.27 | 6.18 | 6.19 | 5.16 |
| ideal | X25519MLKEM768 | 20 | 100.0% | 4.52 | 6.07 | 6.27 | 4.74 |
| europa | X25519 | 20 | 100.0% | 28.63 | 32.15 | 32.34 | 28.75 |
| europa | X25519MLKEM768 | 20 | 100.0% | 28.97 | 29.89 | 30.16 | 28.67 |
| uebersee | X25519 | 20 | 100.0% | 160.10 | 163.36 | 164.13 | 160.50 |
| uebersee | X25519MLKEM768 | 20 | 100.0% | 162.46 | 163.62 | 164.60 | 161.65 |
| kontrolle | X25519 | 20 | 100.0% | 110.81 | 114.41 | 115.61 | 111.09 |
| kontrolle | X25519MLKEM768 | 20 | 100.0% | 111.74 | 113.98 | 114.98 | 111.92 |
| mobil | X25519 | 20 | 100.0% | 111.36 | 114.33 | 114.86 | 111.20 |
| mobil | X25519MLKEM768 | 20 | 100.0% | 111.52 | 259.90 | 479.38 | 139.28 |
| extrem | X25519 | 20 | 100.0% | 112.39 | 547.53 | 800.12 | 209.01 |
| extrem | X25519MLKEM768 | 20 | 100.0% | 110.79 | 125.51 | 283.07 | 121.89 |

## Gruppenvergleich (hybrid minus X25519, 95-%-Intervall)

| Profil | Δ Median (ms) | Δ Mittelwert (ms) | Δ p95 (ms) | r_rb | p (Holm) |
|---|---:|---:|---:|---:|---:|
| ideal | -0.76 [-1.38; +0.45] | -0.42 [-0.96; +0.13] | -0.11 [-0.40; +0.22] | -0.27 | 0.591 |
| europa | +0.34 [-0.45; +0.98] | -0.08 [-0.98; +0.76] | -2.26 [-2.83; +0.55] | +0.08 | 0.655 |
| uebersee | +2.36 [-0.92; +3.00] | +1.14 [+0.02; +2.28] | +0.26 [-0.94; +2.94] | +0.33 | 0.459 |
| kontrolle | +0.93 [-0.38; +2.60] | +0.84 [-0.30; +1.95] | -0.43 [-2.58; +2.28] | +0.26 | 0.591 |
| mobil | +0.16 [-1.39; +2.39] | +28.08 [-0.33; +76.76] | +145.57 [-0.63; +420.76] | +0.21 | 0.591 |
| extrem | -1.60 [-3.15; +1.02] | -87.12 [-181.26; -10.34] | -422.01 [-749.12; -21.28] | -0.31 | 0.509 |

## H1: Liegt das Intervall von Δ Median ganz in ±1 ms?

- ideal: nein
- europa: ja
- uebersee: nein
- kontrolle: nein

## H2: Differenz der Differenzen gegenüber Kontrolle

| Profil | Kennzahl | Kontrast (ms) | 95-%-Intervall |
|---|---|---:|---:|
| mobil | Median | -0.78 | [-3.20; +1.63] |
| mobil | Mittelwert | +27.24 | [-1.34; +76.37] |
| mobil | p95 | +145.99 | [-1.23; +422.26] |
| extrem | Median | -2.53 | [-4.91; +0.31] |
| extrem | Mittelwert | -87.96 | [-183.65; -11.25] |
| extrem | p95 | -421.59 | [-749.55; -23.48] |

## Anteil verzögerter Handshakes

Verzögert heißt länger als 1.5 × Median von X25519 im selben Profil.

| Profil | X25519 | X25519MLKEM768 | p (Fisher) |
|---|---:|---:|---:|
| uebersee | 0.0% | 0.0% | 1.000 |
| kontrolle | 0.0% | 0.0% | 1.000 |
| mobil | 0.0% | 10.0% | 0.487 |
| extrem | 25.0% | 5.0% | 0.182 |
