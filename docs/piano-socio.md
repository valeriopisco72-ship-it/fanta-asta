# Piano: da tool d'asta a socio di stagione

**28/09/2026** · sosta per le nazionali, 5 giornate giocate. Metodo: Superpowers (obra) —
brainstorming → piano scritto → test prima del codice → verifica prima di dire "fatto".

## Il problema

`fanta.py` fa bene una cosa sola: i prezzi limite all'asta. Ma l'asta è una sera; il
campionato sono 38 giornate, e si vince (o si perde) lì:

| decisione | quante volte | chi la prende oggi |
|---|---|---|
| prezzi all'asta | 1 | `fanta.py` ✅ |
| **chi schierare** (modulo, XI, ordine panchina) | 38 | nessuno |
| **quale portiere** fra i due/tre in rosa | 38 | nessuno |
| **scambi** proposti e ricevuti | ~10 | nessuno |
| **svincolati / mercato di riparazione** | 2-3 finestre | nessuno |
| **rischiare o no** contro l'avversario della settimana | 38 | nessuno |

## L'idea che tiene insieme tutto

**Un giocatore vale quello che cambia nella TUA formazione, non in astratto.**
È il VORP dell'asta portato in stagione: un quarto portiere forte vale ~0 se non lo
schieri mai; un difensore medio vale molto se il tuo terzo titolare è peggio.

Ogni modulo nuovo risponde con lo stesso metro: **fantapunti attesi della tua
formazione migliore**, giornata per giornata, con la panchina che entra davvero.

## Moduli

| file | cosa fa | dati (tutti opzionali salvo la rosa) |
|---|---|---|
| `regole.py` | fantavoto, fasce gol, modificatore difesa, moduli, cartellini — tutto configurabile da `lega.json` | — |
| `voti.py` | legge i voti di giornata (formato fantacalcio.it) e costruisce l'archivio della stagione | `voti/*.csv|xlsx` |
| `proiezioni.py` | stima per giocatore: media e dispersione del fantavoto, probabilità di giocare | voti, listone, `titolari.csv` |
| `calendario.py` | difficoltà delle prossime giornate, forza delle squadre, griglia portieri | `calendario.csv`, `squadre_2025-26.csv` |
| `schiera.py` | formazione ottima + panchina; negli scontri diretti **P(vittoria)** e scelta del rischio | rosa, avversario |
| `mercato.py` | scambi e svincolati misurati sul valore marginale della tua formazione | `rose.csv` |
| `socio.py` | il briefing del giovedì: tutto quello sopra in una pagina | `lega.json` |

## Scelte (e perché)

1. **Probabilità di giocare, non sì/no.** Chi è nell'XI probabile gioca ~9 volte su 10,
   chi non c'è ~1,5 su 10 [STIMA dichiarata in `proiezioni.py`]. Con le probabilità la
   panchina smette di essere un dettaglio: il suo valore si calcola esattamente
   (Poisson-binomiale: "primi k del ruolo che scendono in campo").
2. **Shrinkage bayesiano sulla stagione in corso.** Cinque giornate sono poche: 3 partite
   a 9 di fantavoto non battono 30 partite a 7,5. Il peso del passato (listone) e del
   presente (voti) è dichiarato e testato.
3. **Negli scontri diretti non si massimizza la media.** Da favorito la varianza è il
   nemico; da sfavorito è l'unica speranza (letteratura fantasy americana, v. fonti).
   Si simulano le partite (Monte Carlo, numeri casuali comuni) con le fasce gol vere
   della lega e si sceglie la formazione che massimizza **punti in classifica attesi**
   (3·V + 1·N), non fantapunti.
4. **Uno scambio si misura sulla formazione, non sulla somma dei valori.** `mercato.py`
   stampa entrambi, apposta: la differenza è l'errore che fanno tutti.
5. **Regole di casa invariate:** se il dato manca lo dice; ogni stima ha scritto
   [STIMA] accanto; ogni test ha la sua controprova.

## Cosa NON fa (dichiarato)

- Non sa degli infortuni oltre a ciò che le probabili formazioni incorporano.
- La distribuzione del fantavoto è approssimata come normale: sbaglia le code (i bonus
  sono salti, non rumore). Serve a confrontare formazioni, non a prevedere 11 fantavoti.
- La forza delle squadre a inizio stagione è poco più del fattore campo: si affina con
  i risultati (colonne GolCasa/GolTrasferta del calendario).

## Verifica

`python tests/qa_socio.py` — invarianti con controprova, sullo stile di `qa_fanta.py`.
`python esempio.py --stagione` genera una lega finta completa per provare `socio.py`.

## Esito (28/09/2026)

Fatto tutto il piano, test-first: 114 test con controprova in `tests/qa_socio.py`.
I test hanno trovato quattro difetti veri prima che arrivassero a un utente:

1. fasce gol a tabella che si fermavano all'ultima soglia (120 punti = 6 gol);
2. una sola doppietta pesava più di dieci partite da 7,5 → taglio delle code del fantavoto;
3. il taglio stesso diventava una ghigliottina coi dati troppo regolari → mai più stretto del ruolo;
4. la squalifica azzerava il giocatore per tutte le giornate future (e il mercato suggeriva di tagliarlo).

Misura su dati finti (6 stagioni × 10 rose × 18 giornate, walk-forward): formazione del
socio **+2,2 ± 0,24 fantapunti/giornata** contro la formazione ingenua; errore per giocatore
0,98 contro 1,10 della fantamedia finora, pari al listone. Il primo backtest su una rosa
sola dava **−7 punti in 12 giornate**: era rumore, ma l'ho scoperto solo allargando il
campione — ed è il motivo per cui `socio.py verifica` stampa quante giornate ha visto.

Prossimi passi, in ordine di resa:
- misurare P_XI / P_FUORI con le probabili vere contro i voti veri;
- rigoristi (bonus attesi molto diversi a parità di fantamedia);
- correlazione fra compagni di squadra nella simulazione (oggi indipendenti).
