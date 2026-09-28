# Prezzo di mercato della lega — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** per ogni giocatore del listone, la forchetta 25-50-75% del prezzo che la lega pagherà e la probabilità che venga comprato, con le "manie" della lega e una validazione leave-one-out che sceglie il modello.

**Architecture:** un modulo puro `mercato_asta.py` (nessun I/O fuori da `carica`), che unisce `prezzi_lega_*.csv` (Pagato, FVM al momento dell'asta) al listone di agosto; stima per cella (ruolo × fascia di FVM) un modello lineare o logaritmico scelto dall'errore leave-one-out, con ripiego sulla baseline lineare di lega.

**Tech Stack:** Python 3 standard library (`csv`, `math`, `statistics`), niente dipendenze nuove. Test nello stile di `tests/qa_fanta.py` (funzione `t()`, controprove).

**Spec:** `docs/superpowers/specs/2026-09-28-piano-asta-design.md` §§ 2-3, 9.1

## Global Constraints

- Fasce di FVM: `< 20`, `20-49`, `50-99`, `>= 100` (limiti inferiori `FASCE = (0, 20, 50, 100)`).
- Candidati per cella: `lineare` (`pagato = k·FVM`, k = Σpagato/ΣFVM della cella) e `log` (`log pagato = a + b·log FVM`, minimi quadrati); vince l'errore medio assoluto leave-one-out minore.
- Cella con meno di 5 acquisti, o in cui nessun candidato batte la **baseline** (lineare su tutta la lega, stesso leave-one-out): si usa la baseline.
- Forchetta: quantili 25/50/75% dei **rapporti** `pagato / previsto_loo` della cella, moltiplicati per il previsto.
- Nessun prezzo previsto sotto 1 credito.
- File di dati di terzi (`prezzi_lega_*.csv`, `listone_completo.csv`) mai nel repo; i test usano dati sintetici.
- Output a terminale in ASCII (convenzione del repo per le console Windows).

## Review Focus

- Giocatore con FVM 0 o mancante nel listone → escluso dal modello e dichiarato, non `log(0)`.
- Nome presente in `prezzi_lega` ma non nel listone → errore esplicito con i nomi, non join silenzioso.
- Cella vuota per un ruolo (es. nessun portiere con FVM ≥ 100) → la previsione usa la baseline, non va in eccezione.
- Leave-one-out che include il giocatore stesso (errore di implementazione più probabile) → coperto dalla controprova in Task 2.
- Prezzi pagati anomali (1 credito per FVM 160, Woltemade) → restano nel campione: sono il fenomeno da misurare, non outlier da togliere.

---

### Task 1: carica e unisci

**Files:**
- Create: `mercato_asta.py`
- Test: `tests/qa_asta.py`

**Interfaces:**
- Produces: `carica(prezzi_path: str, listone_path: str | None) -> list[dict]`; ogni dict ha `k` (chiave `nomi.giocatore`), `nome`, `ruolo`, `squadra`, `fvm: float`, `quota: float | None`, `pagato: float | None` (None = non comprato), `fantasquadra: str | None`. Senza listone: solo i comprati, con `squadra=''`.

- [ ] **Step 1: test (in `tests/qa_asta.py`, stesso scheletro `t()` di `tests/qa_socio.py`)**

```python
p = scrivi_csv(os.path.join(tmp, 'prezzi.csv'), [['FantaSquadra', 'Nome', 'Ruolo', 'Pagato', 'FVM'],
    ['X', 'Alfa A.', 'A', '40', '100'], ['Y', 'Beta B.', 'D', '10', '20']])
l = scrivi_csv(os.path.join(tmp, 'listone.csv'), [['Nome', 'Ruolo', 'Squadra', 'Quotazione', 'FVM'],
    ['Alfa A.', 'A', 'INT', '20', '100'], ['Beta B.', 'D', 'MIL', '8', '20'], ['Gamma G.', 'C', 'ROM', '3', '5']])
A = mercato_asta.carica(p, l)
t('unisce comprati e non comprati', len(A) == 3 and sum(1 for a in A if a['pagato'] is None) == 1)
al = next(a for a in A if a['nome'] == 'Alfa A.')
t('i comprati portano prezzo, squadra e fantasquadra',
  (al['pagato'], al['squadra'], al['fantasquadra'], al['fvm']) == (40.0, 'INT', 'X', 100.0))
bad = scrivi_csv(os.path.join(tmp, 'prezzi_bad.csv'), [['FantaSquadra', 'Nome', 'Ruolo', 'Pagato', 'FVM'],
    ['X', 'Nessuno N.', 'A', '5', '10']])
try:
    mercato_asta.carica(bad, l); ok = False
except fanta.DatoMancante as e:
    ok = 'Nessuno N.' in str(e)
t('CONTROPROVA: un comprato assente dal listone ferma tutto e lo nomina', ok)
t('senza listone: solo i comprati', len(mercato_asta.carica(p, None)) == 2)
```

- [ ] **Step 2: `python tests/qa_asta.py` → fallisce con `ModuleNotFoundError: mercato_asta`**
- [ ] **Step 3: implementa `carica`** leggendo i file con `voti._righe` (gestisce `;`/`,` e titoli) e `fanta._num`; righe con FVM ≤ 0 escluse e contate in un attributo di modulo `ESCLUSI` (lista di nomi) che la CLI stampa.
- [ ] **Step 4: `python tests/qa_asta.py` → tutti ok**
- [ ] **Step 5: commit** `git add mercato_asta.py tests/qa_asta.py && git commit -m "mercato_asta: carica e unisce prezzi d'asta e listone"`

### Task 2: modello per cella con leave-one-out

**Files:** Modify `mercato_asta.py`; Test `tests/qa_asta.py`

**Interfaces:**
- Consumes: output di `carica`.
- Produces: `stima(acquisti: list[dict]) -> dict` (il "modello": per `(ruolo, fascia)` → `{'tipo': 'lineare'|'log'|'baseline', 'param': tuple, 'rapporti': list[float], 'mae': float, 'mae_base': float, 'n': int}` più `'_base': k`); `prevedi(modello, ruolo: str, fvm: float) -> tuple[float, float, float]` (q25, q50, q75, ciascuno ≥ 1); `fascia(fvm: float) -> int` (indice 0-3).

- [ ] **Step 1: test**

```python
rng = random.Random(3)
lin = [{'k': f'a{i}', 'nome': f'a{i}', 'ruolo': 'A', 'squadra': '', 'fvm': f, 'quota': None,
        'pagato': 0.6 * f * rng.uniform(0.9, 1.1), 'fantasquadra': 'X'} for i, f in enumerate(range(20, 200, 6))]
M = mercato_asta.stima(lin)
q25, q50, q75 = mercato_asta.prevedi(M, 'A', 100)
t('dati proporzionali: previsto vicino a 0.6*FVM', abs(q50 - 60) < 6, f'{q50:.1f}')
t('forchetta ordinata e mai sotto 1', 1 <= q25 <= q50 <= q75)
logd = [dict(x, k=f'l{i}', ruolo='C', fvm=f, pagato=max(1.0, 0.02 * f ** 1.8)) for i, (x, f) in
        enumerate(zip(lin, range(5, 50)))]
M2 = mercato_asta.stima(lin + logd)
t('dati convessi sotto FVM 50: vince il logaritmico', M2[('C', 1)]['tipo'] == 'log', str(M2[('C', 1)]['tipo']))
t('cella con meno di 5 acquisti: baseline', mercato_asta.stima(lin[:3])[('A', 1)]['tipo'] == 'baseline')  # FVM 20-32
t('ruolo mai visto: previsione dalla baseline, senza eccezione', mercato_asta.prevedi(M, 'P', 50)[1] >= 1)
# CONTROPROVA leave-one-out: cambiare il prezzo di un giocatore non cambia il SUO previsto loo
x = lin[5]
prima = mercato_asta.previsto_loo(lin, x['k'])
dopo = mercato_asta.previsto_loo([dict(y, pagato=999.0) if y['k'] == x['k'] else y for y in lin], x['k'])
t('CONTROPROVA: il previsto leave-one-out di un giocatore ignora il suo stesso prezzo', abs(prima - dopo) < 1e-9)
```

- [ ] **Step 2: run → fallisce (`stima` non esiste)**
- [ ] **Step 3: implementa** `fascia`, `stima`, `prevedi` e `previsto_loo(acquisti, k) -> float` (previsione mediana per `k` stimata senza `k`, col tipo scelto per la sua cella). `stima` calcola per ogni cella l'errore loo dei due candidati e della baseline, sceglie il minore fra i candidati solo se batte la baseline, e salva i rapporti `pagato/previsto_loo` per la forchetta. Solo i comprati entrano nel modello.
- [ ] **Step 4: run → ok**
- [ ] **Step 5: commit** `"mercato_asta: modello per cella scelto dal leave-one-out, forchetta dai residui"`

### Task 3: probabilità d'acquisto e manie della lega

**Files:** Modify `mercato_asta.py`; Test `tests/qa_asta.py`

**Interfaces:**
- Produces: `p_acquisto(acquisti, ruolo: str, fvm: float) -> float` (frequenza dei comprati nella cella con correzione di Laplace `(c+1)/(n+2)`); `manie(acquisti, modello) -> list[dict]` con righe `{'dimensione': 'ruolo'|'squadra'|'fascia', 'valore': str, 'n': int, 'scarto': float}` dove `scarto` = mediana di `pagato/(base·FVM) - 1`; le squadre di Serie A compaiono solo con `n >= 5`.

- [ ] **Step 1: test**

```python
pool = [dict(lin[0], k=f'n{i}', fvm=8.0, pagato=None) for i in range(8)] + \
       [dict(lin[0], k=f'c{i}', fvm=8.0, pagato=1.0) for i in range(2)]
t('probabilita di acquisto con Laplace: 2 comprati su 10 -> 0.25',
  abs(mercato_asta.p_acquisto(pool, 'A', 8.0) - 3 / 12) < 1e-9)
porta = [dict(lin[0], k=f'p{i}', ruolo='P', fvm=50.0, pagato=40.0, squadra='INT') for i in range(6)]
man = {(m['dimensione'], m['valore']): m for m in mercato_asta.manie(lin + porta, mercato_asta.stima(lin + porta))}
t('mania per ruolo: i portieri si pagano sopra la baseline', man[('ruolo', 'P')]['scarto'] > 0.2)
t('squadra con almeno 5 acquisti compare', ('squadra', 'INT') in man)
t('CONTROPROVA: squadra con meno di 5 acquisti non compare', ('squadra', '') not in man or man[('squadra', '')]['n'] >= 5)
```

- [ ] **Step 2: run → fallisce**
- [ ] **Step 3: implementa `p_acquisto` e `manie`**
- [ ] **Step 4: run → ok**
- [ ] **Step 5: commit** `"mercato_asta: probabilita di acquisto e manie della lega"`

### Task 4: CLI, comando `socio.py asta --mercato`, dati veri

**Files:** Modify `mercato_asta.py` (aggiungi `main()`), `socio.py` (sottocomando `asta` con flag `--mercato`), `lega.json` (`file.prezzi`: `prezzi_lega_2026-27.csv`), `docs/studio-asta-2026-27.md`; Test `tests/qa_asta.py`

**Interfaces:**
- Consumes: `carica`, `stima`, `prevedi`, `p_acquisto`, `manie`.
- Produces: `python mercato_asta.py --prezzi F --listone L [--ruolo R] [--top N]` che stampa: errore loo modello vs baseline per cella, manie, e per i primi N giocatori del listone per FVM la forchetta e P(acquisto).

- [ ] **Step 1: test di fumo**: `subprocess` su `mercato_asta.py` con i file sintetici del Task 1 → codice 0, output con `baseline` e `forchetta`; senza `--prezzi` esistente → messaggio chiaro, codice ≠ 0, niente `Traceback`.
- [ ] **Step 2: run → fallisce**
- [ ] **Step 3: implementa `main()` e il sottocomando in `socio.py`** (legge i percorsi da `lega.json` → `file.prezzi`, `file.listone`).
- [ ] **Step 4: run → ok; poi sui dati veri** `python socio.py asta --mercato` e verifica a mano che l'errore loo per fascia ≥ 100 non superi la baseline (esplorazione del 28/09: baseline 20,5 crediti).
- [ ] **Step 5: scrivi i numeri veri** (errore per cella, manie) nella sezione "Prezzo di mercato" di `docs/studio-asta-2026-27.md`
- [ ] **Step 6: commit** `"asta --mercato: prezzo previsto della lega sui dati veri"`
