# Piano d'asta: prezzo di mercato, tetto e costruzione della rosa — design

**Data:** 28/09/2026 · **Stato:** design approvato in chat (sezioni 1-4), spec in revisione
**Metodo:** Superpowers (obra) — brainstorming, percorso *architetturale*
**Collegata a:** `2026-09-28-scouting-qualitativo-design.md` (lo scouting corregge il valore; questa spec lo usa)

## 1. Perché

La strategia usata all'asta del 05/09 — niente rilanci sui top, tanti giocatori medi a prezzo
"giusto" — ha prodotto una rosa senza tetto: 313 crediti su 7 giocatori della fascia che in
questa lega rende peggio (`docs/studio-asta-2026-27.md`). `fanta.py` dava prezzi limite a somma
zero sulla lega, ma non costruiva la **tua** rosa e non sapeva **quanto paga davvero la tua lega**.

Obiettivo: per ogni giocatore due numeri, e un piano.

- **Prezzo di mercato previsto** (forchetta): quanto lo pagherà la lega.
- **Tetto**: il massimo che conviene a te, oltre il quale la rosa migliore la fai senza di lui.
- **Piano d'asta** reparto per reparto, con bersagli, alternative e budget, ricalcolato live.

**Successo:** rigiocando l'asta del 05/09 coi soli dati di agosto (§ 7), la rosa del piano batte
la rosa vera di AL DOMORO sui tre metri del § 7. Se non la batte, il lavoro non è finito.

## 2. Dati

| dato | file | note |
|---|---|---|
| prezzi pagati il 05/09 + FVM al momento dell'asta | `prezzi_lega_2026-27.csv` (FantaSquadra;Nome;Ruolo;Pagato;FVM) | 250 acquisti, fuori dal repo (FVM è di Fantacalcio.it) |
| listone di agosto (quotazione, FVM, stagione scorsa) | `listone_completo.csv` | sul PC dell'utente; serve per i **non comprati** e per il valore |
| rose attuali, stime, scouting | come oggi | `socio.py` |

Senza il listone: il modello di prezzo gira sui soli 250 comprati (senza probabilità di acquisto) e
il piano lo dichiara in testa.

## 3. Prezzo di mercato previsto (`mercato_asta.py`)

- **Per reparto**, perché la lega ha manie fortissime e diverse per reparto (mediana pagato/FVM
  riportato a scala lineare, asta del 05/09): **P +46%, D +25%, C −34%, A −39%**.
  Ipotesi dichiarata: è l'effetto dell'ordine di chiamata P → D → C → A (si strapaga all'inizio,
  si compra a sconto quando i budget sono finiti). Non è misurabile finché l'ordine non si registra.
- **Modello a tratti scelto dalla validazione.** Per ogni reparto e ogni fascia di FVM
  (< 20, 20-49, 50-99, ≥ 100) si confrontano, in leave-one-out, due candidati:
  lineare `pagato = k · FVM` e logaritmico `log pagato = a + b · log FVM`; in ogni cella si usa
  quello con errore medio minore. Esplorazione del 28/09: il logaritmico vince sotto FVM 50
  (3,3 vs 3,9 e 5,8 vs 7,3 crediti di errore), perde nettamente sopra (50,4 vs 20,5 oltre FVM 100).
- **Forchetta 25%-50%-75%** dai residui leave-one-out della cella (in scala moltiplicativa).
- **Probabilità di essere comprato** (solo col listone): frequenza di acquisto per reparto e
  fascia di FVM. Un giocatore con probabilità bassa è un candidato "1 credito all'ultimo giro".
- **Manie della lega**: scarto mediano per reparto, per squadra di Serie A (con almeno 5
  acquisti) e per fascia, stampato con il numero di casi.
- **Regola**: se in una cella nessun modello batte la baseline lineare di tutta la lega, si usa la baseline.

## 4. Valore e tetto (`piano_asta.py`)

