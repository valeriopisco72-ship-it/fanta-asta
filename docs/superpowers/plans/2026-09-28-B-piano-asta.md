# Piano d'asta: tetto e ottimizzatore della rosa — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** un piano d'asta reparto per reparto con, per ogni candidato, forchetta di mercato, tetto (prezzo di indifferenza) e alternative; ricalcolo live; verifica rigiocando l'asta del 05/09.

**Architecture:** `piano_asta.py` costruisce il valore dei giocatori dalle stime esistenti (`proiezioni.stima` sul listone), ottimizza la rosa con ricerca locale a scambi sui prezzi mediani di `mercato_asta`, calcola il tetto per bisezione confrontando la miglior rosa con e senza il giocatore, e produce il piano. Il live riusa lo stato JSON di `fanta.Asta`.

**Tech Stack:** Python 3 standard library; moduli del repo `proiezioni`, `schiera`, `regole`, `mercato_asta`, `fanta`. Test in `tests/qa_asta.py`.

**Spec:** `docs/superpowers/specs/2026-09-28-piano-asta-design.md` §§ 4-8, 9.2

## Global Constraints

- Rosa: `R['slot']` (3/8/8/6), budget `R['budget']` (500), 1 credito di riserva per ogni slot vuoto.
- Valore di una rosa = `schiera.valore_atteso(schiera.migliore_semplice(rosa, R)) * giornate`; rosa che non riempie alcun modulo → valore `0.0`.
- Prezzo usato dall'ottimizzatore = mediana di `mercato_asta.prevedi`.
- Vincoli di default (`lega.json` → `asta`): `portieri_max: 10` (crediti in tutto), fascia media `(25, 49)` con `fascia_media_max: 2`, eccezioni per chi ha scouting ≥ 0,3 (`scouting_ok`, insieme di chiavi; vuoto finché il piano C non esiste).
- Ordine di chiamata default `['P', 'D', 'C', 'A']`; budget di reparto = Σ mediane previste dei bersagli × 1,10.
- Etichette: **affare** tetto > q75, **da giocare** q25 ≤ tetto ≤ q75, **lascia** tetto < q25, **fuori piano** oltre i primi 40 per reparto per valore.
- Tetto per bisezione fra 1 e il budget disponibile, tolleranza 1 credito.
- Ottimizzatore deterministico a parità di `seme`; `partenze=5`.
- Il rigioco dell'asta legge solo listone di agosto e `prezzi_lega`: mai voti o tabelle 2026/27.

## Review Focus

- Budget insufficiente a riempire la rosa coi prezzi previsti (es. live a fine asta con 10 crediti e 6 slot) → l'ottimizzatore prende giocatori da 1 credito, non fallisce.
- Giocatore già comprato da altri o già mio durante il live → mai proposto come bersaglio / sempre tenuto.
- Reparto senza abbastanza giocatori disponibili dopo le esclusioni → messaggio esplicito, niente rosa incompleta presentata come piano.
- Tetto di un giocatore irrilevante (p = 0) → 1, non un numero negativo o il budget intero.
- Portieri già al limite `portieri_max` → il tetto di un altro portiere non supera il credito residuo del vincolo.

---

### Task 1: valore dei giocatori e della rosa

**Files:** Create `piano_asta.py`; Test `tests/qa_asta.py`

**Interfaces:**
- Consumes: `proiezioni.stima(S=None, listone=..., titolari=..., R=..., prossima=False)`, `schiera.migliore_semplice`, `schiera.valore_atteso`.
- Produces: `valori(listone: list[dict], R, titolari=None) -> dict[str, dict]` (stime per chiave, senza `_ruoli`); `valore_rosa(chiavi: list[str], E: dict, R, giornate: int = 1) -> float`.

- [ ] **Step 1: aiuti di test** in cima a `tests/qa_asta.py` (li usano i Task 1-6):

