# -*- coding: utf-8 -*-
"""calendario - contro chi gioca, e quanto e' difficile.

Il fantavoto di un attaccante non dipende solo da lui: contro la difesa
peggiore del campionato, in casa, i gol attesi della sua squadra possono essere
il doppio che in trasferta contro la migliore. Per il portiere vale al rovescio.
E' l'informazione che decide chi schierare fra due giocatori simili, e quale
portiere mettere quando ne hai due di squadre diverse.

## Il modello, in una riga

    gol attesi(A contro B) = media gol x attacco(A) x difesa(B) x campo

con attacco e difesa = 1.0 per la squadra media. Si stimano dai risultati della
stagione in corso, TIRATI VERSO 1 (shrinkage): dopo 5 giornate una squadra che
ha segnato 12 gol non e' da 2,4 a partita. Se c'e' `squadre_2025-26.csv`
(npxG/npxGA Understat) si parte da li' invece che da 1, ma solo per le squadre
con lo stesso allenatore: per le altre il dato e' storia, non previsione
(v. squadre.py).

## Il file

`calendario.csv`, una riga per partita:

    Giornata;Casa;Trasferta;GolCasa;GolTrasferta
    6;Inter;Monza;;               <- non ancora giocata: gol vuoti

Accetta anche una colonna Risultato ('2-1'). I nomi delle squadre possono
essere sigle o nomi estesi (v. nomi.py).

## Cosa NON sa (dichiarato)

- Il fattore campo e' una stima [STIMA] 1.12, non misurata su questa stagione.
- Attacco e difesa sono gol, non xG: la fortuna di 5 giornate c'e' dentro, lo
  shrinkage la smorza ma non la toglie.
- Neopromosse senza prior partono da 1.0, cioe' da squadra media: e'
  probabilmente ottimista, ed e' scritto qui invece di essere corretto a occhio.

Uso:
    python calendario.py                          # difficolta delle prossime 5 per tutti
    python calendario.py --squadra Inter --prossime 8
    python calendario.py --portieri Inter,Parma,Genoa   # griglia di alternanza
"""
import argparse
import math
import os
import re

import nomi
import voti

CASA = 1.12            # [STIMA] moltiplicatore dei gol attesi in casa (e 1/CASA fuori)
MEDIA_GOL = 1.30       # [STIMA] gol per squadra per partita quando non ci sono risultati
K_SQUADRA = 5.0        # partite "virtuali" di prior: quanto e' lento a crederci

COLONNE = {
    'giornata': ['giornata', 'g', 'turno', 'round'],
    'casa': ['casa', 'home', 'squadracasa', 'locali'],
    'trasferta': ['trasferta', 'ospite', 'ospiti', 'away', 'squadratrasferta'],
    'gc': ['golcasa', 'gc', 'golhome', 'reticasa'],
    'gt': ['goltrasferta', 'gt', 'golaway', 'golospite', 'retitrasferta'],
    'ris': ['risultato', 'ris', 'score'],
}


def _int(v):
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return None


def carica(path='calendario.csv'):
    """-> [{giornata, casa, trasferta, gc, gt, giocata}] con le squadre in chiave nomi.squadra."""
    if not path or not os.path.exists(path):
        return []
    import fanta
    righe = voti._righe(path)
    norm = [fanta._norm(c) for c in righe[0]]
    col = {k: next((norm.index(c) for c in cand if c in norm), None) for k, cand in COLONNE.items()}
    if col['giornata'] is None or col['casa'] is None or col['trasferta'] is None:
        raise fanta.DatoMancante(f'{path}: servono le colonne Giornata, Casa, Trasferta')
    out = []
    for r in righe[1:]:
        def get(k):
            i = col[k]
            return r[i] if i is not None and i < len(r) else None
        g = _int(get('giornata'))
        if g is None or not get('casa') or not get('trasferta'):
            continue
        gc, gt = _int(get('gc')), _int(get('gt'))
        if (gc is None or gt is None) and get('ris'):
            m = re.match(r'\s*(\d+)\s*[-:]\s*(\d+)', str(get('ris')))
            if m:
                gc, gt = int(m.group(1)), int(m.group(2))
        out.append({'giornata': g, 'casa': nomi.squadra(get('casa')),
                    'trasferta': nomi.squadra(get('trasferta')),
                    'gc': gc, 'gt': gt, 'giocata': gc is not None and gt is not None})
    return out


