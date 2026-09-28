# -*- coding: utf-8 -*-
"""piano_asta - la rosa da costruire, e il prezzo massimo vero di ogni giocatore.

Due numeri per ogni giocatore, e un piano:

- **forchetta di mercato** (da `mercato_asta`): quanto lo paghera' la tua lega;
- **tetto**: il prezzo oltre il quale la rosa migliore la fai SENZA di lui. Non
  e' "quanto vale in assoluto": e' il prezzo di indifferenza fra la miglior
  rosa che lo contiene e la miglior rosa che non lo contiene, con lo stesso
  budget e gli stessi vincoli. Tiene conto delle alternative e dei reparti gia'
  coperti;
- **piano**: reparto per reparto nell'ordine di chiamata, i bersagli con
  forchetta, tetto e due alternative, e il budget da non superare.

## Il valore

Il valore di una rosa e' quello del socio: fantapunti attesi a giornata della
formazione migliore con la panchina che entra davvero (`schiera`). La versione
esatta costa 0,84 ms; l'ottimizzatore e il tetto ne chiedono centinaia di
migliaia, quindi usano `valore_rapido`: la stessa matematica per reparto
(Poisson-binomiale sui giocatori ordinati per fantavoto atteso) con la panchina
non limitata. Con panchina lunga coincidono (un test lo impone); con panchina
corta la rapida sopravvaluta un po' le rose profonde. I report usano l'esatta.

Spec: docs/superpowers/specs/2026-09-28-piano-asta-design.md (par. 4-8)
"""
import random

import proiezioni
import regole
import schiera


def valori(listone, R, titolari=None):
    """Stime dei giocatori del listone (senza '_ruoli'), per il piano d'asta."""
    E = proiezioni.stima(S=None, listone=listone, titolari=titolari, R=R, prossima=False)
    return proiezioni.giocatori(E)


def valore_rosa(chiavi, E, R, giornate=1):
    """Fantapunti attesi della formazione migliore (esatto), per le giornate."""
    f = schiera.migliore_semplice([E[k] for k in chiavi if k in E], R)
    return schiera.valore_atteso(f) * giornate if f else 0.0


def _per_ruolo(chiavi, E):
    out = {r: [] for r in regole.RUOLI}
    for k in chiavi:
        if k in E:
            out[E[k]['ruolo']].append(E[k])
    for r in out:
        out[r].sort(key=lambda g: g['mu'], reverse=True)
    return out


def _v_ruolo(lista, n, cache=None):
    """Valore esatto del reparto con n titolari (panchina = tutto il resto)."""
    if cache is None:
        return schiera.valore_ruolo(lista, n)
    chiave = (tuple(g['k'] for g in lista), n)
    if chiave not in cache:
        cache[chiave] = schiera.valore_ruolo(lista, n)
    return cache[chiave]


def valore_rapido(chiavi, E, R, cache=None):
    """Valore di rosa per l'ottimizzatore: max sui moduli della somma per reparto."""
    per = _per_ruolo(chiavi, E)
    migliore = 0.0
    for m in R['moduli']:
        n = regole.modulo(m)
        if any(len(per[r]) < n[r] for r in regole.RUOLI):
            continue
        migliore = max(migliore, sum(_v_ruolo(per[r], n[r], cache) for r in regole.RUOLI))
    return migliore


# ------------------------------------------------------------------ OTTIMIZZATORE

CANDIDATI_RUOLO = 40      # i migliori per mu*p di ogni reparto...
ECONOMICI_RUOLO = 10      # ...piu' i piu' economici, per poter sempre chiudere la rosa
COPPIE_UP, COPPIE_DOWN = 60, 200


def rispetta(rosa, prezzi, E, vincoli):
    """Vincoli dello studio d'asta: crediti totali sui portieri, quanti nella fascia media."""
    if sum(prezzi[k] for k in rosa if E[k]['ruolo'] == 'P') > vincoli.get('portieri_max', float('inf')):
        return False
    lo, hi = vincoli.get('fascia_media', (25, 49))
    ok = vincoli.get('scouting_ok', set())
    medi = sum(1 for k in rosa if lo <= prezzi[k] <= hi and k not in ok)
    return medi <= vincoli.get('fascia_media_max', float('inf'))


def _pool(E, prezzi, slot, fissati, esclusi):
    pool = {}
    for r in regole.RUOLI:
        tutti = [k for k in E if E[k]['ruolo'] == r and k not in esclusi and k in prezzi]
        forti = sorted(tutti, key=lambda k: (-E[k]['mu'] * E[k]['p'], k))[:CANDIDATI_RUOLO]
        economici = sorted(tutti, key=lambda k: (prezzi[k], -E[k]['mu'] * E[k]['p'], k))[:ECONOMICI_RUOLO]
        pool[r] = sorted(set(forti) | set(economici) | {k for k in fissati if E[k]['ruolo'] == r})
    return pool


