# Studio dell'asta 2026/27 — lega *porcodidiosanto*

**28/09/2026**, dopo 5 giornate di Serie A. Dati: le 10 rose con prezzo pagato (Costo), valore di
mercato oggi (FVMp, riportato sulla scala dei crediti: 1 FVMp = 0,914 crediti) e MV/FM di stagione.
Rifattibile con `python studio_asta.py --tabella <file>`.

## La domanda

La strategia usata all'asta — niente rilanci sui super top, tanti giocatori medi a prezzo
"giusto" — ha prodotto una squadra mediocre? E cosa conviene fare la prossima volta?

## Risposta breve

**Sì, e i dati spiegano perché.** In questa lega la fascia di prezzo dove sono finiti i crediti
di AL DOMORO (31-60) è la peggiore di tutte: costa quanto i top, rende quanto i giocatori da 5
crediti. Ma la correzione non è "compra i super top" e basta: è **dove NON spendere**.

## I numeri

| fascia (crediti) | giocatori | speso | vale oggi | resa | FM di chi gioca | crediti per trovare un FM ≥ 7 |
|---|---|---|---|---|---|---|
| 0-2 | 62 | 74 | 449 | 6,07* | 6,08 | **12** |
| 3-9 | 62 | 347 | 640 | 1,85 | 6,25 | **32** |
| 10-24 | 57 | 908 | 811 | 0,89 | 6,20 | 83 |
| **25-49** | 45 | **1.546** | 1.171 | **0,76** | **6,27** | **155** |
| 50-89 | 15 | 949 | 797 | 0,84 | 6,83 | 119 |
| 90+ | 9 | 1.113 | 1.068 | 0,96 | **7,95** | 159 |

\* gonfiata: il FVMp minimo di un rincalzo è ~5, quindi un giocatore da 1 credito "guadagna" quasi sempre.

Tre cose, in ordine di solidità:

1. **La fascia 25-49 è denaro perso.** Un terzo del budget della lega (1.546 crediti) è finito lì;
   la fantamedia di chi gioca (6,27) è **uguale a quella dei giocatori da 3-9 crediti** (6,25);
   ogni giocatore da FM ≥ 7 trovato lì è costato 155 crediti, quanto un top.
2. **I top rendono davvero di più per slot.** Oltre i 90 crediti la FM è 7,95: +1,7 punti a
   partita rispetto alla fascia media, su uno slot che giochi sempre. In 33 giornate sono ~55 punti,
   ~9 gol di fasce. E tengono il valore (0,96) meglio di qualunque fascia sopra i 10 crediti.
3. **I portieri non si pagano.** 7 portieri da 30+ crediti: 351 crediti per una FM di 5,10.
   I portieri da ≤5 crediti che giocano fanno 4,74. **+0,36 a partita per 337 crediti.**
   Quattro dei cinque portieri più cari hanno perso fra 22 e 29 crediti di valore.

## Come hanno speso le squadre

| squadra | forza (socio) | top1 | primi 3 | fascia 31-60 | fascia 0-5 |
|---|---|---|---|---|---|
| Sbirrodemerda FC | **75,8** | Malen 182 | 55% | 213 cr / 5 g | 17 cr / **13 g** |
| AQ Alessia quondam | **73,6** | Ramos 129 | 53% | 51 cr / 1 g | 12 cr / 8 g |
| **AL DOMORO** | 69,7 | 51 | **30%** (il più basso) | **313 cr / 7 g** | 22 cr / 8 g |
| Scasserra FC | 65,1 (ultima) | Hojlund 140 | 57% | 50 cr / 1 g | 18 cr / 11 g |

- Le prime due hanno **un fuoriclasse vero + tanti biglietti della lotteria da 1-3 crediti**
  che sono usciti (Raimondo, Kvernadze, Zeballos, Varela, Adzic, Moreira).
- **Concentrare la spesa non basta:** la correlazione fra quota dei primi 3 e forza è +0,06.
  Scasserra (57%) è ultima: Hojlund 140 → vale 110, e gli altri top flop della lega sono tutti
  sopra i 100 (Kolo Muani −49, Douvikas −45). Il fuoriclasse è un rischio: va scelto bene.
- AL DOMORO non è mediocre in assoluto (3ª-4ª per forza stimata), ma è **senza tetto**: nessun
  giocatore da FM ≥ 8,5, e 313 crediti in 7 giocatori della fascia peggiore, di cui due persi
  quasi per intero (Martinez Jo. 51 → 29, Santos A. 45 → 17).

## Contraddico una cosa sola

"Prendere i super top" letto come *rilanciare su chiunque sia quotato alto* sarebbe sbagliato:
metà dei giocatori sopra i 100 crediti ha perso 17-49 crediti di valore. La regola che esce dai
dati è più stretta:

## La strategia per la prossima asta (e per il mercato di riparazione)

1. **1-2 fuoriclasse in attacco**, solo fra quelli con storico da top (FM ≥ 8 per più stagioni,
   rigorista o centravanti titolare di una squadra da 1,8+ gol attesi). È lì che la fascia 90+
   rende: 7,95 di FM.
2. **Zero crediti nella fascia 25-49**, salvo eccezioni motivate uno per uno. È il buco da
   1.546 crediti della lega.
3. **Portieri: coppia da ≤ 10 crediti totali** di una squadra da difesa solida, con alternanza di
   calendario (`python socio.py portieri`). Il modificatore difesa si prende coi difensori, non
   col portiere caro.
4. **12-14 slot a 1-5 crediti su titolari probabili** di neopromosse e squadre medie, soprattutto
   attaccanti e centrocampisti offensivi: è la fascia dove un FM ≥ 7 costa 12-32 crediti invece di 155.
   Con il **rendimento** attivo servono comunque 11 che prendono voto: la lotteria va giocata sui
   titolari, non sulle riserve (Spence e Mazzocchi, 28 crediti, 0 presenze).
5. **Difesa a 3-9 crediti**, titolari sicuri: la FM dei difensori non dipende quasi dal prezzo.

## Limiti, dichiarati

- 5 giornate: la FM di fascia è rumorosa, le differenze sotto 0,3 non significano niente.
- Il FVMp è consenso di mercato, non punti fatti.
- 10 squadre: le correlazioni fra strategia e forza sono aneddoti, non leggi.
- La letteratura americana (fantasy football, dove si schierano ~9 su 16) va nella stessa
  direzione: gli "stars and scrubs" vincono più spesso dei rosters equilibrati
  ([studio su 40.000 simulazioni](https://statholesports.substack.com/p/punt-the-bench-40000-fantasy-football),
  [FantasyPros](https://www.fantasypros.com/2019/06/stars-and-scrubs-or-balanced-auction-roster-how-to-decide-fantasy-football/)).
  Nel fantacalcio si schierano 11 su 25 ma con 5 cambi e il rendimento: la panchina conta di più,
  per questo la parte "scrubs" va fatta con titolari, non con nomi.

Da rifare a fine girone d'andata con i Pv veri di tutte le rose: se la fascia 25-49 resta sotto
le altre anche a 19 giornate, diventa una regola del tool d'asta (`fanta.py`), non un consiglio.