```python
def G(k, ruolo, mu, p=1.0, prezzo=1.0):
    return {'k': k, 'nome': k, 'ruolo': ruolo, 'mu': mu, 'mv': min(mu, 6.3), 'p': p,
            'sd': 1.0, 'sd_v': 0.5, 'stato': '', 'prezzo': prezzo}

def rosa_sintetica():   # 3/8/8/6 decrescenti + extra 'XA0'..'XA7' (attaccanti liberi, mu 5.0..8.5)
    r = [G(f'P{i}', 'P', 5.5 - .5 * i) for i in range(3)] + [G(f'D{i}', 'D', 6.6 - .2 * i) for i in range(8)]
    r += [G(f'C{i}', 'C', 7.0 - .2 * i) for i in range(8)] + [G(f'A{i}', 'A', 7.5 - .3 * i) for i in range(6)]
    return r + [G(f'XA{i}', 'A', 5.0 + .5 * i) for i in range(8)]

def pool_piccolo():     # 3P 4D 4C 3A, prezzi 1..30, un solo attaccante nettamente migliore ('A0')
    P = [G(f'P{i}', 'P', 5.0 + .3 * i, prezzo=1 + 4 * i) for i in range(3)]
    D = [G(f'D{i}', 'D', 5.8 + .3 * i, prezzo=1 + 3 * i) for i in range(4)]
    C = [G(f'C{i}', 'C', 6.0 + .4 * i, prezzo=1 + 5 * i) for i in range(4)]
    A = [G('A0', 'A', 8.5, prezzo=20), G('A1', 'A', 6.2, prezzo=4), G('A2', 'A', 6.0, prezzo=1)]
    return {g['k']: g for g in P + D + C + A}

def combinazioni(E, slot):   # tutte le rose con esattamente slot[r] giocatori per ruolo
    per = {r: [k for k in E if E[k]['ruolo'] == r] for r in slot}
    return (sum(c, ()) for c in itertools.product(*(itertools.combinations(per[r], slot[r]) for r in 'PDCA')))

def forchette_finte(E, k=1.0):   # q25/q50/q75 = prezzo * (0.8, 1, 1.25) * k
    return {x: (g['prezzo'] * .8 * k, g['prezzo'] * k, g['prezzo'] * 1.25 * k) for x, g in E.items()}
```

- [ ] **Step 2: test**

```python
R = regole.carica_lega(None)
E = {g['k']: g for g in rosa_sintetica()}
base = [k for k in E if not k.startswith('X')]    # la rosa completa
v0 = piano_asta.valore_rosa(base, E, R)
migliore = max((k for k in E if k.startswith('XA')), key=lambda k: E[k]['mu'])
peggiore_a = min((k for k in base if E[k]['ruolo'] == 'A'), key=lambda k: E[k]['mu'])
v1 = piano_asta.valore_rosa([k for k in base if k != peggiore_a] + [migliore], E, R)
t('sostituire il peggior attaccante con uno migliore alza il valore', v1 > v0)
t('rosa senza portieri: valore 0', piano_asta.valore_rosa([k for k in base if E[k]['ruolo'] != 'P'], E, R) == 0.0)
t('il valore scala con le giornate', abs(piano_asta.valore_rosa(base, E, R, 33) - 33 * v0) < 1e-6)
```

- [ ] **Step 3: run → fallisce**
- [ ] **Step 4: implementa `valori` e `valore_rosa`**
- [ ] **Step 5: run → ok**
- [ ] **Step 6: commit** `"piano_asta: valore di giocatori e rosa dalle stime"`

### Task 2: ottimizzatore della rosa

**Files:** Modify `piano_asta.py`; Test `tests/qa_asta.py`

**Interfaces:**
- Produces: `ottimizza(E: dict, prezzi: dict[str, float], R, budget: float, slot: dict[str, int], vincoli: dict, fissati=(), esclusi=(), seme: int = 1, partenze: int = 5) -> dict` con `{'rosa': list[str], 'costo': float, 'valore': float}`; `rispetta(rosa, prezzi, E, vincoli) -> bool`.

- [ ] **Step 1: test** (istanza minuscola risolvibile a forza bruta)