def prossima(partite):
    """La prima giornata con almeno una partita non giocata. None a stagione finita."""
    g = [p['giornata'] for p in partite if not p['giocata']]
    return min(g) if g else None


def prior_da_squadre(path='squadre_2025-26.csv'):
    """Prior di attacco/difesa da npxG/npxGA della stagione scorsa, SOLO per le
    squadre con lo stesso allenatore. {} se il file non c'e'."""
    if not path or not os.path.exists(path):
        return {}
    import squadre
    dati = [r for r in squadre.carica(path) if r['stato'] == 'confermato']
    if not dati:
        return {}
    m_att = sum(r['npxG_p'] for r in dati) / len(dati)
    m_dif = sum(r['npxGA_p'] for r in dati) / len(dati)
    return {nomi.squadra(r['Squadra']): {'att': r['npxG_p'] / m_att, 'dif': r['npxGA_p'] / m_dif}
            for r in dati}


def forze(partite, prior=None, k=K_SQUADRA, casa=CASA):
    """Attacco e difesa di ogni squadra, 1.0 = media. Shrinkage verso il prior."""
    prior = prior or {}
    squadre = {p['casa'] for p in partite} | {p['trasferta'] for p in partite}
    giocate = [p for p in partite if p['giocata']]
    if giocate:
        media = sum(p['gc'] + p['gt'] for p in giocate) / (2.0 * len(giocate))
    else:
        media = MEDIA_GOL
    media = media or MEDIA_GOL
    stat = {s: {'gf': 0, 'ga': 0, 'n': 0} for s in squadre}
    for p in giocate:
        stat[p['casa']]['gf'] += p['gc']
        stat[p['casa']]['ga'] += p['gt']
        stat[p['trasferta']]['gf'] += p['gt']
        stat[p['trasferta']]['ga'] += p['gc']
        stat[p['casa']]['n'] += 1
        stat[p['trasferta']]['n'] += 1
    out = {}
    for s, x in stat.items():
        pr = prior.get(s, {'att': 1.0, 'dif': 1.0})
        n = x['n']
        att = pr['att'] if not n else (k * pr['att'] + n * x['gf'] / n / media) / (k + n)
        dif = pr['dif'] if not n else (k * pr['dif'] + n * x['ga'] / n / media) / (k + n)
        out[s] = {'att': att, 'dif': dif, 'n': n}
    if giocate:
        fonte = f'{len(giocate)} partite giocate' + (' + prior 2025/26' if prior else '')
    else:
        fonte = ('nessun risultato: solo prior 2025/26 e fattore campo' if prior
                 else 'nessun risultato e nessun prior: solo fattore campo')
    return {'squadre': out, 'media': media, 'casa': casa, 'fonte': fonte}


def xg(squadra, avversario, in_casa, F):
    """Gol attesi di `squadra` contro `avversario`."""
    s = F['squadre'].get(nomi.squadra(squadra), {'att': 1.0})
    a = F['squadre'].get(nomi.squadra(avversario), {'dif': 1.0})
    campo = F['casa'] if in_casa else 1.0 / F['casa']
    return F['media'] * s['att'] * a['dif'] * campo


def partita(partite, squadra, giornata):
    """(avversario, in_casa) o None se quella squadra non gioca quella giornata."""
    s = nomi.squadra(squadra)
    for p in partite:
        if p['giornata'] != giornata:
            continue
        if p['casa'] == s:
            return p['trasferta'], True
        if p['trasferta'] == s:
            return p['casa'], False
    return None


