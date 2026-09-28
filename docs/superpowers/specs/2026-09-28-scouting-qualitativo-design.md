# Scouting qualitativo — design

**Data:** 28/09/2026 · **Stato:** design approvato in chat (sezioni 1-3), spec in revisione
**Metodo:** Superpowers (obra) — brainstorming, percorso *architetturale*

## 1. Perché

Il tool d'asta ha lavorato solo sui numeri e, per chi lo ha usato, è stato mediocre proprio dove
contava: scoprire i gioielli da 1-5 crediti. Il repo lo aveva già misurato: la previsione dei
breakout fatta coi soli dati ha lift **0,25x** (`talenti.py`). Resta la strada qualitativa: chi
gioca, dove, per quale allenatore, con quali compiti, con che testa.

Il vincolo che rende questa strada diversa da un'opinione: **ogni giudizio ha prova, fonte e
data, e viene misurato** contro quello che succede dopo.

Cosa dicono già i dati della lega *porcodidiosanto* (28/09/2026, 5 giornate):
fra i giocatori pagati ≤ 5 crediti, gli **attaccanti di neopromosse** sono stati un colpo
(FM ≥ 7) 4 volte su 10, quelli delle altre squadre 2 su 16; difensori e portieri economici 0 su 41.

## 2. Obiettivo e criterio di successo

- **In stagione:** entro l'asta di riparazione di **gennaio**, una lista corta di gioielli fra i
  giocatori **liberi** (listone meno le 10 rose), ciascuno con un prezzo massimo.
- **Asta di agosto 2027:** lo stesso strumento sul listone intero.
- **Successo:** a fine girone (giornata 19) lo scouting migliora le previsioni rispetto ai soli
  numeri sui giocatori schedati; a fine stagione i gioielli presi valgono più della media della
  lega nella stessa fascia di prezzo. Se no, il tool lo stampa e lo scouting perde peso.

Fuori perimetro: scouting dei giocatori già in rosa (possibile dopo, stesso formato); ricerca
automatica senza revisione umana; qualsiasi login a siti per conto dell'utente.

## 3. La scheda

Un file JSON per giocatore in `scouting/`, nome file libero:

```json
{
 "nome": "Varela G.",
 "squadra": "Monza",
 "ruolo": "A",
 "data": "2026-09-28",
 "autore": "claude",
 "kpi": {
  "spazio":         {"voto": 2, "prova": "titolare nelle prime 5 giornate, unico centravanti di ruolo", "fonte": "<link alla notizia>"},
  "palle_inattive": {"voto": 1, "prova": "batte le punizioni dal limite", "fonte": "<link alla notizia>"}
 },
 "note": "testo libero, non entra nei calcoli"
}
```

Regole di validità (una scheda o un KPI che non le rispetta viene **scartato e dichiarato**):

- `nome` e `data` (ISO, `AAAA-MM-GG`) obbligatori;
- ogni KPI: `voto` intero fra −2 e +2, `prova` non vuota, `fonte` non vuota (link o
  "osservato: <partita, data>");
- solo i KPI della tabella sotto: un campo sconosciuto invalida la scheda (niente KPI inventati);
- una scheda **scade dopo 60 giorni** dalla sua data: non si applica e il tool lo dice.

## 4. Gli 8 KPI

| KPI | domanda | −2 | +2 | peso iniziale |
|---|---|---|---|---|
| `spazio` | giocherà? | riserva chiusa | titolare inamovibile | 1,0 |
| `ruolo_tattico` | quanto gioca vicino alla porta? | compiti difensivi | libero di attaccare | 0,8 |
| `palle_inattive` | rigori, punizioni, corner | nessuna | rigorista designato | 0,6 |
| `contesto` | la squadra gli fa fare bonus? | chiusa e sterile | offensiva / neopromossa che gli dà minuti | 0,6 |
| `allenatore` | fiducia del tecnico | fuori dai piani | voluto da lui | 0,5 |
| `fisico` | infortuni, condizione | cronico / rotto | integro e in forma | 0,5 |
| `traiettoria` | in crescita? | in calo | età e stagione in rampa | 0,4 |
| `carattere` | affidabilità e fame | indisciplina documentata | leader / motivato | 0,3 |

`carattere` si vota **solo su fatti verificabili** (cartellini, squalifiche, dichiarazioni,
episodi riportati); un'impressione non è una prova. I pesi sono stime dichiarate: la verifica
del § 7 li ricalibra.

## 5. Dalla scheda alle stime

- **Indice** ∈ [−1, +1] = Σ peso·voto sui KPI validi / (2 · Σ di tutti i pesi). Un KPI mancante
  vale 0, non "neutro stimato".