```python
Rm = regole.carica_lega(None, {'moduli': ['1-1-1'], 'modificatore': {'attivo': False}, 'panchina': 0})
slot = {'P': 1, 'D': 2, 'C': 2, 'A': 1}
E4 = pool_piccolo()
prezzi = {k: g['prezzo'] for k, g in E4.items()}
vinc = {'portieri_max': 99, 'fascia_media': (25, 49), 'fascia_media_max': 99, 'scouting_ok': set()}
ris = piano_asta.ottimizza(E4, prezzi, Rm, 60, slot, vinc)
bruta = max((c for c in combinazioni(E4, slot) if sum(prezzi[k] for k in c) <= 60),
            key=lambda c: piano_asta.valore_rosa(list(c), E4, Rm))
t('su istanza piccola trova l ottimo della forza bruta',
  abs(ris['valore'] - piano_asta.valore_rosa(list(bruta), E4, Rm)) < 1e-9)
t('rispetta budget e slot', ris['costo'] <= 60 and sorted(E4[k]['ruolo'] for k in ris['rosa']) == sorted('PDDCCA'))
t('deterministico a parita di seme', piano_asta.ottimizza(E4, prezzi, Rm, 60, slot, vinc, seme=4) ==
  piano_asta.ottimizza(E4, prezzi, Rm, 60, slot, vinc, seme=4))
vp = dict(vinc, portieri_max=2)
t('vincolo portieri rispettato', sum(prezzi[k] for k in piano_asta.ottimizza(E4, prezzi, Rm, 60, slot, vp)['rosa']
                                     if E4[k]['ruolo'] == 'P') <= 2)
fis = [next(k for k in E4 if E4[k]['ruolo'] == 'D')]
t('i fissati restano, gli esclusi non entrano',
  set(fis) <= set(piano_asta.ottimizza(E4, prezzi, Rm, 60, slot, vinc, fissati=fis)['rosa']) and
  not set(fis) & set(piano_asta.ottimizza(E4, prezzi, Rm, 60, slot, vinc, esclusi=fis)['rosa']))
t('budget minimo: 6 slot con 6 crediti -> tutti da 1 credito se esistono, nessuna eccezione',
  piano_asta.ottimizza(E4, {k: 1.0 for k in E4}, Rm, 6, slot, vinc)['costo'] == 6)
```

- [ ] **Step 2: run → fallisce**
- [ ] **Step 3: implementa `ottimizza`**: partenze = la rosa più economica valida, la più forte che entra nel budget (greedy per `mu*p`), più `partenze-2` casuali valide (`random.Random(seme)`); per ciascuna, scambi 1-per-1 dello stesso ruolo che aumentano il valore rispettando budget e vincoli, finché non ce ne sono; si tiene la migliore. Se nessuna rosa valida esiste → `ValueError` con il reparto che non si riempie.
- [ ] **Step 4: run → ok**
- [ ] **Step 5: commit** `"piano_asta: ottimizzatore della rosa a scambi con vincoli"`

### Task 3: tetto per bisezione

**Files:** Modify `piano_asta.py`; Test `tests/qa_asta.py`

**Interfaces:**
- Consumes: `ottimizza`.
- Produces: `tetto(k: str, E, prezzi, R, budget, slot, vincoli, **kw) -> float` = massimo prezzo `p` (intero) tale che `ottimizza(... fissati=[k], prezzi={**prezzi, k: p}).valore >= ottimizza(... esclusi=[k]).valore`; `1.0` se nemmeno a 1 conviene.

- [ ] **Step 1: test**

```python
stella = max((k for k in E4 if E4[k]['ruolo'] == 'A'), key=lambda k: E4[k]['mu'])
t('la stella unica ha tetto sopra il suo prezzo previsto', piano_asta.tetto(stella, E4, prezzi, Rm, 60, slot, vinc) > prezzi[stella])
E5 = dict(E4); E5['clone'] = dict(E4[stella], k='clone', mu=E4[stella]['mu'] - 0.5); prezzi5 = dict(prezzi, clone=3.0)
t('con un clone quasi uguale da 3 crediti, il tetto della stella crolla',
  piano_asta.tetto(stella, E5, prezzi5, Rm, 60, slot, vinc) < piano_asta.tetto(stella, E4, prezzi, Rm, 60, slot, vinc))
morto = next(k for k in E4 if E4[k]['ruolo'] == 'C'); E6 = dict(E4); E6[morto] = dict(E4[morto], p=0.0)
t('chi non gioca mai ha tetto 1', piano_asta.tetto(morto, E6, prezzi, Rm, 60, slot, vinc) == 1.0)
t('CONTROPROVA: alzare il fantavoto atteso alza il tetto',
  piano_asta.tetto(stella, {**E4, stella: dict(E4[stella], mu=E4[stella]['mu'] + 2)}, prezzi, Rm, 60, slot, vinc)
  > piano_asta.tetto(stella, E4, prezzi, Rm, 60, slot, vinc))
```

