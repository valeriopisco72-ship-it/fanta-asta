# Scouting qualitativo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** schede qualitative per giocatore (8 KPI con prova, fonte e data) che correggono in modo limitato le stime, un imbuto che sceglie chi schedare fra i liberi, la lista dei gioielli per l'asta di gennaio e la verifica per KPI senza futuro.

**Architecture:** `scouting.py` è puro (valida, indice, correzione, segnali, candidati, gioielli); `socio.py` carica `scouting/` e applica la correzione alle stime; `verifica.py` misura ogni KPI solo sulle giornate successive alla data della scheda; una skill di progetto dice a Claude come compilare le schede.

**Tech Stack:** Python 3 standard library, `json`; moduli del repo `nomi`, `proiezioni`, `mercato`, `piano_asta` (per il prezzo massimo, piano B). Test in `tests/qa_scouting.py`.

**Spec:** `docs/superpowers/specs/2026-09-28-scouting-qualitativo-design.md`

## Global Constraints

- KPI e pesi iniziali: `spazio 1.0, ruolo_tattico 0.8, palle_inattive 0.6, contesto 0.6, allenatore 0.5, fisico 0.5, traiettoria 0.4, carattere 0.3`.
- Voto intero in `[-2, 2]`; `prova` e `fonte` non vuote; `data` ISO; `giornata` (intero, ultima giornata giocata alla data della scheda) facoltativa ma richiesta dalla verifica; KPI sconosciuto = scheda invalida.
- Scadenza: 60 giorni dalla data della scheda.
- Indice = Σ peso·voto / (2·Σ tutti i pesi); confidenza = Σ pesi dei KPI validi / Σ tutti i pesi.
- Correzione: `p += 0.15 * spazio / 2` tagliato a `[0.02, 0.98]`; `mu += 0.6 * indice_senza_spazio` (indice ricalcolato escludendo `spazio` da numeratore e denominatore), `MAX_MU = 0.6`, `MAX_P = 0.15`.
- Prezzo massimo per gennaio: somma zero `1 + (B - S) * guadagno_i / Σ guadagno` sui primi `S` gioielli, poi tetti **25** (tutti) e **5** (portieri).
- Segnale strutturale misurato (lega 2026/27): attaccante di neopromossa (40% di colpi fra i pagati ≤ 5 contro 12%); difensori e portieri economici 0 su 41.

## Review Focus

- File JSON malformato in `scouting/` → scartato e nominato, le altre schede restano valide.
- Due schede per lo stesso giocatore → vale la più recente, e lo si dice.
- Scheda di un giocatore non presente nelle stime → ignorata e dichiarata, niente chiave nuova inventata.
- Nome scritto diverso dal listone ("N. Gonzalez") → trovato con `nomi.cerca` se unico, altrimenti dichiarato ambiguo.
- Verifica con zero giornate dopo la data della scheda → la riga del KPI dice "nessun dato ancora", non 0.

---

### Task 1: scheda, validazione, indice

**Files:** Create `scouting.py`, `tests/qa_scouting.py` (stesso scheletro `t()`; la bozza è in `scratchpad/bozza_test_scouting.py` della sessione del 28/09 — i test sotto ne sono la versione definitiva)

**Interfaces:**
- Produces: `KPI: dict[str, tuple[float, str]]` (peso, domanda); `valida(scheda: dict) -> list[str]` (errori, vuota = valida); `indice(scheda: dict, escludi=()) -> tuple[float, float]` (indice, confidenza; i KPI non validi non contano); `carica(cartella: str) -> tuple[dict[str, dict], list[str]]` (schede per chiave `nomi.giocatore`, errori leggibili).

