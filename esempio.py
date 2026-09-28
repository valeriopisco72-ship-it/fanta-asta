# -*- coding: utf-8 -*-
"""Genera un listone FINTO per provare il tool prima di avere quello vero.

I nomi sono inventati apposta ('AGiocatore007'): se un giorno questo file
finisce aperto per sbaglio al posto delle quotazioni vere, si deve vedere a
colpo d'occhio che non sono dati reali.

    python esempio.py            -> scrive esempio_quotazioni.csv
    python esempio.py --no-storico   (per vedere come il tool dichiara di non sapere)
    python esempio.py --stagione     -> cartella esempio_stagione/ con una lega
                                        finta completa per provare socio.py
"""
import csv
import json
import math
import os
import random
import sys

N = {'P': 60, 'D': 200, 'C': 200, 'A': 120}
FM = {'P': 5.6, 'D': 5.9, 'C': 6.1, 'A': 6.4}


def genera(path='esempio_quotazioni.csv', con_storico=True, seme=42):
    rng = random.Random(seme)
    righe = [['Nome', 'Ruolo', 'Squadra', 'Quotazione', 'Fantamedia', 'Presenze']]
    for ruolo, n in N.items():
        for i in range(n):
            rango = i / n
            fm = FM[ruolo] + (1 - rango) * 1.8 + rng.uniform(-0.25, 0.25)
            pres = max(2, int(34 * (1 - rango) + rng.uniform(-6, 6)))
            quota = max(1, int((1 - rango) ** 2 * 40 + rng.uniform(0, 3)))
            r = [f'{ruolo}Giocatore{i:03d}', ruolo, f'Team{rng.randint(1, 20):02d}', quota]
            r += [round(fm, 2), pres] if con_storico else ['', '']
            righe.append(r)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        csv.writer(f, delimiter=';').writerows(righe)
    print(f'scritto {path}  ({sum(N.values())} giocatori finti, '
          f'storico: {"si" if con_storico else "no"})')
    return path


# ------------------------------------------------------------------ STAGIONE

SQ_SERIE_A = [f'Team{i:02d}' for i in range(1, 21)]
FANTA = ['FC Alfa', 'FC Beta', 'FC Gamma', 'FC Delta', 'FC Epsilon',
         'FC Zeta', 'FC Eta', 'FC Theta', 'FC Iota', 'FC Kappa']
ROSA_CLUB = {'P': 3, 'D': 8, 'C': 8, 'A': 6}


def _poisson(rng, lam):
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1