- **Confidenza** ∈ [0, 1] = somma dei pesi dei KPI documentati / somma di tutti i pesi.
- **Correzione limitata** applicata a una *copia* delle stime (`proiezioni`):
  - probabilità di giocare: `p += 0,15 · spazio/2`, poi tagliata a [0,02; 0,98];
  - fantavoto atteso: `mu += 0,6 · indice_senza_spazio`, dove `indice_senza_spazio` è l'indice
    calcolato con la stessa formula ma **escludendo `spazio`** sia dal numeratore sia dalla somma dei
    pesi (lo spazio agisce già su `p`, contarlo due volte gonfierebbe la correzione); mai oltre ±0,6;
  - la fonte della stima diventa `"... + scouting (data)"`.
- Il qualitativo **sposta** le stime, non le sostituisce: serve a far pendere la bilancia fra
  giocatori simili, non a inventare un campione.

## 6. L'imbuto e l'output per gennaio

1. **Liberi** = listone Fantacalcio.it meno le rose di `rose.csv`. Serve il listone completo
   (dal PC dell'utente): senza, il comando lo dice e si ferma.
2. **Segnali strutturali** (dai dati, niente ricerca) che ordinano i candidati:
   - reparto: A > C offensivi > resto (dato della lega, § 1);
   - squadra neopromossa, o squadra sopra la media per gol fatti;
   - minuti in crescita (presenze nelle ultime 3 giornate vs le prime), quando ci sono i voti di giornata;
   - quotazione bassa.
   Ogni segnale è dichiarato nell'output accanto al giocatore.
3. **~30 candidati** in cima (più quelli aggiunti a mano) → Claude compila le schede con le
   fonti → l'utente le rivede.
4. **Lista gioielli**: per ciascuno indice, confidenza, fantapunti in più nella formazione
   dell'utente da gennaio a fine stagione (`mercato.svincolati` sulle stime corrette) e **prezzo
   massimo** consigliato.
5. **Prezzo massimo**, a somma zero come i prezzi d'asta di `fanta.py`: dati il budget `B` che
   l'utente avrà a gennaio e gli `S` slot da riempire (opzioni `--budget` e `--slot`), si prendono
   i primi `S` gioielli per guadagno e a ciascuno va `1 + (B − S) · guadagno_i / Σ guadagno`,
   poi i tetti dello studio d'asta (`docs/studio-asta-2026-27.md`): **massimo 25 crediti** per
   chiunque, **massimo 5** per i portieri. I crediti tagliati dai tetti restano non spesi, e lo si
   dice: meglio arrivare in fondo all'asta con crediti che pagarli nella fascia peggiore.

## 7. Verifica, senza futuro

- Ogni scheda si confronta **solo con le giornate successive alla sua data** (test obbligatorio,
  come `verifica.stime_prima`).
- A fine girone, per ogni KPI: i giocatori con voto alto hanno reso più di quelli con voto basso
  **a parità di stima numerica**? Output: una riga per KPI con differenza e numero di casi.
- Se lo scouting nel complesso non batte i soli numeri, il socio lo scrive in testa all'output
  (stesso patto di `valida.py`), e i pesi scendono.

## 8. Componenti

| file | responsabilità |
|---|---|
| `scouting.py` | `KPI` (pesi, domande), `valida`, `carica(cartella) -> (schede, errori)`, `indice`, `applica(E, schede, oggi)`, `segnali(g, neopromosse)`, `candidati(...)`, `gioielli(...)`, CLI |
| `socio.py` | carica `scouting/` se esiste, applica alle stime, avvisa di schede scartate/scadute; comandi `scouting candidati` e `scouting gioielli --budget B --slot S` |
| `verifica.py` | resa per KPI dopo la data della scheda |
| `.claude/skills/scouting/SKILL.md` | come Claude scheda un giocatore: ricerche, fonti ammesse, come dare i voti, niente voto senza link; scritta con `superpowers:writing-skills` |
| `tests/qa_socio.py` | test con controprova per ogni regola dei §§ 3, 5, 7 |
| `lega.json` | `neopromosse` (lista) e `file.listone` |

## 9. Rischi dichiarati

- **Ricerca costosa:** ~30 schede per finestra. Mitigazione: imbuto dai dati, skill che fissa il metodo.
- **Fonti opinabili** (giornali, probabili): la prova deve dire *cosa* è successo, non cosa pensa il giornalista.
- **Campione piccolo** a fine girone: la ricalibrazione dei pesi è prudente (mai sotto 0, mai più del doppio in un colpo).
- **Pregiudizio del narratore:** chi scrive la scheda conosce già i numeri. Per questo il
  `carattere` pesa poco e ogni KPI viene misurato separatamente.
