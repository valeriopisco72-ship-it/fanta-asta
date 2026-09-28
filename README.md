# fanta-asta · il socio di fantacalcio

> **Stato al 28/09/2026** — 132/132 test del socio + 68/68 dell'asta verdi
> (`python tests/qa_socio.py`, `python tests/qa_fanta.py`).
>
> | | |
> |---|---|
> | ✅ **Prezzi d'asta** tarati sulla tua lega (VORP, somma zero, termometro live) | solido, testato |
> | ✅ **Titolarità osservata** dalle probabili formazioni (`formazioni.py`) | +22% di accordo col mercato |
> | ✅ **Analisi calcistica** (xG/xA, contesto tattico, allenatori) | solido, con limiti dichiarati |
> | ✅ **Pavimento di sostituzione** | **contato**, non più stimato: i titolari veri di Serie A |
> | 🆕 **Formazione della settimana** (modulo, XI, panchina, rischio vs avversario) | testato; +2,2 fantapunti/giornata **su dati finti** |
> | 🆕 **Scambi e svincolati** misurati sulla TUA formazione | testato |
> | 🆕 **Calendario e griglia portieri** | testato; forza squadre ancora grezza a inizio stagione |
> | 🆕 **Backtest sui tuoi voti** (`socio.py verifica`) | è lo strumento per smentire tutto quello sopra |
> | ⚠️ **Riparto del budget fra reparti** | **delegato al mercato**: il modello non ha edge |
> | ❌ **Previsione dei breakout** | **misurato lift 0,25x: non funziona** |
>
> Le ultime due righe non sono lavori incompiuti: sono risultati negativi verificati.
> Vedi `valida.py`, l'intestazione di `talenti.py` e la sezione sulla calibrazione.

## Il socio di stagione — `socio.py` (nuovo)

L'asta è una sera. Il campionato sono **38 formazioni**, un paio di finestre di mercato e
una decina di scambi proposti: è lì che si vince, ed era la parte che il tool non toccava.
`socio.py` la copre con un metro solo, lo stesso VORP dell'asta portato in stagione:
**un giocatore vale quello che cambia nella TUA formazione**, non in astratto.

```bash
python esempio.py --stagione                               # lega FINTA completa per provarlo
python socio.py --lega esempio_stagione/lega.json settimana
```

| comando | cosa risponde |
|---|---|
| `socio.py settimana` | il briefing del giovedì: allarmi (squalificati, diffidati, a rischio), formazione, portieri, svincolati |
| `socio.py formazione [--avversario X]` | modulo + XI + **ordine della panchina**; negli scontri diretti P(vittoria/pareggio/sconfitta) |
| `socio.py rosa` | i tuoi giocatori: fantavoto atteso, probabilità di giocare, da dove viene la stima |
| `socio.py scambio --dai "A" --ricevi "B,C"` | effetto sulla tua formazione nelle prossime giornate, **accanto** alla somma grezza |
| `socio.py svincolati [--ruolo C]` | chi prendere e **chi tagliare** |
| `socio.py portieri` | gol subiti attesi dei tuoi portieri e la coppia migliore, anche con i liberi |
| `socio.py verifica` | backtest: le stime ci azzeccano sui tuoi voti veri? |

### Le tre idee