- **Valore stagionale** di un giocatore: fantavoto atteso × presenze attese, dalle stime di
  `proiezioni` (listone + titolarità osservata + scouting quando c'è).
- **Valore di una rosa** = fantapunti attesi a giornata della formazione migliore con la panchina
  (`schiera.migliore_semplice` + `valore_atteso`), per il numero di giornate che restano.
- **Tetto** del giocatore *i* = il prezzo *p* per cui
  `V(miglior rosa con i pagato p) = V(miglior rosa senza i)`, trovato per bisezione su *p* fra 1 e
  il budget disponibile (V è non crescente in *p*). Calcolato per i candidati rilevanti (i primi
  ~40 per reparto per valore), non per tutti i 500.
- Il tetto usa i fantapunti **medi**: la varianza resta alla formazione settimanale. Il tetto è
  un numero solo; accanto si stampa la fonte della stima del giocatore (`listone`, `quotazione`,
  `scouting`...) perché si sappia quanto è solido.

## 5. Ottimizzatore della rosa

- **Problema**: scegliere 3/8/8/6 giocatori che massimizzano V(rosa), con la somma dei prezzi
  **mediani previsti** ≤ budget − (slot ancora vuoti × 1).
- **Metodo**: ricerca locale a scambi (un giocatore fuori, uno dello stesso reparto dentro, se
  migliora V rispettando il budget) da più rose di partenza valide (casuali con seme fisso, più
  "la più economica" e "la più forte che entra nel budget"); si tiene la migliore. Deterministica
  a parità di seme.
- **Vincoli di default** (da `docs/studio-asta-2026-27.md`, modificabili da `lega.json` → `asta`):
  - portieri: al massimo **10 crediti in tutto**;
  - fascia 25-49 crediti: al massimo **2 giocatori**, oltre solo con indice di scouting ≥ 0,3;
  - un giocatore già comprato da altri non esiste più per il piano.
- **Ordine di chiamata** P → D → C → A (configurabile): il piano indica per ogni reparto il
  **budget da non superare**, cioè la somma dei prezzi mediani previsti dei bersagli del reparto
  **più il 10%**, così i crediti arrivano all'ultimo reparto, dove la lega vende a sconto.

## 6. Output e live

- `python piano_asta.py` (e `socio.py asta`): per ogni reparto nell'ordine di chiamata, i
  bersagli con **forchetta di mercato | tetto | 2 alternative** ("se lo perdi oltre X, vai su Y
  fino a Z"), il budget di reparto e la struttura risultante (quanti top, medi, da 1-5 crediti).
- Accanto a ogni candidato: **affare** (tetto sopra il 75% della forchetta), **da giocare**
  (tetto dentro la forchetta), **lascia** (tetto sotto il 25%). Chi è fuori dai ~40 candidati per
  reparto del § 4 non ha tetto e compare come **fuori piano**, con la sola forchetta di mercato.
- **Live**: con `fanta.py --live asta.json` (formato esistente), dopo ogni assegnazione il piano si
  ricalcola con budget, slot e giocatori rimasti; i prezzi previsti dei rimasti si correggono col
  termometro del mercato già calcolato da `fanta.mercato()`.

## 7. Verifica: rigiocare l'asta del 05/09

- Solo informazioni di agosto: listone e FVM di agosto, stagione 2025/26. Nessun voto 2026/27.
- Per ogni bersaglio nell'ordine P → D → C → A: se il tetto ≥ prezzo pagato davvero + 1, il
  giocatore è "tuo" a prezzo+1 (budget che scende); altrimenti si passa all'alternativa. Un
  giocatore che nessuno ha comprato si prende a 1.
- Si confronta la rosa ottenuta con la vera AL DOMORO e con le altre 9 su:
  forza stimata oggi (`socio.py lega`), fantamedia delle giornate giocate, valore FVMp di oggi.
- **Ottimista per costruzione** (gli altri avrebbero reagito ai rilanci): è dichiarato
  nell'output. Un test impone che la verifica non legga dati successivi al 05/09.

## 8. Componenti

| file | responsabilità |
|---|---|
| `mercato_asta.py` | modello di prezzo per reparto e fascia, forchette, probabilità di acquisto, manie, validazione leave-one-out |
| `piano_asta.py` | valore di rosa, ottimizzatore, tetto per bisezione, piano per reparto, ricalcolo live, rigioco dell'asta |
| `socio.py` | comando `asta` (piano) e `asta --rigioca` (verifica) |
| `lega.json` | sezione `asta`: ordine di chiamata, vincoli, budget |
| `tests/qa_socio.py` | test con controprova: leave-one-out onesto (il giocatore non entra nel proprio modello), scelta di modello per cella, tetto = indifferenza, vincoli rispettati, ottimizzatore mai peggio della rosa di partenza, rigioco senza dati futuri |

## 9. Due piani di implementazione, in quest'ordine

1. **Prezzo di mercato** (§ 3): `mercato_asta.py`, validazione, manie. Utile da solo: dice dove la
   lega strapaga e dove regala.
2. **Piano d'asta** (§§ 4-7): valore, tetto, ottimizzatore, output, live, rigioco dell'asta.

## 10. Miglioramenti del tool, in ordine di resa

1. Registrare ogni asta (prezzi, ordine di chiamata, acquirente): il modello di prezzo passa da stima a dato.
2. Voti di giornata di tutta la Serie A (`voti_2026-27.csv`): presenze vere per tutti, dispersione reale.
3. Misurare le probabili (P_XI / P_FUORI) contro i voti della domenica.
4. Scouting qualitativo (spec collegata), soprattutto per i gioielli dell'ultimo reparto.
5. Rigoristi e calci piazzati come dato.
6. Calendario di Serie A per le partite vere.
7. Routine del giovedì sul PC: probabili + `socio.py settimana` + riepilogo.

## 11. Rischi dichiarati

- **Un'asta sola**: forchette larghe; il modello migliora solo registrando le prossime.
- **Effetto ordine ipotizzato, non misurato**: il modello per reparto lo cattura senza spiegarlo.
- **Ottimizzatore euristico**: niente garanzia di ottimo globale; più partenze e un test "mai
  peggio della partenza".
- **Valore dalle stime**: se le stime sono sbagliate, il tetto lo è; per questo la verifica § 7
  è la condizione di successo, non un extra.
