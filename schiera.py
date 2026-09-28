# -*- coding: utf-8 -*-
"""schiera - la formazione della settimana: modulo, undici, ordine della panchina.

## Cosa ottimizza

A somma punti: i fantapunti attesi. Negli scontri diretti NO: conta vincere,
e un +3 di media che vale sempre 1 gol in meno del tuo avversario non serve.
Qui l'obiettivo e' **punti in classifica attesi** (3 x P(vittoria) + P(pareggio)),
con le fasce gol vere della lega.

La conseguenza che nessun consiglio "chi schierare" ti da':

- da **favorito** la varianza e' il nemico: meglio il 6,5 sicuro che il
  7 che puo' fare 4 o 13;
- da **sfavorito** e' l'unica speranza: se la tua media perde, ti serve la
  coda alta.

E' un risultato classico del fantasy americano [pub, v. README], qui
misurato partita per partita invece che dato come regola a occhio.

## Come

1. Per ogni modulo ammesso si costruiscono formazioni candidate con criteri
   diversi: per fantavoto atteso, per fantavoto x probabilita' di giocare, e
   due varianti di rischio (piu' e meno varianza).
2. Il valore atteso di ogni formazione e' esatto per ruolo (Poisson-binomiale:
   "i primi k del ruolo che scendono in campo, nell'ordine"), e serve a
   scartare i moduli senza speranza.
3. Le candidate rimaste si simulano (Monte Carlo) con GLI STESSI numeri
   casuali per tutte - numeri casuali comuni: la differenza fra due formazioni
   non si perde nel rumore della simulazione. La simulazione fa entrare la
   panchina nell'ordine, per ruolo, fino al tetto di cambi della lega, e
   calcola il modificatore di difesa sui voti puri.

## Cosa approssima (dichiarato)

- Fantavoto = voto + bonus, entrambi normali e indipendenti fra giocatori.
  Le code sono sbagliate (i bonus sono salti) e due compagni di squadra non
  sono indipendenti (se la squadra prende 4 gol soffrono tutti i difensori).
  Per confrontare formazioni fra loro basta; per prevedere un punteggio no.
- Cambi solo nello stesso ruolo (Classic standard). Il "cambio modulo" di
  alcune leghe non e' modellato.
"""
import math
import random

import regole

RUOLI = regole.RUOLI
LAMBDA_RISCHIO = (-0.75, 0.75)


# ------------------------------------------------------------------ VALORE ESATTO

def valore_ruolo(lista, k):
    """E[somma dei mu dei primi k che giocano], lista nell'ordine di preferenza.

    Programmazione dinamica sul numero di giocatori gia' scesi in campo: un
    giocatore conta se gioca E prima di lui ne sono entrati meno di k."""
    if k <= 0:
        return 0.0
    dist = [1.0] + [0.0] * k
    tot = 0.0
    for g in lista:
        p = g['p']
        tot += g['mu'] * p * sum(dist[:k])
        nuova = [0.0] * (k + 1)
        for j, q in enumerate(dist):
            if not q:
                continue
            if j == k:
                nuova[k] += q
            else:
                nuova[j] += q * (1 - p)
                nuova[j + 1] += q * p
        dist = nuova
    return tot


def valore_atteso(form):
    """Fantapunti attesi della formazione con la panchina (senza tetto di cambi
    e senza modificatore: serve a ordinare, la simulazione fa il conto vero)."""
    n = regole.modulo(form['modulo'])
    return sum(valore_ruolo([g for g in form['titolari'] + form['panchina'] if g['ruolo'] == r], n[r])
               for r in RUOLI)


# ------------------------------------------------------------------ FORMAZIONE

CHIAVI = {
    'mu': lambda g: g['mu'],
    'mu x p': lambda g: g['mu'] * g['p'],
    # chi gioca meno di una volta su due scivola dietro: e' la scelta che fa
    # quasi chiunque a mano, qui e' solo una delle candidate
    'ibrida': lambda g: g['mu'] if g['p'] >= 0.5 else g['mu'] * g['p'],
}