def _girone(squadre):
    """Metodo del cerchio: 19 giornate di andata, poi il ritorno a campi invertiti."""
    s = list(squadre)
    n = len(s)
    andata = []
    for g in range(n - 1):
        partite = [(s[i], s[n - 1 - i]) if g % 2 == 0 else (s[n - 1 - i], s[i]) for i in range(n // 2)]
        andata.append(partite)
        s = [s[0]] + [s[-1]] + s[1:-1]
    return andata + [[(b, a) for a, b in giornata] for giornata in andata]


def genera_stagione(cartella='esempio_stagione', giocate=5, seme=7):
    """Una lega finta coerente: listone, probabili, calendario con risultati,
    voti di giornata nel formato Fantacalcio.it, rose di 10 fantasquadre."""
    rng = random.Random(seme)
    os.makedirs(os.path.join(cartella, 'voti'), exist_ok=True)
    forza = {s: (rng.uniform(0.7, 1.35), rng.uniform(0.7, 1.35)) for s in SQ_SERIE_A}  # att, dif
    gioc, n = [], 0
    for sq in SQ_SERIE_A:
        for ruolo, k in ROSA_CLUB.items():
            for j in range(k):
                q = rng.gauss(0, 1) - 0.35 * j        # i primi di ogni reparto sono i titolari
                gioc.append({'nome': f'{ruolo}Giocatore{n:03d}', 'ruolo': ruolo, 'squadra': sq, 'q': q})
                n += 1
    xi_n = {'P': 1, 'D': 4, 'C': 3, 'A': 3}
    tit = set()
    for sq in SQ_SERIE_A:
        for r, k in xi_n.items():
            L = sorted((g for g in gioc if g['squadra'] == sq and g['ruolo'] == r),
                       key=lambda g: -(g['q'] + rng.gauss(0, 0.3)))
            tit |= {g['nome'] for g in L[:k]}
    fm_base = {'P': 5.0, 'D': 6.0, 'C': 6.3, 'A': 6.7}
    with open(os.path.join(cartella, 'listone.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['Nome', 'Ruolo', 'Squadra', 'Quotazione', 'Fantamedia', 'Mv', 'Presenze'])
        for g in gioc:
            pres = max(0, int(30 * (0.8 if g['nome'] in tit else 0.3) + rng.uniform(-6, 6)))
            fm = fm_base[g['ruolo']] + 0.45 * g['q'] + rng.gauss(0, 0.25)
            quota = max(1, int(8 + 7 * g['q'] + (6 if g['nome'] in tit else 0) + rng.uniform(-2, 2)))
            w.writerow([g['nome'], g['ruolo'], g['squadra'], quota,
                        round(fm, 2) if pres >= 3 else '', round(6.0 + 0.2 * g['q'], 2) if pres >= 3 else '',
                        pres if pres >= 3 else ''])
            g['quota'] = quota
    with open(os.path.join(cartella, 'titolari.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['Nome', 'Squadra', 'Modulo'])
        for g in gioc:
            if g['nome'] in tit:
                w.writerow([g['nome'], g['squadra'], '4-3-3'])

    cal = _girone(SQ_SERIE_A)
    with open(os.path.join(cartella, 'calendario.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['Giornata', 'Casa', 'Trasferta', 'GolCasa', 'GolTrasferta'])
        for gi, partite in enumerate(cal, 1):
            voti_g = []
            for casa, fuori in partite:
                if gi > giocate:
                    w.writerow([gi, casa, fuori, '', ''])
                    continue
                gc = _poisson(rng, 1.3 * forza[casa][0] * forza[fuori][1] * 1.12)
                gt = _poisson(rng, 1.3 * forza[fuori][0] * forza[casa][1] / 1.12)
                w.writerow([gi, casa, fuori, gc, gt])
                for sq, gf, gs in ((casa, gc, gt), (fuori, gt, gc)):
                    voti_g.append([sq.upper()])
                    in_campo = [g for g in gioc if g['squadra'] == sq
                                and rng.random() < (0.9 if g['nome'] in tit else 0.12)]
                    peso = {'P': 0, 'D': 1, 'C': 2.5, 'A': 5}
                    marcatori = rng.choices(in_campo, [peso[g['ruolo']] * math.exp(0.5 * g['q'])
                                                       for g in in_campo], k=gf) if gf and in_campo else []
                    assist = rng.choices(in_campo, [1 + (g['ruolo'] in 'CA') for g in in_campo],
                                         k=gf) if gf and in_campo else []
                    for g in in_campo:
                        voto = round(2 * (6.0 + 0.25 * g['q'] + 0.3 * (gf - gs) / 2 + rng.gauss(0, 0.5))) / 2
                        sv = g['ruolo'] != 'P' and rng.random() < 0.08
                        voti_g.append([n, g['ruolo'], g['nome'], '6*' if sv else voto,
                                       marcatori.count(g), gs if g['ruolo'] == 'P' else 0, 0, 0, 0, 0,
                                       int(rng.random() < 0.13), int(rng.random() < 0.01),
                                       assist.count(g)])
            if gi <= giocate:
                with open(os.path.join(cartella, 'voti', f'voti_giornata_{gi:02d}.csv'), 'w',
                          encoding='utf-8', newline='') as fv:
                    wv = csv.writer(fv, delimiter=';')
                    wv.writerow([f'Voti Fantacalcio (FINTI) - Giornata {gi}'])
                    wv.writerow(['Cod.', 'Ruolo', 'Nome', 'Voto', 'Gf', 'Gs', 'Rp', 'Rs', 'Rf',
                                 'Au', 'Amm', 'Esp', 'Ass'])
                    wv.writerows(voti_g)

    # rose: asta finta "a serpente" per quotazione, reparto per reparto
    rose = {f: [] for f in FANTA}
    for r, k in (('P', 3), ('D', 8), ('C', 8), ('A', 6)):
        L = sorted((g for g in gioc if g['ruolo'] == r), key=lambda g: -g['quota'] + rng.uniform(-3, 3))
        ordine = []
        for giro in range(k):
            ordine += FANTA if giro % 2 == 0 else FANTA[::-1]
        for fs, g in zip(ordine, L):
            rose[fs].append(g['nome'])
    with open(os.path.join(cartella, 'rose.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['FantaSquadra', 'Nome'])
        for fs, L in rose.items():
            w.writerows([fs, x] for x in L)

    lega = {'nome': 'Lega FINTA di esempio', 'mia': 'FC Alfa', 'formula': 'scontri',
            'calendario_lega': {str(g): FANTA[1 + (g % 9)] for g in range(1, 39)},
            'file': {'listone': 'listone.csv', 'voti': 'voti', 'calendario': 'calendario.csv',
                     'rose': 'rose.csv', 'titolari': 'titolari.csv'}}
    with open(os.path.join(cartella, 'lega.json'), 'w', encoding='utf-8') as f:
        json.dump(lega, f, ensure_ascii=False, indent=1)
    print(f'scritta {cartella}/  (lega FINTA: 20 squadre, {n} giocatori, {giocate} giornate giocate)')
    print(f'   prova:  python socio.py --lega {cartella}/lega.json settimana')
    return cartella


if __name__ == '__main__':
    if '--stagione' in sys.argv:
        genera_stagione()
    else:
        genera(con_storico='--no-storico' not in sys.argv)