1. **Negli scontri diretti non si massimizza la media.** Da favorito la varianza è il
   nemico; da sfavorito è l'unica speranza ([pub] è un risultato classico del fantasy
   americano: [Footballguys](https://www.footballguys.com/article/DFS_expectationvariance),
   [Fantasy Footballers](https://www.thefantasyfootballers.com/articles/variance-in-fantasy-football-embrace-the-chaos/)).
   `schiera.py` simula la giornata (Monte Carlo, numeri casuali comuni fra le formazioni
   candidate) con **le fasce gol della tua lega** e sceglie la formazione che massimizza i
   punti in classifica attesi. Il test lo verifica in entrambe le direzioni, e su 10 semi
   casuali su 10.
2. **Uno scambio si misura sulla formazione.** "Do un 6,5 e prendo un 7" è sbagliato quando
   il 7 finisce in panchina o quando il 6,5 era il tuo unico portiere affidabile. Il comando
   stampa i due numeri uno accanto all'altro: la differenza è il motivo per cui esiste.
3. **La panchina ha un valore, e si calcola.** Con la probabilità di giocare per ogni
   giocatore, il valore di un reparto è esatto (Poisson-binomiale: "i primi k che scendono in
   campo, nell'ordine") e la simulazione fa entrare i cambi fino al tetto della lega.

### I file

Tutti opzionali tranne la rosa; ogni file mancante viene **detto in testa all'output**.

| file | cosa | dove |
|---|---|---|
| `lega.json` | regole della lega (bonus, fasce gol, modificatore, moduli, cambi), la tua squadra, i percorsi | lo scrivi tu (v. `regole.py`, esempio in `esempio_stagione/`) |
| `rose.csv` | `FantaSquadra;Nome` per tutte le squadre della lega | lo scrivi tu (o export della piattaforma) |
| `voti/*.xlsx\|csv` | un file per giornata, formato voti di Fantacalcio.it | [fantacalcio.it/voti-fantacalcio-serie-a](https://www.fantacalcio.it/voti-fantacalcio-serie-a) |
| `calendario.csv` | `Giornata;Casa;Trasferta;GolCasa;GolTrasferta` | calendario Serie A |
| `titolari.csv` | probabili formazioni | `python formazioni.py` |
| `listone_completo.csv` | quello dell'asta: prior dalla stagione scorsa | `unisci.py` |

Esempio minimo di `lega.json`:

```json
{
 "nome": "Fantalega del bar",
 "mia": "FC Tuoi",
 "formula": "scontri",
 "bonus": {"porta_inviolata": 1, "gol": {"D": 4.5}},
 "soglie": [66, 72, 77, 81, 85, 89],
 "max_sostituzioni": 5,
 "panchina": 12,
 "rendimento": {"attivo": true},
 "capitano": {"attivo": true, "giocatore": "Gonzalez N.", "vice": "Rabiot"},
 "calendario_lega": {"6": "FC Avversari", "7": "FC Altri"}
}
```

Il `lega.json` nella radice del repo è quello vero della lega *porcodidiosanto*: modificatore
difesa a 5 fasce (6 / 6,25 / 6,5 / 6,75 / 7 → +1 / +2 / +3 / +4,5 / +6), rendimento, capitano
fisso sul voto puro, 5 cambi a pari ruolo, fasce gol 66 + 6. Quello che non è stato osservato
(bonus individuali, lunghezza della panchina) è elencato nel file sotto `_da_verificare`.

### Cosa è misurato e cosa no

- **Misurato su dati finti** (`esempio.py --stagione`, 6 stagioni × 10 rose × 18 giornate):
  la formazione del socio fa **+2,2 ± 0,24 fantapunti a giornata** rispetto a quella
  "ingenua" (3-4-3 coi migliori per fantamedia finora). Sull'errore per giocatore batte
  nettamente la fantamedia finora (0,98 contro 1,10 di errore medio) e **pareggia col listone**
  — che nei dati finti è quasi un oracolo, nella realtà no.
  **Non è una promessa sui dati veri**: il generatore l'ho scritto io, e un modello che batte
  i dati che ha generato il suo autore dimostra solo che non è rotto.
- **Da misurare sui tuoi dati:** `python socio.py verifica` rifà le stime giornata per giornata
  usando solo il passato (un test impone che non sbirci il futuro) e le confronta con i voti
  veri. Se il socio non batte le baseline, lo stampa.
- **Stime dichiarate, non misurate:** probabilità di giocare di chi è / non è nelle probabili
  (0,90 / 0,15), fattore campo 1,12, peso del prior (6 partite), taglio delle code del fantavoto
  (2 deviazioni). Sono in cima a `proiezioni.py` e `calendario.py`, con scritto sopra che sono
  stime. La prima da misurare è la probabilità delle probabili: si fa confrontando
  `titolari.csv` del giovedì con i voti della domenica.
- **Non modellato:** infortuni oltre alle probabili, rigoristi, correlazione fra compagni di
  squadra (se la difesa prende 4 gol soffrono tutti), il "cambio modulo" di alcune leghe.

Il piano di lavoro con le scelte e i perché è in [`docs/piano-socio.md`](docs/piano-socio.md).

---

## L'asta — `fanta.py`

Prezzi limite per l'asta del fantacalcio, tarati sulla **tua** lega.
Classic, 10 squadre, 500 crediti (configurabile da riga di comando).

**Stato:** 80/80 test verdi (`python tests\qa_fanta.py`), verificato end-to-end su
listone e su asta live. Nessuna dipendenza esterna per i CSV; per gli `.xlsx` serve
`openpyxl`.

---

## L'idea in tre righe

Il ranking dei giocatori è una commodity: le quotazioni ufficiali ce le hanno tutti.
Quello che decide l'asta è il **surplus** — valore atteso meno prezzo atteso — e il
prezzo dipende dalla tua lega, non dalla media nazionale.

1. **VORP**: un giocatore vale quanto supera il *peggior titolare che prenderesti
   comunque* nel suo ruolo. Con 10 squadre × 3 portieri il pavimento è il 30° portiere;
   con 12 squadre è il 36°, molto più in basso, e i portieri buoni valgono di più.
2. **Somma zero**: 10 × 500 = 5.000 crediti verranno spesi *tutti* su 250 giocatori.
   La somma dei prezzi consigliati fa esattamente 5.000, per costruzione.
3. **Prezzo di riserva dinamico**: durante l'asta i limiti si ricalcolano.

## Cosa serve

Un file di quotazioni `.csv` o `.xlsx` con almeno **Nome, Ruolo, Quotazione**.
Se ha anche **Fantamedia** e **Presenze** della stagione scorsa, il tool costruisce una
stima *indipendente* dal mercato — ed è l'unico caso in cui può trovare occasioni vere.

Dove prenderlo:
- quotazioni ufficiali → <https://www.fantacalcio.it/quotazioni-fantacalcio>
- statistiche stagione precedente → <https://www.fantacalcio.it/statistiche-serie-a>
- archivio storico scaricabile → <https://www.fanta.soccer/it/archivioquotazioni/>

Le intestazioni vengono riconosciute da sole (`Qt.A`, `Qt. A`, `quotazione`, `R`,
`Ruolo`…), separatore `;` o `,`, e i ruoli Mantra vengono ricondotti al reparto Classic.
Se manca una colonna essenziale il tool **si ferma e lo dice**, non tira a indovinare.

## Uso

Prova senza dati veri:

```bash
python esempio.py
python fanta.py --quot esempio_quotazioni.csv
```

Sul file vero:

```bash
python fanta.py --quot quotazioni.xlsx
python fanta.py --quot quotazioni.xlsx --ruolo A --top 40
python fanta.py --quot quotazioni.xlsx --squadre 8 --budget 300 --slot 3,8,8,6
```

### Durante l'asta

Apri un terminale e tienilo lì. Dopo ogni assegnazione registri chi è andato e a quanto:

```bash
python fanta.py --quot quotazioni.xlsx --live asta.json --venduto "Lautaro" 180
python fanta.py --quot quotazioni.xlsx --live asta.json --compra "Thuram" 95
```

`--venduto` = l'ha preso un avversario · `--compra` = l'hai preso tu (scala il tuo budget).
Lo stato è su `asta.json` e sopravvive alla chiusura del terminale.

Ogni volta il tool ristampa i limiti aggiornati più il **termometro del mercato**:

```
termometro del mercato: 1.87x  CARO: gli avversari stanno strapagando.
   Hanno bruciato 141 crediti sopra il valore.
   -> il resto del listone costera MENO del previsto: aspetta e prendi valore a sconto.
```

È la lettura che un listone statico non può darti. Il pavimento di sostituzione **non**
si muove quando i giocatori vengono venduti (l'indice scala insieme a loro), quindi
l'unica cosa che sposta i prezzi residui è **quanto budget è uscito rispetto a quanto
valore è uscito**:

- **indice > 1** → strapagano: restano meno crediti in circolo, il resto costerà meno.
  Il tuo potere d'acquisto è cresciuto senza che tu abbia fatto niente.
- **indice < 1** → comprano a sconto: si portano via valore per poco e resta più
  concorrenza sui crediti. Alza i limiti o rimani con la rosa peggiore.

## Cosa NON fa, dichiarato

- **Non prevede il rendimento dei giocatori.** Usa la fantamedia della stagione scorsa
  regredita verso la media del ruolo (più regressione se le presenze sono poche: 8.0 di
  fantamedia in 4 partite non è un dato, è rumore). Niente xG, niente calendario, niente
  infortuni, niente rigoristi. È l'input a più bassa leva: ci sbagliamo tutti allo stesso
  modo, e non è lì che si vince.
- **Se il file non ha statistiche storiche**, il tool usa la quotazione ufficiale come
  proxy del valore **e lo scrive in testa all'output**: in quel caso sta riordinando il
  consenso di mercato per scarsità di ruolo, non battendolo. Utile per il budget, inutile
  per le occasioni.
- **Non indovina niente dai silenzi.** Se non registri un'assegnazione, per il tool quel
  giocatore è ancora disponibile. È un registro, non un osservatore.
- Le presenze attese di default (`PRES_ATTESE` in `fanta.py`) sono **stime** dichiarate,
  non dati.
- ⚠️ **I portieri restano probabilmente sopravvalutati.** Giocano 38 partite, quindi
  accumulano molti fantapunti totali anche con fantamedia bassa, e il loro pavimento di
  sostituzione è bassissimo (il 30° portiere è una riserva con 2 presenze). Una parte di
  questo effetto è reale — un titolare vale davvero molto più di una riserva — ma il
  livello no. Sul listone vero il tool mette Falcone, Caprile e Muric fra le occasioni
  principali: sono titolari veri, quindi non è assurdo, ma **prendilo come un ordine di
  grandezza, non come un prezzo**. Il fix serio è modellare i gol subiti attesi, e non c'è.

## File

```
fanta.py              l'asta (CLI)
socio.py              la stagione: formazione, scambi, svincolati, portieri, verifica
regole.py             il regolamento della lega (lega.json)
voti.py               archivio dei voti di giornata
proiezioni.py         fantavoto atteso, dispersione, probabilita di giocare
calendario.py         forza squadre, difficolta, griglia portieri
schiera.py            formazione ottima e simulazione della giornata
mercato.py            scambi e svincolati sul valore della formazione
verifica.py           backtest walk-forward sui voti veri
nomi.py               chiavi comuni per giocatori e squadre
esempio.py            listone finto (--stagione: lega finta completa)
tests/qa_fanta.py     test dell'asta, con controprove
tests/qa_socio.py     test del socio, con controprove
```

## 🔴 Il difetto n.1 del tool, oggi: il pavimento di sostituzione

Il VORP misura quanto un giocatore supera il *rimpiazzo*. Ma chi è il rimpiazzo?

Fino al 10/08 era **l'ultimo giocatore comprato** (il 30° portiere, l'80° difensore). Sbagliato:
il terzo portiere non è la tua alternativa, perché non lo schieri mai. L'alternativa vera è
**l'ultimo titolare disponibile**. Compri 3 portieri e ne schieri 1; compri 8 difensori e ne
schieri 3.

Corretto con `TITOLARI` + `PESO_PANCHINA` (0 = pavimento sui soli titolari, 1 = vecchio
comportamento). **Ma la correzione ha aperto un problema più grande di quello che ha chiuso:**

| `--peso-panchina` | Pavimento portieri | Limite su Svilar |
|---|---|---|
| 0.0 | 154 punti | 62 |
| **0.35** (default) | 52 punti | **76** |
| 1.0 | 4 punti | 49 |

**Un parametro scelto da me muove il prezzo del 55%, e non è nemmeno monotono.** Il 0.35 non
viene da nessuna fonte: è una mia stima di quanto valga una riserva. È lo stesso errore che in
`prezzo.py` di land-scout aveva prodotto un verdetto falso — con la differenza che stavolta è
dichiarato, parametrizzato e testato invece di essere sepolto in una costante.

### Come si calibra — `--calibra` (17/08/2026)

I prezzi *reali pagati* in aste passate della tua lega non ce li ho, e restano il riferimento
migliore. Ma un'ancora esterna il listone ce l'aveva già e il tool non la leggeva: la colonna
**FVM** di Fantacalcio.it, cioè la loro stima del prezzo d'asta su 500 crediti. Non sono prezzi
pagati — è **consenso di mercato**, e va letta per quello che è. È però abbastanza per trasformare
`PESO_PANCHINA` da parametro libero nell'incognita di un'equazione: *quale valore riproduce lo
split di budget per ruolo che il mercato si aspetta?*

```bash
python fanta.py --quot listone_completo.csv --calibra
```

Confronto sui 250 giocatori che la lega compra davvero (non sui 503 del listone: due scale diverse
sono confrontabili solo sullo stesso universo), tutto riscalato su 5.000 crediti:

| ruolo | FVM (mercato) | peso 0.00 | **peso 0.35** (default) | peso 1.00 |
|---|---|---|---|---|
| P | **297** | 409 | **827** | 636 |
| D | 947 | 797 | 979 | 1.357 |
| C | 1.705 | 1.482 | 1.277 | 1.310 |
| A | 2.051 | 2.312 | 1.917 | 1.696 |
| **scarto dal mercato** | — | **745** | 1.126 | 1.499 |

Su una griglia di 21 valori il minimo cade a **0.00**, non a 0.35: il mercato dice che il pavimento
di sostituzione va messo sui **soli titolari**, e che la panchina non conta quasi niente. Il default
scelto a mano sbagliava di 1.126 crediti su 5.000, quasi tutti sui portieri (827 contro 297: **2,8x**).

**Due cose che questo NON risolve, e vanno dette:**

1. Il minimo è **sul bordo del dominio** (0.00). Un parametro che va a fondo scala non è tarato: è
   un parametro che ha finito la corsa prima di chiudere il buco. Il gap resta.
2. Anche a 0.00 i portieri valgono 409 contro 297 di mercato — **+38%**. La sopravvalutazione
   strutturale sopravvive alla calibrazione, quindi non era `PESO_PANCHINA`: è il pavimento stesso.
   Il fix resta quello dichiarato — modellare i gol subiti attesi — e non c'è.

Prima di fidarti di un prezzo, gira comunque il tool con almeno due valori e guarda quanto si muove.

### Il pavimento di sostituzione: erano due difetti, non uno (17/08/2026)

Il primo tentativo — soglia = fm del rango × presenze di un titolare — è stato **provato e
scartato**: sistemava i portieri (827 → 358 contro 297 di mercato) e rompeva gli attaccanti
(1.917 → 1.279 contro 2.051), perché il budget è a somma zero. Restava la diagnosi senza la cura.

La cura è arrivata guardando **cosa c'era dentro la lista ordinata**, non come la si tagliava.

**Difetto 1 — due unità di misura nello stesso campo.** 144 giocatori su 503 (il 29%) non hanno
storico, e per loro `punti` conteneva la **quotazione** (scala 1-35) accanto a punti veri
(70-200). Non è una stima bassa: è un'unità di misura diversa — lo stesso errore che il README
documenta per lo `scarto`. Conseguenze: quei 144 finivano sotto a *chiunque* per costruzione — e
sono i nuovi acquisti, cioè i più cari del listone — e il pavimento ci atterrava sopra (il primo
portiere senza storico stava al rango 30, cioè esattamente dove `--peso-panchina 1.0` lo mandava,
facendolo crollare a 4 punti).
Corretto riportandoli sulla scala giusta **per quantile** (non con un fattore: la relazione
quota-punti non passa per l'origine) e **dentro lo stesso stato di titolarità**, altrimenti la
riscalatura sovrascriveva i punti e buttava via proprio l'XI.

**Difetto 2 — il pavimento era stimato invece che contato.** `titolari.csv` dice quanti titolari
esistono davvero in Serie A per ruolo: **20 portieri, 81 difensori, 79 centrocampisti, 34
attaccanti**. Se in Serie A giocano 20 portieri e tu ne schieri 10, la tua alternativa è il 20°
— non il 30° (una riserva che non gioca mai) né il 10° (che è già un titolare di prima fascia).
Il numero è **contato**, non scelto: per questo sostituisce `PESO_PANCHINA` invece di tararlo.

La conferma che non è fitting: cercando a forza il pavimento che minimizza lo scarto dal mercato,
il rango ottimo per i portieri viene **20** — esattamente il conteggio. Su difensori (68 vs 80) e
centrocampisti (72 vs 79) cade entro il rumore. `PESO_PANCHINA` resta solo come ripiego quando
`titolari.csv` non c'è.

**Misurato contro la versione pubblicata**, sui 250 giocatori che la lega compra:

| | ordinamento (Spearman vs FVM) | | dispersione (errore medio, crediti) | |
|---|---|---|---|---|
| | prima | dopo | prima | dopo |
| Portieri | 0,624 | **0,696** | 3,28 | 3,48 |
| Difensori | 0,330 | **0,495** | 7,49 | **5,20** |
| Centrocampisti | 0,423 | **0,547** | 12,58 | **10,74** |
| Attaccanti | 0,460 | 0,351 | 30,72 | **22,49** |
| **media** | 0,459 | **0,522** | 13,52 | **10,37** |

**Il costo, dichiarato: gli attaccanti perdono sull'ordinamento** (0,460 → 0,351). Isolando le due
correzioni si vede perché: la riscalatura da sola li porta a **0,493**, il pavimento contato li
riporta a 0,351. Per gli attaccanti il conteggio (34 titolari veri) è più *basso* del pavimento
vecchio (rango 40), quindi più attaccanti finiscono con VORP zero e pareggiano in fondo. È il
ruolo dove i due difetti si ostacolano, e non l'ho risolto: l'ho misurato e lasciato scritto.

Un'ipotesi intermedia — che i pareggi della mappatura a quantile spiegassero il calo — è stata
**testata e falsificata** (interpolare non ha spostato lo Spearman di un millesimo), quindi
l'interpolazione è stata tolta invece di essere tenuta come spiegazione che suona bene.

## Analisi tecnico-tattica di squadre e allenatori

`squadre.py` legge i dati di squadra Understat (PPDA, passaggi profondi, npxG/npxGA per partita,
punti attesi) e li incrocia con un **registro allenatori 2026/27 compilato a mano e datato**.

```bash
python squadre.py                 # quadro completo
python squadre.py --continuita    # dove il dato vale e dove no
python squadre.py --portieri      # forza difensiva -> valore del portiere
python squadre.py --sorprese      # classifica vs meriti
python squadre.py --squadra Como
```

🔴 **Il fatto che governa tutto: il dato tattico è usabile su 9 squadre su 20.**
Otto hanno cambiato allenatore (Sarri all'Atalanta, Tedesco al Bologna, Grosso alla Fiorentina,
Gattuso alla Lazio, Amorim al Milan, Allegri al Napoli, Aquilani al Sassuolo, Abate al Torino) e
tre sono neopromosse senza alcun dato di Serie A (Frosinone, Monza, Venezia — con Juric che è
insieme allenatore nuovo *e* squadra senza dati). Per quelle squadre il 2025/26 **descrive il
passato, non prevede il futuro**, e il modulo lo stampa riga per riga invece di lasciartelo dedurre.

Il registro è manuale come quello dei nodi di rete in land-scout: un esonero a ottobre lo rende
sbagliato e non c'è modo di accorgersene da soli. Va riverificato prima di usarlo.

### Cosa ha corretto, concretamente

Fra la difesa che concede meno (Inter, 0,86 npxGA/partita) e quella che concede di più
(Lecce, 1,59) ballano **~28 punti fanta a stagione a parità di bravura del portiere**. Il tool
metteva **Falcone** in cima alle occasioni guardando le sue 38 presenze — e Falcone para nella
difesa peggiore del campionato. `--avanzate` ora applica la forza difensiva della squadra
**attuale** a tutti i portieri accoppiati.

⚠️ **Attenzione a cosa questo risolve e cosa no.** La correzione vale per chi *cambia* squadra;
per chi resta dov'era è nulla per costruzione (un test lo impone, altrimenti l'effetto verrebbe
contato due volte). La sopravvalutazione **strutturale** dei portieri — pavimento di sostituzione
bassissimo perché il 30° portiere è una riserva — resta aperta.

## Analisi avanzata — oltre il fantacalcio

`analisi.py` legge i dati Understat (xG, npxG, xA, xGChain, xGBuildup, **minuti**) e risponde a
quattro domande che gol e assist non pongono nemmeno:

```bash
python analisi.py                      # panoramica completa
python analisi.py --solo sovra         # chi ha segnato piu'/meno del dovuto
python analisi.py --solo creatori      # chi crea e non viene ripagato
python analisi.py --solo registi       # chi fa gioco senza prendere bonus
python analisi.py --solo tiri          # chi arriva in posizione buona
python analisi.py --squadra Napoli     # una squadra sola
python analisi.py --solo squadre       # produzione attesa vs reale, per club
```

| Metrica | Cosa dice | Perché conta |
|---|---|---|
| **gol − npxG** | finalizzazione oltre l'atteso | il gol è raro: su 30 partite la fortuna pesa quanto la bravura, e il delta rientra |
| **xA − assist** | palloni buoni sprecati dai compagni | cambia chi finalizza, cambiano gli assist |
| **xGBuildup/90** | contributo alla costruzione, **tolti tiri e assist** | l'unica metrica che vede il regista invisibile al fantacalcio |
| **npxG/tiro** | qualità della posizione di tiro | distingue chi arriva in area da chi tira da fuori |
| **minuti** | esposizione reale | venti spezzoni non sono venti partite |

Applicati al motore dei prezzi con `--avanzate`: sostituiscono i **bonus realizzati** con quelli
**attesi**, lasciando intatto il voto base (che è rumoroso e non si modella).

```bash
python fanta.py --quot listone_completo.csv --avanzate --ruolo A --top 40
```

⚠️ **Understat blocca i client non-browser**: `understat.py` esiste e documenta il formato, ma la
pagina servita a Python è una versione ridotta senza i dati. Il CSV incluso è stato estratto dal
browser — stesso patto delle visure in land-scout: il gesto va fatto a mano, il parsing no.

## Dati inclusi (scaricati il 10/08/2026 da Fantacalcio.it)

```
quotazioni_ufficiali.csv    503 giocatori, quotazioni 2026/27 + FVM
statistiche_2025-26.csv     663 giocatori, presenze/MV/FM/gol/assist/rigori calciati
listone_completo.csv        il merge dei due  <- questo e' il file da usare
unisci.py                   rifa' il merge quando riscarichi
```

Il merge copre **359/503 (71%)**, ma il buco pesa solo il **17% del listone a valore**.
Chi manca sono i nuovi arrivati dall'estero e dalla B — i piu' cari sono **Ramos G.** (27)
e **Kolo Muani** (26). Nessun modello costruito sullo storico italiano li vede: e' un limite
strutturale, non un difetto del merge, e `unisci.py` te lo stampa in faccia ogni volta.

## Tre bug trovati provando sui dati veri

Il listone sintetico non ne mostrava nessuno. Le quotazioni ufficiali sì.

0. **Le presenze passate non sono presenze attese.** Il caso: **Provedel**, 27 presenze con
   la Lazio 2025/26, oggi riserva dell'Inter a quotazione 2; **Paleari**, 29 presenze,
   quotazione **1**. Il tool li metteva in cima alle occasioni e consigliava di scartare i
   titolari che hanno preso il loro posto. Ora un `fattore_titolarita()` usa la quotazione
   — l'unico segnale su chi gioca *oggi* — per tagliare le presenze attese, **senza toccare
   la qualita' stimata**. L'esponente `ESP_TITOLARITA = 0.5` è **una stima mia, dichiarata
   in cima al file**: è il parametro più arbitrario del tool.

Il listone sintetico non li faceva vedere. Le quotazioni ufficiali sì.

1. **Unità di misura diverse.** La quotazione di Fantacalcio.it vive su una scala 1-35 che
   non somma al budget della lega; il limite del tool è in crediti su 5.000. Confrontarli
   dava *«+71 su Lautaro»*, che si legge come un affare colossale ed era solo un cambio di
   unità. Ora le quotazioni vengono **riscalate** perché la somma di quelle dei 250
   giocatori che verranno presi faccia esattamente il budget della lega.
2. **Allocazione ≠ occasione.** Anche senza storico gli scarti non erano nulli, e sembravano
   promettere occasioni che il tool non ha titolo di vedere. Il motivo è corretto — il VORP
   sottrae il pavimento e quindi sposta budget verso i top — ma il messaggio era sbagliato.
   Ora senza storico il tool **non riscrive la graduatoria** (un test lo impone) e dichiara
   che lo scarto è una raccomandazione di *allocazione*, non di *rendimento*.

## Nota di metodo

Un test di questa suite è nato sbagliato: pretendeva che, spariti i primi tre
attaccanti, il quarto valesse **di più**. I numeri dicono il contrario quando gli
avversari li strapagano — ed è il codice ad avere ragione. La versione attuale testa i
tre casi insieme (strapagati → scende, regalati → sale, pagati al modello → invariato):
è molto più difficile da soddisfare per caso, e ha prodotto la funzione `mercato()`, che
è la cosa più utile del tool. *Un test che conferma la tua intuizione non serve a niente
finché non provi a romperlo.*

---

## Titolarità osservata — `formazioni.py`

Il difetto n.1 del tool non era un parametro: era che **non sapeva chi gioca**. La
titolarità veniva dedotta da due proxy indiretti — le presenze della stagione scorsa e
la quotazione — e fra il 10° e il 20° portiere del listone i punti attesi crollavano
dell'83% mentre la fantamedia restava piatta. Il modello non stava dicendo «è più
scarso», stava dicendo «l'anno scorso non ha giocato». Un portiere promosso a titolare
e uno retrocesso a riserva erano indistinguibili.

```bash
python formazioni.py                 # scarica titolari.csv (220 titolari, 20 squadre)
python formazioni.py --stato         # quanti giorni ha il file
python fanta.py --quot listone.csv   # lo usa da solo se titolari.csv esiste
```

Fonte unica: `fantacalcio.it/probabili-formazioni-serie-a`, che dà modulo + XI delle 20
squadre con i **nomi nello stesso formato del listone** — il join è esatto, non fuzzy
(214/220 accoppiati; i 6 mancanti vengono stampati, non nascosti). Aggregare 5 testate
darebbe un gradiente 0-5 invece di un binario: non è stato fatto perché il guadagno non
è misurato, e sono 5 parser fragili invece di uno.

**Cosa ha cambiato, misurato** (Spearman fra prezzo del modello e FVM di mercato, sui
250 giocatori che la lega compra):

| | senza XI | con XI |
|---|---|---|
| Portieri | 0,503 | **0,624** |
| Difensori | 0,224 | **0,330** |
| Centrocampisti | 0,374 | **0,423** |
| Attaccanti | 0,401 | **0,460** |
| **media** | 0,375 | **0,459** (+22%) |

Migliora in tutti e quattro i ruoli. **Ma l'XI da solo peggiorava i livelli**: portieri
al 30% del monte crediti. Ordinamento buono, calibrazione no — da cui la scelta qui sotto.

### La rinuncia dichiarata: il riparto fra reparti va al mercato

Il modello decide **chi vale** dentro il ruolo; la colonna FVM decide **quanto** va a
ogni reparto. Non è un pareggio diplomatico: sul riparto fra reparti il tool ha sbagliato
in **ogni** configurazione provata (scarto 745-3.322 crediti su 5.000), e dopo la delega
scende a **154**. In più `--peso-panchina` smette di muovere l'allocazione fra reparti:
il parametro che spostava i prezzi del 55% ora agisce solo dentro il ruolo.

Chi vuole l'opinione indipendente del modello anche sul riparto deve toglierlo a mano
in `prezzi()` — ed è documentato lì perché è una scelta, non un dettaglio.

## Aggiornamento automatico

Le probabili formazioni cambiano ogni giorno. `aggiorna_xi.cmd` rilancia `formazioni.py`
e scrive in `aggiornamenti.log`; su Windows si registra così (**ogni giorno alle 08:00**):

```bash
schtasks /Create /SC DAILY /ST 08:00 /TN "fanta-asta aggiorna XI" /TR "%CD%ggiorna_xi.cmd" /F
```

Per toglierlo: `schtasks /Delete /TN "fanta-asta aggiorna XI" /F`.
Se `titolari.csv` ha più di 3 giorni, `fanta.py` lo dice in testa all'output: un XI
vecchio è peggio di nessun XI, perché sembra un dato.

## Dati e fonti

**Questo repository non contiene dati di terzi.** Il tool gira senza: `python esempio.py`
genera un listone finto per provarlo. I file veri li scarichi tu, e restano tuoi:

| dato | dove | usato da |
|---|---|---|
| quotazioni e FVM 2026/27 | [fantacalcio.it/quotazioni-fantacalcio](https://www.fantacalcio.it/quotazioni-fantacalcio) | `fanta.py` |
| statistiche stagione precedente | [fantacalcio.it/statistiche-serie-a](https://www.fantacalcio.it/statistiche-serie-a) | `unisci.py` |
| probabili formazioni | [fantacalcio.it/probabili-formazioni-serie-a](https://www.fantacalcio.it/probabili-formazioni-serie-a) | `formazioni.py` |
| xG, xA, npxG, xGChain | [understat.com](https://understat.com) | `understat.py`, `analisi.py`, `squadre.py` |
| voti di giornata | [fantacalcio.it/voti-fantacalcio-serie-a](https://www.fantacalcio.it/voti-fantacalcio-serie-a) | `voti.py`, `socio.py` |
| calendario e risultati Serie A | qualunque fonte, in `calendario.csv` | `calendario.py`, `socio.py` |

I marchi *Fantacalcio®* e i dati citati appartengono ai rispettivi titolari. Questo è un
progetto amatoriale, gratuito, senza scopo di lucro e non affiliato ad alcuna delle fonti.
Gli scraper sono per **uso personale**: rispetta i termini di servizio dei siti che
interroghi e non martellarli.

## Licenza

[AGPL-3.0](LICENSE). Usalo, modificalo, distribuiscilo — ma se ci costruisci sopra un
servizio accessibile in rete, il codice del servizio va condiviso con la stessa licenza.