- [ ] **Step 2: run → fallisce**
- [ ] **Step 3: implementa `tetto`** (bisezione su interi in `[1, budget - (slot_totali - 1)]`)
- [ ] **Step 4: run → ok**
- [ ] **Step 5: commit** `"piano_asta: tetto come prezzo di indifferenza"`

### Task 4: il piano per reparto

**Files:** Modify `piano_asta.py`; Test `tests/qa_asta.py`

**Interfaces:**
- Consumes: `ottimizza`, `tetto`. Le forchette arrivano già calcolate (la CLI del Task 7 le ottiene da `mercato_asta.prevedi`): il piano non conosce il modello di mercato.
- Produces: `piano(E, forchette: dict[str, tuple[float, float, float]], R, budget, slot, vincoli, ordine=('P','D','C','A'), candidati=40, fissati=(), esclusi=()) -> dict` (prezzi dell'ottimizzatore = `forchette[k][1]`) con `{'rosa', 'costo', 'valore', 'reparti': {r: {'budget': float, 'bersagli': [riga], 'altri': [riga]}}}`; `riga = {'k', 'nome', 'forchetta': (q25,q50,q75), 'tetto': float|None, 'etichetta': 'affare'|'da giocare'|'lascia'|'fuori piano', 'alternative': [k, k]}`.

- [ ] **Step 1: test**

```python
P_ = piano_asta.piano(E4, forchette_finte(E4), Rm, 60, slot, vinc, candidati=3)
righe = [r for rep in P_['reparti'].values() for r in rep['bersagli'] + rep['altri']]
t('budget di reparto = somma mediane dei bersagli x 1.10',
  all(abs(rep['budget'] - 1.10 * sum(r['forchetta'][1] for r in rep['bersagli'])) < 1e-6 for rep in P_['reparti'].values()))
t('etichette secondo il tetto e la forchetta', all(
  (r['etichetta'] == 'affare') == (r['tetto'] is not None and r['tetto'] > r['forchetta'][2]) for r in righe))
t('fuori piano = senza tetto', all((r['tetto'] is None) == (r['etichetta'] == 'fuori piano') for r in righe))
t('alternative dello stesso ruolo e fuori dalla rosa del piano',
  all(E4[a]['ruolo'] == E4[r['k']]['ruolo'] and a not in P_['rosa'] for r in righe for a in r['alternative']))
```

- [ ] **Step 2: run → fallisce**
- [ ] **Step 3: implementa `piano`**: rosa = `ottimizza`; per ogni reparto, bersagli = giocatori del reparto nella rosa, altri = i successivi per valore fino a `candidati`; tetto per bersagli e altri; alternative = i 2 migliori per `mu*p/prezzo` dello stesso ruolo fuori rosa.
- [ ] **Step 4: run → ok**
- [ ] **Step 5: commit** `"piano_asta: piano per reparto con etichette e alternative"`

### Task 5: live

**Files:** Modify `piano_asta.py`; Test `tests/qa_asta.py`

**Interfaces:**
- Consumes: stato JSON di `fanta.Asta` (`venduti: [{nome, prezzo, mio}]`, `mio_budget`, `miei`).
- Produces: `termometro(venduti, forchette, E) -> float` = Σ pagato / Σ mediana prevista dei venduti, tagliato in `[0.5, 2.0]`, `1.0` senza vendite; `ricalcola(stato: dict, E, forchette, R, vincoli, **kw) -> dict` (stesso formato di `piano`) con miei = `fissati`, venduti ad altri = `esclusi`, budget = `mio_budget`, slot = slot residui, forchette dei rimasti × termometro.

- [ ] **Step 1: test**

```python
stato = {'venduti': [{'nome': E4[stella]['nome'], 'prezzo': 2 * prezzi[stella], 'mio': False}], 'mio_budget': 60, 'miei': []}
t('termometro: pagato il doppio del previsto -> 2.0', abs(piano_asta.termometro(stato['venduti'], forchette_finte(E4), E4) - 2.0) < 1e-9)
t('termometro senza vendite = 1', piano_asta.termometro([], forchette_finte(E4), E4) == 1.0)
Pl = piano_asta.ricalcola(stato, E4, forchette_finte(E4), Rm, vinc)
t('venduto ad altri: mai nel piano', stella not in Pl['rosa'])
mio = {'venduti': [{'nome': E4[stella]['nome'], 'prezzo': 10, 'mio': True}], 'mio_budget': 50,
       'miei': [{'nome': E4[stella]['nome'], 'prezzo': 10}]}
t('comprato da me: sempre nel piano, budget scalato', stella in piano_asta.ricalcola(mio, E4, forchette_finte(E4), Rm, vinc)['rosa'])
```

- [ ] **Step 2: run → fallisce**
- [ ] **Step 3: implementa `termometro` e `ricalcola`** (chiavi dei nomi con `nomi.giocatore`)
- [ ] **Step 4: run → ok**
- [ ] **Step 5: commit** `"piano_asta: ricalcolo live dallo stato dell'asta"`

### Task 6: rigiocare l'asta del 05/09

**Files:** Modify `piano_asta.py`; Test `tests/qa_asta.py`

**Interfaces:**
- Consumes: `piano`, formato di `mercato_asta.carica`.
- Produces: `rigioca(acquisti: list[dict], E_agosto: dict, forchette, R, vincoli, ordine=('P','D','C','A')) -> dict` con `{'rosa': list[str], 'speso': float, 'log': [str]}`. Firma senza voti/tabelle 2026/27: la funzione non può leggerli.

- [ ] **Step 1: test**

```python
acq = [dict(k=k, nome=E4[k]['nome'], ruolo=E4[k]['ruolo'], squadra='', fvm=10.0, quota=None,
            pagato=prezzi[k] if i % 2 else None, fantasquadra='Altri' if i % 2 else None) for i, k in enumerate(E4)]
rg = piano_asta.rigioca(acq, E4, forchette_finte(E4), Rm, vinc)
t('rosa completa e budget mai negativo', len(rg['rosa']) == 6 and rg['speso'] <= Rm['budget'])
t('un bersaglio comprato da altri si prende solo se tetto >= pagato + 1 (lo dice il log)',
  all(('preso' in l) or ('perso' in l) or ('libero' in l) for l in rg['log']))
t('un giocatore mai comprato si prende a 1', all(l.endswith(' 1') for l in rg['log'] if 'libero' in l))
```

- [ ] **Step 2: run → fallisce**
- [ ] **Step 3: implementa `rigioca`**: per reparto nell'ordine, per ogni bersaglio del piano ricalcolato: se nessuno lo ha comprato → preso a 1; se `tetto >= pagato + 1` → preso a `pagato + 1`; altrimenti perso e il reparto si ricalcola con lui escluso. Log `"preso Tizio 23"`, `"perso Caio (pagato 40, tetto 31)"`, `"libero Sempronio 1"`.
- [ ] **Step 4: run → ok**
- [ ] **Step 5: commit** `"piano_asta: rigioco dell'asta con i soli dati di agosto"`

### Task 7: CLI, `socio.py asta`, dati veri e verdetto

**Files:** Modify `piano_asta.py` (`main()`), `socio.py` (`asta` → piano; `asta --live asta.json`; `asta --rigioca`), `lega.json` (sezione `asta`: `ordine`, `portieri_max`, `fascia_media`, `fascia_media_max`), `README.md`, `docs/studio-asta-2026-27.md`; Test `tests/qa_asta.py`

- [ ] **Step 1: test di fumo** con `subprocess` su una lega sintetica (listone + prezzi generati nel test): `socio.py asta` → codice 0, output con i 4 reparti nell'ordine e le etichette; `asta --rigioca` → codice 0 e riga di confronto; file mancanti → messaggio, codice ≠ 0, niente `Traceback`.
- [ ] **Step 2: run → fallisce**
- [ ] **Step 3: implementa `main()` e i sottocomandi**
- [ ] **Step 4: run → ok**
- [ ] **Step 5: sui dati veri**: `python socio.py asta --rigioca`; confronta la rosa del piano con la vera AL DOMORO e con le altre 9 su forza (`socio.py lega` ricalcolato sulla tabella di oggi), FM delle giornate giocate e FVMp di oggi. Scrivi il verdetto in `docs/studio-asta-2026-27.md` (sezione "Rigioco"), **anche se negativo**.
- [ ] **Step 6: commit** `"socio asta: piano d'asta, live e rigioco sui dati veri"`