def _chiave_rischio(lam):
    return lambda g: (g['mu'] + lam * g['sd']) if g['p'] >= 0.5 else (g['mu'] + lam * g['sd']) * g['p']


def formazione(rosa, mod, R, chiave='mu'):
    """Titolari e panchina ordinata per un modulo, secondo un criterio."""
    key = CHIAVI[chiave] if isinstance(chiave, str) else chiave
    n = regole.modulo(mod)
    per_ruolo = {r: sorted((g for g in rosa if g['ruolo'] == r),
                           key=lambda g: (g['p'] > 0, key(g)), reverse=True) for r in RUOLI}
    titolari, resto = [], {}
    for r in RUOLI:
        titolari += per_ruolo[r][:n[r]]
        resto[r] = [g for g in per_ruolo[r][n[r]:] if g['p'] > 0] + \
                   [g for g in per_ruolo[r][n[r]:] if g['p'] <= 0]
    # Panchina: prima il portiere di riserva, poi a giro D, C, A nell'ordine.
    # Le sostituzioni cercano il primo del ruolo, quindi conta l'ordine DENTRO
    # il ruolo; il giro serve a non riempire la panchina di un reparto solo.
    panchina = resto['P'][:1]
    code = {r: list(resto[r]) for r in 'DCA'}
    while len(panchina) < R['panchina'] and any(code.values()):
        for r in 'DCA':
            if code[r] and len(panchina) < R['panchina']:
                panchina.append(code[r].pop(0))
    extra = resto['P'][1:]
    while len(panchina) < R['panchina'] and extra:
        panchina.append(extra.pop(0))
    return {'modulo': mod, 'titolari': titolari, 'panchina': panchina,
            'criterio': chiave if isinstance(chiave, str) else 'rischio'}


def completa(rosa, mod):
    """Il modulo si puo' fare con questa rosa?"""
    n = regole.modulo(mod)
    return all(sum(1 for g in rosa if g['ruolo'] == r) >= n[r] for r in RUOLI)


# ------------------------------------------------------------------ SIMULAZIONE

def estrazioni(rosa, n, seme=1):
    """Numeri casuali COMUNI: per ogni giocatore e ogni simulazione, se gioca,
    il voto e il fantavoto. Tutte le formazioni candidate usano questi stessi."""
    rng = random.Random(seme)
    out = {}
    for g in sorted(rosa, key=lambda x: x['k']):
        sd_b = math.sqrt(max(g['sd'] ** 2 - g['sd_v'] ** 2, 0.05))
        b = g['mu'] - g['mv']
        gioca, voto, fv = [], [], []
        for _ in range(n):
            gioca.append(rng.random() < g['p'])
            v = rng.gauss(g['mv'], g['sd_v'])
            voto.append(v)
            fv.append(v + rng.gauss(b, sd_b))
        out[g['k']] = (gioca, voto, fv)
    out['_n'] = n
    return out


def punteggi(form, E, R):
    """Fantapunti di squadra in ogni simulazione, panchina e modificatore compresi."""
    n = E['_n']
    tetto = R['max_sostituzioni']
    out = []
    for s in range(n):
        cambi, usati, finali = 0, set(), []
        for g in form['titolari']:
            if E[g['k']][0][s]:
                finali.append(g)
                continue
            if cambi >= tetto:
                continue
            sub = next((b for b in form['panchina'] if b['ruolo'] == g['ruolo']
                        and b['k'] not in usati and E[b['k']][0][s]), None)
            if sub is not None:
                usati.add(sub['k'])
                cambi += 1
                finali.append(sub)
        tot = sum(E[g['k']][2][s] for g in finali)
        por = next((E[g['k']][1][s] for g in finali if g['ruolo'] == 'P'), None)
        tot += regole.modificatore(por, [E[g['k']][1][s] for g in finali if g['ruolo'] == 'D'], R)
        out.append(tot)
    return out


