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

## Prezzo di mercato della lega (`python socio.py asta --mercato`)

Modello per ruolo × fascia di FVM, scelto dall'errore **leave-one-out** (il prezzo di ogni
giocatore previsto senza usare il suo acquisto), su 250 acquisti e 342 non comprati del listone
del 04/09. Baseline di lega: 1 punto FVM = 0,433 crediti.

| cella | modello | errore medio | baseline |
|---|---|---|---|
| A 20-49 | logaritmico | **4,0** | 8,8 |
| C 20-49 | logaritmico | **5,2** | 6,8 |
| D 20-49 | lineare | **5,3** | 7,3 |
| P 50-99 | lineare | **3,9** | 25,2 |
| A 100+ | baseline | 20,4 | 20,4 |
| C 100+ | lineare | 18,7 | 19,2 |

Sotto FVM 50 il modello dimezza l'errore; sui top nessun modello batte la retta semplice, e
si usa quella: **sui top la tua lega è imprevedibile di ±20 crediti**, ed è lì che il tetto
(piano d'asta) conta più della previsione.

**Le manie** (pagato rispetto alla baseline, mediana):

| strapaga | | regala | |
|---|---|---|---|
| portieri | **+46%** | attaccanti | **−39%** |
| difensori | +25% | centrocampisti | −34% |
| Como | **+57%** | Frosinone | **−84%** |
| Inter | +38% | Monza | **−81%** |
| Udinese | +31% | Venezia | −68% |
| Roma | +26% | Parma, Cagliari | −67% |
| Milan | +18% | Sassuolo | −63% |

La lega paga il **nome** della squadra, non il giocatore: Como e Inter si pagano quasi il doppio di
Monza e Frosinone a parità di FVM. È esattamente il posto da cui sono usciti i gioielli di
quest'anno (Varela, Zeballos, Raimondo, Kvernadze, Adzic): **il mercato li ha svenduti perché
erano di squadre senza nome**. Per lo scouting (piano C) significa che l'imbuto deve partire da lì.

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

## Rigioco

`python socio.py asta --rigioca` (28/09/2026) rigioca l'asta del 05/09 reparto per reparto:
il piano, costruito **solo con dati di agosto** (listone, prezzi previsti dal modello della
lega), va sul suo bersaglio più caro. Se nessuno lo aveva comprato lo prende a 1; se il suo
tetto arriva a pagato + 1 lo prende a pagato + 1; altrimenti lo perde e rifà il piano.
**È ottimista per costruzione**, due volte: quando rilanci, gli altri non reagiscono; e le
forchette dei prezzi con cui sceglie i bersagli sono tarate sui prezzi di questa stessa asta,
che ad agosto non si conoscevano (sono i dati veri della lega, ma a posteriori).

La rosa del rigioco: Di Gregorio, Milinkovic-Savic V., Provedel · Dimarco (71), Ostigard,
Pavlovic, Kabasele, Gallo, Terracciano F., Drobnic, Puczka · Paz N. (94), McTominay (51),
Modric, Mandragora, Thuram K., Konè I., Keita M., Mkhitaryan · Thuram (107), Davis K. (63),
Yildiz, Esposito Se., Vitinha O., Buksa. 500 crediti, 5 giocatori sopra i 50, 11 presi a 1
credito fra quelli che nessuno ha comprato.

| rosa | valore col modello di agosto | forza oggi (socio) | FM di chi gioca | FVMp oggi (crediti) |
|---|---|---|---|---|
| **piano (rigioco)** | **72,1** (1ª) | n.d. (14 noti su 25) | 6,46 sui 14 noti | **579 sui 14 noti** |
| Sbirrodemerda FC | 63,6 (9ª) | **74,2** | 6,56 | 595 |
| AQ Alessia quondam | 65,3 (7ª) | 73,4 | **6,80** | 552 |
| **AL DOMORO (vera)** | 62,4 (**10ª**) | 69,6 (3ª) | 6,08 | 459 |
| ziopera | 68,5 (2ª) | 65,7 (9ª) | 6,30 | 558 |
| Scasserra FC | 67,3 (3ª) | 64,2 (10ª) | 6,09 | 453 |

(le altre 5 rose fra 66,6 e 69,4 di forza oggi.)

### Il verdetto, in tre righe

1. **Il piano spende meglio.** A prezzi veri (anzi pagato + 1), i 14 giocatori del piano che
   qualcuno aveva davvero comprato valgono oggi **579 crediti**: più di 9 rose intere su 10, e
   120 più di tutta AL DOMORO (459) con 11 slot ancora da contare. La loro FM (6,46) è sopra
   quella di AL DOMORO (6,08). I top che prende sono quelli giusti (Thuram, Paz, Dimarco).
2. **Ma il valore che ottimizza è sbagliato, e questo è il punto.** Il modello di agosto mette
   le 10 rose vere in un ordine **opposto** a quello di oggi: correlazione di rango **−0,53**.
   Sbirrodemerda e AQ, prime oggi, erano 9ª e 7ª per il modello; ziopera e Scasserra, prime per
   il modello, sono 9ª e 10ª. Il piano "vince" sul modello per costruzione: il test vero è la
   classifica, e lì il modello di agosto non ha predetto niente.
3. **Gli 11 giocatori da 1 credito sono la scommessa non verificabile.** Nessuno li ha comprati
   e la tabella dell'app di oggi ha solo i giocatori in rosa: la loro stagione non si conosce
   da qui. La forza di oggi della rosa del piano quindi **non si può calcolare**, e non la
   stimo.

**Cosa ne segue.** Il motore dei prezzi (forchetta, tetto, somma zero) fa quello che deve: dato
un valore, spende bene. Il limite è il **valore dei giocatori ad agosto**, che è fatto di
stagione scorsa e quotazioni: le rose migliori di oggi le hanno fatte i biglietti da 1-3
crediti che sono usciti (§ Come hanno speso), cioè esattamente quello che il modello non vede.
È il motivo per cui il piano C (scouting con fonti) viene dopo questo: i tetti diventano utili
solo quando il valore di chi costa poco è stimato meglio. Fino ad allora usa il piano per la
**struttura** (dove non spendere, i portieri a 1-2 crediti, 1-2 top veri) e per i **tetti dei
top**, e non fidarti del suo giudizio sui giocatori da 1 credito.

Limiti: 5 giornate, 10 rose (la correlazione ha un intervallo largo); rigioco ottimista; FVMp
è consenso di mercato. Da rifare a giornata 19 con le schede di scouting in `scouting/`.