def _costruisci(ordine, E, prezzi, slot, vincoli, fissati, budget):
    """Riempie gli slot nell'ordine dato, senza mai rendere impossibile chiudere la rosa."""
    rosa = list(fissati)
    manca = {r: slot[r] - sum(1 for k in rosa if E[k]['ruolo'] == r) for r in regole.RUOLI}
    economici = {r: sorted(prezzi[k] for k in ordine if E[k]['ruolo'] == r and k not in rosa)
                 for r in regole.RUOLI}
    for k in ordine:
        r = E[k]['ruolo']
        if k in rosa or manca[r] <= 0:
            continue
        manca[r] -= 1
        riserva = sum(sum(economici[x][:manca[x]]) for x in regole.RUOLI)
        prova = rosa + [k]
        if sum(prezzi[x] for x in prova) + riserva <= budget and rispetta(prova, prezzi, E, vincoli):
            rosa = prova
        else:
            manca[r] += 1
    return rosa if all(v == 0 for v in manca.values()) else None


def ottimizza(E, prezzi, R, budget, slot, vincoli, fissati=(), esclusi=(), seme=1, partenze=5):
    """La rosa slot[r] per reparto con il valore rapido massimo, entro budget e vincoli.

    Ricerca locale da piu' partenze: scambi 1-per-1 nello stesso reparto e, quando
    non ce ne sono piu', coppie "rinforzo + risparmio" (il budget morde sempre:
    per migliorare un reparto bisogna liberare crediti in un altro)."""
    fissati, esclusi = list(dict.fromkeys(fissati)), set(esclusi)
    for r in regole.RUOLI:
        if sum(1 for k in fissati if E[k]['ruolo'] == r) > slot[r]:
            raise ValueError(f'reparto {r}: piu fissati che slot')
    pool = _pool(E, prezzi, slot, fissati, esclusi)
    for r in regole.RUOLI:
        if len(pool[r]) < slot[r]:
            raise ValueError(f'reparto {r}: servono {slot[r]} giocatori, disponibili {len(pool[r])}')
    cache = {}

    def val(rosa):
        return valore_rapido(rosa, E, R, cache)

    def costo(rosa):
        return sum(prezzi[k] for k in rosa)

    tutti = sorted(k for r in regole.RUOLI for k in pool[r])
    ordini = [sorted(tutti, key=lambda k: (prezzi[k], k)),
              sorted(tutti, key=lambda k: (-E[k]['mu'] * E[k]['p'], k))]
    rng = random.Random(seme)
    for _ in range(max(0, partenze - 2)):
        o = list(tutti)
        rng.shuffle(o)
        ordini.append(o)
    migliore = None
    for ordine in ordini:
        rosa = _costruisci(ordine, E, prezzi, slot, vincoli, fissati, budget)
        if rosa is None:
            continue
        rosa = sorted(_migliora(rosa, pool, E, prezzi, vincoli, budget, fissati, val, costo))
        if migliore is None or val(rosa) > val(migliore) + 1e-12:
            migliore = rosa
    if migliore is None:
        raise ValueError(f'budget {budget} insufficiente per riempire la rosa con questi vincoli')
    rosa = migliore
    return {'rosa': rosa, 'costo': costo(rosa), 'valore': val(rosa), 'valore_esatto': valore_rosa(rosa, E, R)}


def _migliora(rosa, pool, E, prezzi, vincoli, budget, fissati, val, costo):
    fissi = set(fissati)
    while True:
        cur, c0 = val(rosa), costo(rosa)
        fuori = [k for k in sorted(rosa) if k not in fissi]
        su, giu, fatto = [], [], False
        for out in fuori:
            r = E[out]['ruolo']
            for inn in pool[r]:
                if inn in rosa:
                    continue
                nuova = [x for x in rosa if x != out] + [inn]
                if not rispetta(nuova, prezzi, E, vincoli):
                    continue
                dv, dc = val(nuova) - cur, prezzi[inn] - prezzi[out]
                if c0 + dc <= budget and dv > 1e-12:
                    rosa, fatto = nuova, True
                    break
                if dv > 1e-12:
                    su.append((dv, dc, out, inn))
                elif dc < 0:
                    giu.append((dv / -dc, dv, dc, out, inn))
            if fatto:
                break
        if fatto:
            continue
        su = sorted(su, reverse=True)[:COPPIE_UP]
        giu = sorted(giu, reverse=True)[:COPPIE_DOWN]
        for _, dc1, o1, i1 in su:
            for _, _, dc2, o2, i2 in giu:
                if o2 == o1 or i2 == i1 or c0 + dc1 + dc2 > budget:
                    continue
                nuova = [x for x in rosa if x not in (o1, o2)] + [i1, i2]
                if rispetta(nuova, prezzi, E, vincoli) and val(nuova) > cur + 1e-12:
                    rosa, fatto = nuova, True
                    break
            if fatto:
                break
        if not fatto:
            return rosa