def scontro(miei, suoi, R):
    """P(vittoria), P(pareggio), P(sconfitta) accoppiando le simulazioni."""
    v = p = 0
    for a, b in zip(miei, suoi):
        ga, gb = regole.gol(a, R), regole.gol(b, R)
        v += ga > gb
        p += ga == gb
    n = float(len(miei))
    return v / n, p / n, 1 - (v + p) / n


# ------------------------------------------------------------------ CONSIGLIO

def migliore_semplice(rosa, R):
    """La formazione a valore atteso massimo, senza simulazione (per l'avversario
    e per il mercato: si assume che chiunque schieri la sua migliore)."""
    cand = [formazione(rosa, m, R, c) for m in R['moduli'] if completa(rosa, m) for c in CHIAVI]
    return max(cand, key=valore_atteso) if cand else None


def consiglia(rosa, R, avversario=None, n=3000, seme=7, moduli_top=3):
    """La formazione da schierare. `avversario` = lista di giocatori (stesso
    formato della rosa): si assume che schieri la sua formazione migliore."""
    cand = []
    for m in R['moduli']:
        if completa(rosa, m):
            cand += [formazione(rosa, m, R, c) for c in CHIAVI]
    if not cand:
        raise ValueError('la rosa non basta per nessun modulo ammesso')
    for c in cand:
        c['atteso'] = valore_atteso(c)
    buoni = sorted({c['modulo'] for c in sorted(cand, key=lambda c: -c['atteso'])},
                   key=lambda m: -max(c['atteso'] for c in cand if c['modulo'] == m))[:moduli_top]
    cand = [c for c in cand if c['modulo'] in buoni]
    for m in buoni:
        for lam in LAMBDA_RISCHIO:
            f = formazione(rosa, m, R, _chiave_rischio(lam))
            f['criterio'] = f'rischio {lam:+.2f}'
            f['atteso'] = valore_atteso(f)
            cand.append(f)

    visti, uniche = set(), []
    for c in cand:
        firma = (c['modulo'], tuple(sorted(g['k'] for g in c['titolari'])),
                 tuple(g['k'] for g in c['panchina']))
        if firma not in visti:
            visti.add(firma)
            uniche.append(c)

    E = estrazioni(rosa, n, seme)
    avv, avviso = None, None
    scontri = bool(R['formula'] == 'scontri' and avversario)
    if scontri:
        fa = migliore_semplice(avversario, R)
        if fa is None:
            scontri = False
            avviso = ("la rosa dell'avversario non basta per nessun modulo: "
                      'ottimizzo la media invece della vittoria')
        else:
            avv = punteggi(fa, estrazioni(avversario, n, seme + 1000), R)
    for c in uniche:
        tot = punteggi(c, E, R)
        c['media'] = sum(tot) / n
        c['sd'] = math.sqrt(sum((x - c['media']) ** 2 for x in tot) / max(n - 1, 1))
        c['gol_medi'] = sum(regole.gol(x, R) for x in tot) / n
        if scontri:
            c['p_v'], c['p_n'], c['p_s'] = scontro(tot, avv, R)
            c['punti'] = 3 * c['p_v'] + c['p_n']
    if scontri:
        uniche.sort(key=lambda c: (-c['punti'], -c['media']))
        obiettivo = 'punti in classifica'
    else:
        uniche.sort(key=lambda c: -c['media'])
        obiettivo = 'media'
    out = {'migliore': uniche[0], 'candidati': uniche, 'obiettivo': obiettivo, 'n': n}
    if avviso:
        out['avviso'] = avviso
    if avv is not None:
        out['avversario'] = {'media': sum(avv) / n,
                             'sd': math.sqrt(sum((x - sum(avv) / n) ** 2 for x in avv) / max(n - 1, 1))}
    return out