- [ ] **Step 1: test** — quelli della bozza (validità, fonte vuota, voto fuori scala, KPI sconosciuto, indice ±, confidenza crescente, KPI senza fonte fuori dall'indice, `carica` che scarta e nomina) più:

```python
json.dump({'nome': 'Doppio D.', 'data': '2026-09-01', 'kpi': {}}, open(os.path.join(sdir, 'd1.json'), 'w'))
json.dump(scheda('Doppio D.', spazio=2) | {'data': '2026-09-20'}, open(os.path.join(sdir, 'd2.json'), 'w'))
open(os.path.join(sdir, 'rotto.json'), 'w').write('{non json')
Sc, err = scouting.carica(sdir)
t('due schede dello stesso giocatore: vale la piu recente, e lo si dice',
  Sc[nomi.giocatore('Doppio D.')]['data'] == '2026-09-20' and any('Doppio' in e for e in err))
t('JSON rotto: scartato e nominato, le altre restano', any('rotto.json' in e for e in err) and Sc)
```

- [ ] **Step 2: `python tests/qa_scouting.py` → fallisce (`ModuleNotFoundError`)**
- [ ] **Step 3: implementa `KPI`, `valida`, `indice`, `carica`**
- [ ] **Step 4: run → ok**
- [ ] **Step 5: commit** `"scouting: schede con 8 KPI, validazione e indice"`

### Task 2: correzione delle stime e segnali strutturali

**Files:** Modify `scouting.py`, `socio.py`, `lega.json` (`neopromosse: ["Monza", "Frosinone", "Venezia"]`); Test `tests/qa_scouting.py`

**Interfaces:**
- Produces: `applica(E: dict, schede: dict, oggi: str) -> dict` (copia; `fonte` + `" + scouting (AAAA-MM-GG)"`; schede scadute non applicate); `segnali(g: dict, neopromosse: set[str]) -> list[str]`; in `socio.Contesto`: `self.schede`, applicazione a `E_ora` ed `E_base`, avvisi per schede scartate, scadute o senza giocatore.

- [ ] **Step 1: test** — quelli della bozza (alza/abbassa, limiti `MAX_MU`/`MAX_P`, fonte dichiarata, originali intatti, scadenza 60 giorni, segnale neopromossa, controprova difensore) più:

```python
Eu = scouting.applica(base, {nomi.giocatore('Fantasma F.'): scheda('Fantasma F.', spazio=2)}, oggi='2026-09-30')
t('scheda di un giocatore assente: ignorata, nessuna chiave inventata', set(Eu) == set(base))
C = socio.Contesto(lega_con_scouting)        # lega finta di esempio.py + cartella scouting/ con 1 scheda
t('socio applica lo scouting e lo dichiara', any('scouting' in C.E_base[k].get('fonte', '') for k in C.E_base
                                                 if not k.startswith('_')))
```

- [ ] **Step 2: run → fallisce**
- [ ] **Step 3: implementa `applica`, `segnali`, l'aggancio in `socio.Contesto`**
- [ ] **Step 4: run → ok, e `python tests/qa_socio.py` resta verde**
- [ ] **Step 5: commit** `"scouting: correzione limitata delle stime e segnali strutturali"`

### Task 3: imbuto dei candidati e gioielli con prezzo massimo

**Files:** Modify `scouting.py`, `socio.py` (`scouting candidati`, `scouting gioielli --budget B --slot S`); Test `tests/qa_scouting.py`

**Interfaces:**
- Consumes: listone (`fanta.carica`), `rose.csv` (`mercato.carica_rose`), `mercato.svincolati`.
- Produces: `candidati(listone: list[dict], occupati: set[str], neopromosse: set[str], n: int = 30) -> list[dict]` (ordinati per punteggio di segnali, ognuno con la lista `segnali`); `gioielli(liberi_stimati: list[dict], guadagni: dict[str, float], budget: float, slot: int) -> list[dict]` con `prezzo_max`.

- [ ] **Step 1: test**

```python
lst = [{'nome': 'Punta N.', 'ruolo': 'A', 'squadra': 'MON', 'quota': 3}, {'nome': 'Terzino N.', 'ruolo': 'D', 'squadra': 'MON', 'quota': 3},
       {'nome': 'Punta V.', 'ruolo': 'A', 'squadra': 'INT', 'quota': 3}, {'nome': 'Preso P.', 'ruolo': 'A', 'squadra': 'MON', 'quota': 3}]
cand = scouting.candidati(lst, occupati={nomi.giocatore('Preso P.')}, neopromosse={'Monza'})
t('i gia in rosa non sono candidati', 'Preso P.' not in [c['nome'] for c in cand])
t('attaccante di neopromossa davanti a tutti', cand[0]['nome'] == 'Punta N.' and cand[0]['segnali'])
gi = scouting.gioielli([{'k': 'a', 'ruolo': 'A'}, {'k': 'b', 'ruolo': 'C'}, {'k': 'p', 'ruolo': 'P'}],
                       {'a': 30.0, 'b': 10.0, 'p': 20.0}, budget=100, slot=3)
# ordine per guadagno: a (1+97*30/60 = 49.5 -> 25), p (33.3 -> 5, portiere), b (1+97*10/60 = 17.2)
t('tetto 25 per tutti, 5 per i portieri', [g['prezzo_max'] for g in gi] == [25, 5, 1 + 97 * 10 / 60])
t('crediti tagliati dai tetti dichiarati', sum(g['prezzo_max'] for g in gi) < 100)
```

- [ ] **Step 2: run → fallisce**
- [ ] **Step 3: implementa `candidati`, `gioielli` e i due sottocomandi** (`gioielli` ordina per guadagno decrescente; i guadagni vengono da `mercato.svincolati` sulle stime corrette dallo scouting, orizzonte fino alla 38ª)
- [ ] **Step 4: run → ok**
- [ ] **Step 5: sui dati veri**: `python socio.py scouting candidati` → la lista dei 30 da schedare, salvata in `docs/scouting-candidati-2026-09.md`
- [ ] **Step 6: commit** `"scouting: imbuto dei candidati e gioielli con prezzo massimo"`

### Task 4: verifica per KPI senza futuro

**Files:** Modify `verifica.py`, `socio.py` (`verifica --scouting`); Test `tests/qa_scouting.py`

**Interfaces:**
- Consumes: `voti.stagione`, schede.
- Produces: `verifica_kpi(schede: dict, records: list[dict], stime_numeriche: dict) -> list[dict]` con righe `{'kpi', 'n_alti', 'n_bassi', 'scarto': float | None}` dove lo scarto = media di (fantavoto − stima numerica) dei giocatori con voto ≥ 1 meno quella dei giocatori con voto ≤ −1, **solo sulle giornate con data successiva alla scheda**.

- [ ] **Step 1: test**

```python
def rec_(g, nome, fv):
    return {'giornata': g, 'nome': nome, 'ruolo': 'A', 'squadra': 'X', 'voto': 6.0, 'fv': fv,
            'gf': 0, 'gs': 0, 'rp': 0, 'rs': 0, 'rf': 0, 'au': 0, 'amm': 0, 'esp': 0, 'ass': 0}
stime_uguali = {nomi.giocatore(n): {'mu': 6.5} for n in ('Alto A.', 'Basso B.')}
rec = [rec_(g, 'Alto A.', 8.0) for g in range(1, 6)] + [rec_(g, 'Basso B.', 5.0) for g in range(1, 6)]
sch = {nomi.giocatore('Alto A.'): scheda('Alto A.', spazio=2) | {'data': '2026-09-10', 'giornata': 3},
       nomi.giocatore('Basso B.'): scheda('Basso B.', spazio=-2) | {'data': '2026-09-10', 'giornata': 3}}
V = {r['kpi']: r for r in verifica.verifica_kpi(sch, rec, stime_uguali)}
t('KPI predittivo: scarto positivo', V['spazio']['scarto'] > 2)
fut = [dict(r, fv=r['fv'] + (50 if r['giornata'] <= 3 else 0)) for r in rec]
t('CONTROPROVA: le giornate fino a quella della scheda non contano',
  V['spazio']['scarto'] == {r['kpi']: r for r in verifica.verifica_kpi(sch, fut, stime_uguali)}['spazio']['scarto'])
t('KPI senza casi: nessun dato, non zero', V['carattere']['scarto'] is None)
```

(La scheda porta anche `giornata`: l'ultima giornata giocata alla data della scheda; è il confine anti-futuro.)

- [ ] **Step 2: run → fallisce**
- [ ] **Step 3: implementa `verifica_kpi` e il flag**
- [ ] **Step 4: run → ok**
- [ ] **Step 5: commit** `"verifica: misura per KPI dello scouting, senza futuro"`

### Task 5: la skill di progetto per compilare le schede

**Files:** Create `.claude/skills/scouting/SKILL.md`

- [ ] **Step 1: leggi `superpowers:writing-skills`** (da `skills/writing-skills/SKILL.md` di obra/superpowers) e segui il suo ciclo: scenario di pressione prima (compilare una scheda per "Varela G." senza istruzioni e annotare dove si inventa una prova o si vota il carattere a sensazione), poi la skill che chiude quei buchi.
- [ ] **Step 2: scrivi la skill** con: quando usarla (schedare un candidato), i KPI e le domande da `scouting.KPI`, le ricerche da fare per ciascuno (probabili formazioni, conferenze stampa, rigoristi designati, infortuni, dichiarazioni), le fonti ammesse e quelle no, la regola "niente link = KPI vuoto", il formato JSON e il comando per validarlo (`python scouting.py --valida scouting/<file>.json`, da aggiungere alla CLI in questo task).
- [ ] **Step 3: prova la skill** sullo stesso scenario del Step 1 e verifica con `--valida` che la scheda prodotta sia valida e che ogni KPI abbia un link.
- [ ] **Step 4: commit** `"skill di progetto: come compilare una scheda di scouting"`
