# -*- coding: utf-8 -*-
"""valida - il detector di talenti funziona davvero? Test retrospettivo.

Finora `talenti.py` era un filtro di attenzione con pesi scelti a mano. Questo
modulo prova a trasformarlo in un predittore nell'unico modo onesto: **calcolare
i segnali sulla stagione 2024/25 e misurare cosa e' successo davvero nel
2025/26**, su dati che il detector non ha mai visto.

## Come si misura un "breakout"

Definizione operativa: **crescita dei bonus attesi totali** fra le due stagioni.
    bonus = npxG * 3 + xA * 1        (la parte modellabile della fantamedia)
Un giocatore e' esploso se ha aumentato i bonus totali di almeno +3 punti E di
almeno il 50%. Serve la doppia condizione: chi passa da 0,2 a 0,4 e' cresciuto
del 100% ma non e' successo niente.

## Cosa NON puo' misurare, e va detto subito

Chi nel 2024/25 **non era in Serie A** e' invisibile: non ha una riga da cui
partire. E' il caso di Marco Palestra, che nella stagione precedente non ha
minuti in A - il suo breakout e' avvenuto da zero. Nessun detector costruito su
dati di Serie A poteva vederlo, e questo mette un tetto strutturale a quanto
qualunque modello del genere puo' funzionare.

Uso:
    python valida.py                # report completo
    python valida.py --lift         # solo la metrica che conta
"""
import argparse
import csv
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import talenti  # noqa: E402

PRIMA = 'statistiche_2024-25.csv'
DOPO = 'statistiche_avanzate.csv'
CRESCITA_MIN = 3.0     # punti bonus assoluti
CRESCITA_PCT = 0.50    # e almeno +50%


def bonus(r):
    return talenti.num(r['npxG']) * 3.0 + talenti.num(r['xA'])


def chiave(nome):
    t = talenti.nrm(nome).split()
    return t[-1] if t else ''


def carica_coppie():
    if not os.path.exists(PRIMA):
        raise SystemExit('[!] manca ' + PRIMA)
    p = talenti.punteggia(talenti.carica(PRIMA))
    d = {}
    with open(DOPO, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f, delimiter=';'):
            if talenti.num(r['Min']) >= 400:
                d.setdefault(chiave(r['Nome']), []).append(r)

    coppie, ambigui = [], 0
    for x in p:
        c = d.get(chiave(x['Nome']), [])
        if len(c) != 1:
            ambigui += len(c) > 1
            continue
        y = c[0]
        b0, b1 = bonus(x), bonus(y)
        x['b0'], x['b1'] = b0, b1
        x['crescita'] = b1 - b0
        x['esploso'] = (b1 - b0) >= CRESCITA_MIN and (b0 <= 0 or (b1 / b0 - 1) >= CRESCITA_PCT)
        coppie.append(x)
    return coppie, ambigui, len(p)


def report(coppie, ambigui, tot_prima):
    n = len(coppie)
    espl = [x for x in coppie if x['esploso']]
    base = len(espl) / n if n else 0
    print('\n=== POPOLAZIONE ===')
    print('  %d giocatori con >=400 min nel 2024/25' % tot_prima)
    print('  %d ritrovati anche nel 2025/26 (%.0f%%)' % (n, 100.0 * n / tot_prima))
    print('  %d persi: cambio campionato, infortuni, meno di 400 minuti' % (tot_prima - n))
    print('  %d scartati per omonimia (non indovinati)' % ambigui)
    print('\n  esplosi secondo la definizione: %d su %d = **%.1f%%**'
          % (len(espl), n, 100 * base))
    print('  (bonus attesi +%.0f punti assoluti E almeno +%.0f%%)'
          % (CRESCITA_MIN, 100 * CRESCITA_PCT))

    # LIFT: quanti esplosi nel decile piu' alto di score vs tasso base.
    ordinati = sorted(coppie, key=lambda x: -x['score'])
    print('\n=== IL TEST: il detector batte il caso? ===')
    print('  %-14s%8s%12s%9s' % ('segmento', 'n', 'esplosi', 'lift'))
    for etichetta, sel in (('top 10%', ordinati[:max(1, n // 10)]),
                           ('top 20%', ordinati[:max(1, n // 5)]),
                           ('top 50%', ordinati[:max(1, n // 2)]),
                           ('meta bassa', ordinati[n // 2:])):
        if not sel:
            continue
        tasso = sum(1 for x in sel if x['esploso']) / len(sel)
        lift = tasso / base if base else 0
        print('  %-14s%8d%11.1f%%%8.2fx' % (etichetta, len(sel), 100 * tasso, lift))
    print('\n  lift 1.00 = il detector NON aggiunge niente al caso.')
    print('  lift 2.00 = nel segmento esplode il doppio dei giocatori.')

    # Quale segnale predice davvero: confronto delle medie fra esplosi e non.
    print('\n=== QUALE SEGNALE PREDICE (media esplosi vs non esplosi) ===')
    non = [x for x in coppie if not x['esploso']]
    print('  %-18s%12s%12s%10s' % ('segnale', 'esplosi', 'non espl.', 'rapporto'))
    for k, nome in (('anomalia', 'anomalia ruolo'), ('sottoutilizzo', 'sottoutilizzo'),
                    ('sfortuna90', 'sfortuna/90'), ('creazione', 'creazione'),
                    ('min', 'minuti giocati')):
        if not espl or not non:
            continue
        a = st.mean([x[k] for x in espl])
        b = st.mean([x[k] for x in non])
        r = a / b if b else 0
        marca = '  <-- discrimina' if r > 1.25 or r < 0.8 else ''
        print('  %-18s%12.2f%12.2f%9.2fx%s' % (nome, a, b, r, marca))

    print('\n=== CHI IL DETECTOR AVREBBE INDICATO (top 10 del 2024/25) ===')
    for i, x in enumerate(ordinati[:10], 1):
        esito = 'ESPLOSO' if x['esploso'] else '-'
        print('  %2d. %-26s%-16s score %5.2f   bonus %5.1f -> %5.1f   %s'
              % (i, x['Nome'][:25], x['Squadra'][:15], x['score'],
                 x['b0'], x['b1'], esito))
    return base, ordinati


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lift', action='store_true')
    ap.parse_args()
    coppie, ambigui, tot = carica_coppie()
    print('=' * 76)
    print('  VALIDAZIONE RETROSPETTIVA  2024/25 -> 2025/26')
    print('=' * 76)
    report(coppie, ambigui, tot)
    print('\n  [!] Limite strutturale: chi nel 2024/25 non era in Serie A non ha')
    print('      una riga da cui partire ed e invisibile a questo test. E il caso')
    print('      di Palestra. Nessun modello su dati di Serie A poteva vederlo.\n')


if __name__ == '__main__':
    main()