def gol_subiti_attesi(partite, F, squadra, giornata):
    m = partita(partite, squadra, giornata)
    if m is None:
        return None
    avv, casa = m
    return xg(avv, squadra, not casa, F)


def difficolta(partite, F, squadra, giornate):
    out = []
    for g in giornate:
        m = partita(partite, squadra, g)
        if m is None:
            continue
        avv, casa = m
        out.append({'giornata': g, 'avversario': avv, 'casa': casa,
                    'xg_fatti': xg(squadra, avv, casa, F),
                    'xg_subiti': xg(avv, squadra, not casa, F)})
    return out


def griglia(partite, F, squadre, giornate):
    """Coppie di portieri: ogni giornata schieri quello che subisce meno.
    Punteggio = gol subiti attesi sommati scegliendo ogni volta il migliore dei
    due. Ordinate dalla migliore. Una coppia di squadre con lo stesso calendario
    vale esattamente quanto una squadra sola: e' il controllo che il conto torna."""
    ks = [nomi.squadra(s) for s in squadre]
    giornate = list(giornate)
    out = []
    for i, a in enumerate(ks):
        for b in ks[i + 1:]:
            tot, n = 0.0, 0
            for g in giornate:
                ga, gb = gol_subiti_attesi(partite, F, a, g), gol_subiti_attesi(partite, F, b, g)
                vals = [v for v in (ga, gb) if v is not None]
                if vals:
                    tot += min(vals)
                    n += 1
            out.append({'coppia': (a, b), 'gs_attesi': tot, 'giornate': n})
    return sorted(out, key=lambda c: c['gs_attesi'])


def p_porta_inviolata(gs_attesi):
    """Poisson: probabilita' di zero gol subiti."""
    return math.exp(-gs_attesi)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--calendario', default='calendario.csv')
    ap.add_argument('--squadre-prior', default='squadre_2025-26.csv')
    ap.add_argument('--squadra', default=None)
    ap.add_argument('--prossime', type=int, default=5)
    ap.add_argument('--portieri', default=None, help='squadre separate da virgola')
    A = ap.parse_args()

    P = carica(A.calendario)
    if not P:
        print(f'{A.calendario} non trovato o vuoto. Formato: Giornata;Casa;Trasferta;GolCasa;GolTrasferta')
        return 1
    F = forze(P, prior_da_squadre(A.squadre_prior))
    g0 = prossima(P)
    if g0 is None:
        print('stagione finita: nessuna partita da giocare')
        return 0
    gg = range(g0, g0 + A.prossime)
    print(f'forza squadre: {F["fonte"]} | media {F["media"]:.2f} gol/partita | '
          f'giornate {g0}-{g0 + A.prossime - 1}')

    if A.portieri:
        sq = [s.strip() for s in A.portieri.split(',') if s.strip()]
        print('\n=== GRIGLIA PORTIERI (gol subiti attesi, scegliendo ogni volta il migliore) ===')
        for c in griglia(P, F, sq, gg):
            print(f'    {c["coppia"][0]:<12}+ {c["coppia"][1]:<12}{c["gs_attesi"]:>6.2f}  '
                  f'in {c["giornate"]} giornate')
        return 0

    squadre = [nomi.squadra(A.squadra)] if A.squadra else sorted(F['squadre'])
    righe = []
    for s in squadre:
        d = difficolta(P, F, s, gg)
        if d:
            righe.append((s, d, sum(x['xg_fatti'] - x['xg_subiti'] for x in d)))
    print('\n=== CALENDARIO: saldo gol attesi nelle prossime giornate (alto = facile) ===')
    for s, d, saldo in sorted(righe, key=lambda r: -r[2]):
        partite = '  '.join(f'{x["avversario"][:6].upper()}{"(c)" if x["casa"] else "(f)"}' for x in d)
        print(f'    {s[:12]:<13}{saldo:>+6.2f}   {partite}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
