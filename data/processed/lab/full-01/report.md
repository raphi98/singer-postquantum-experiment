# Auswertung full-01

## Manipulationskontrolle

| Profil | RTT Soll | RTT Ping | Verlust Soll | Verlust real Client/Server |
|---|---:|---:|---:|---:|
| ideal | 0 ms | 0.16 ms | 0 % | 0.00% / 0.00% |
| europa | 20 ms | 21.00 ms | 0 % | 0.00% / 0.00% |
| uebersee | 150 ms | 149.84 ms | 0 % | 0.00% / 0.00% |
| kontrolle | 100 ms | 101.34 ms | 0 % | 0.00% / 0.00% |
| mobil | 100 ms | 99.73 ms | 2 % | 1.88% / 1.94% |
| extrem | 100 ms | 101.50 ms | 5 % | 4.84% / 4.65% |

## Handshake-Dauer

| Profil | Gruppe | n | Erfolg | Median | p95 | p99 | Mittelwert |
|---|---|---:|---:|---:|---:|---:|---:|
| ideal | X25519 | 1000 | 100.0% | 5.74 | 6.27 | 6.41 | 5.59 |
| ideal | X25519MLKEM768 | 1000 | 100.0% | 5.95 | 6.47 | 6.69 | 5.82 |
| europa | X25519 | 1000 | 100.0% | 26.03 | 29.31 | 31.04 | 26.19 |
| europa | X25519MLKEM768 | 1000 | 100.0% | 26.56 | 29.58 | 31.61 | 26.71 |
| uebersee | X25519 | 1000 | 100.0% | 168.07 | 172.97 | 173.95 | 167.77 |
| uebersee | X25519MLKEM768 | 1000 | 100.0% | 167.99 | 172.92 | 173.99 | 167.70 |
| kontrolle | X25519 | 1000 | 100.0% | 114.45 | 119.72 | 120.87 | 114.14 |
| kontrolle | X25519MLKEM768 | 1000 | 100.0% | 115.03 | 120.16 | 121.18 | 114.71 |
| mobil | X25519 | 1000 | 100.0% | 117.14 | 377.40 | 571.85 | 141.08 |
| mobil | X25519MLKEM768 | 1000 | 100.0% | 117.76 | 369.31 | 710.45 | 151.63 |
| extrem | X25519 | 1000 | 100.0% | 115.78 | 544.56 | 700.45 | 166.48 |
| extrem | X25519MLKEM768 | 1000 | 100.0% | 116.66 | 668.40 | 916.12 | 200.02 |

## Gruppenvergleich (hybrid minus X25519, 95-%-Intervall)

| Profil | Δ Median (ms) | Δ Mittelwert (ms) | Δ p95 (ms) | r_rb | p (Holm) |
|---|---:|---:|---:|---:|---:|
| ideal | +0.21 [+0.17; +0.28] | +0.22 [+0.17; +0.27] | +0.20 [+0.15; +0.26] | +0.28 | 0.000 |
| europa | +0.52 [+0.41; +0.68] | +0.53 [+0.37; +0.68] | +0.26 [-0.21; +0.90] | +0.21 | 0.000 |
| uebersee | -0.08 [-0.58; +0.36] | -0.06 [-0.39; +0.27] | -0.04 [-0.33; +0.31] | -0.01 | 0.655 |
| kontrolle | +0.58 [+0.13; +1.05] | +0.57 [+0.24; +0.88] | +0.45 [-0.04; +0.92] | +0.09 | 0.002 |
| mobil | +0.62 [-0.11; +1.33] | +10.55 [-2.22; +26.50] | -8.09 [-96.83; +118.54] | +0.04 | 0.220 |
| extrem | +0.87 [+0.41; +1.37] | +33.55 [+17.78; +49.39] | +123.84 [+21.38; +204.32] | +0.11 | 0.000 |

## H1: Liegt das Intervall von Δ Median ganz in ±1 ms?

- ideal: ja
- europa: ja
- uebersee: ja
- kontrolle: nein

## H2: Differenz der Differenzen gegenüber Kontrolle

| Profil | Kennzahl | Kontrast (ms) | 95-%-Intervall |
|---|---|---:|---:|
| mobil | Median | +0.04 | [-0.84; +0.90] |
| mobil | Mittelwert | +9.98 | [-2.73; +26.24] |
| mobil | p95 | -8.54 | [-96.04; +115.49] |
| extrem | Median | +0.29 | [-0.40; +0.95] |
| extrem | Mittelwert | +32.98 | [+17.44; +48.83] |
| extrem | p95 | +123.39 | [+21.19; +202.30] |

## Anteil verzögerter Handshakes

Verzögert heißt länger als 1.5 × Median von X25519 im selben Profil.

| Profil | X25519 | X25519MLKEM768 | p (Fisher) |
|---|---:|---:|---:|
| uebersee | 0.0% | 0.0% | 1.000 |
| kontrolle | 0.0% | 0.0% | 1.000 |
| mobil | 7.2% | 8.7% | 0.247 |
| extrem | 13.6% | 21.2% | 0.000 |
