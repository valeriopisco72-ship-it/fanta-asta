# -*- coding: utf-8 -*-
"""studio_asta - a che prezzo si e' comprato, e cosa e' rimasto: la lezione per la prossima asta.

Legge la tabella delle rose dell'app (FantaSquadra, Nome, Ruolo, MV, FM, Costo,
FVMp) e risponde a tre domande:

1. **Quale fascia di prezzo ha reso?** Per ogni fascia: quanto si e' speso,
   quanto vale oggi sul mercato (FVMp riportato sulla scala dei crediti della
   lega), la fantamedia di chi gioca e quanti crediti e' costato OGNI
   giocatore da fantamedia >= 7 trovato in quella fascia.
2. **Come hanno speso le squadre?** Quota del budget sui primi 3, quanti
   giocatori da 30+ e da 1-2 crediti, spesa per reparto.
3. **Colpi e flop:** chi e' stato pagato poco e vale molto, e come hanno
   tenuto i giocatori piu' cari.

Letture da fare con cautela, e il programma le stampa:
- il FVMp e' consenso di mercato, non punti fatti;
- un giocatore da 1 credito "guadagna" quasi sempre, perche' il FVMp minimo
  di un rincalzo e' circa 5: la resa della fascia bassa e' gonfiata dalla scala;
- 10 squadre e poche giornate sono un campione piccolo.

Uso:
    python studio_asta.py --tabella statistiche_rose_2026-27.csv
"""
import argparse
import statistics as st

import mercato

FASCE = ((0, 2), (3, 9), (10, 24), (25, 49), (50, 89), (90, 9999))
FM_TOP = 7.0


def prepara(righe):
    """FVMp riportato sulla scala dei crediti spesi: sommano uguale."""
    spesi = sum(r['costo'] or 0 for r in righe)
    fvm = sum(r['fvm'] or 0 for r in righe)
    k = spesi / fvm if fvm else 1.0
    for r in righe:
        r['valore'] = (r['fvm'] or 0) * k
    return k


def fasce(righe, bordi=FASCE):
    out = []
    for a, b in bordi:
        L = [r for r in righe if a <= (r['costo'] or 0) <= b]
        if not L:
            continue
        gioc = [r for r in L if r['mv']]
        top = [r for r in gioc if (r['fm'] or 0) >= FM_TOP]
        speso = sum(r['costo'] or 0 for r in L)
        out.append({'da': a, 'a': b, 'n': len(L), 'speso': speso,
                    'valore': sum(r['valore'] for r in L),
                    'resa': sum(r['valore'] for r in L) / speso if speso else float('nan'),
                    'con_voto': len(gioc),
                    'fm': st.mean(r['fm'] for r in gioc) if gioc else float('nan'),
                    'top': len(top),
                    'crediti_per_top': speso / len(top) if top else float('nan')})
    return out


def squadre(righe):
    out = {}
    for r in righe:
        out.setdefault(r['fantasquadra'], []).append(r)
    res = []
    for fs, L in out.items():
        L.sort(key=lambda r: -(r['costo'] or 0))
        sp = sum(r['costo'] or 0 for r in L)
        res.append({'squadra': fs, 'speso': sp, 'top1': L[0]['costo'] or 0,
                    'top3': sum(r['costo'] or 0 for r in L[:3]) / sp if sp else 0,
                    'da30': sum(1 for r in L if (r['costo'] or 0) >= 30),
                    'da1_2': sum(1 for r in L if (r['costo'] or 0) <= 2),
                    'reparti': {x: sum(r['costo'] or 0 for r in L if r['ruolo'] == x) for x in 'PDCA'},
                    'valore': sum(r['valore'] for r in L)})
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--tabella', default='statistiche_rose.csv')
    A = ap.parse_args()
    T = mercato.carica_tabella(A.tabella)
    k = prepara(T)
    print(f'{len(T)} giocatori, {sum(r["costo"] or 0 for r in T):.0f} crediti spesi, '
          f'1 FVMp = {k:.3f} crediti')
    print('\n=== FASCE DI PREZZO ===')
    print(f'  {"fascia":<9}{"n":>4}{"speso":>7}{"vale ora":>9}{"resa":>6}{"FM chi gioca":>13}'
          f'{"FM>=7":>6}{"crediti per un FM>=7":>22}')
    for f in fasce(T):
        et = f'{f["da"]}-{f["a"]}' if f['a'] < 9999 else f'{f["da"]}+'
        print(f'  {et:<9}{f["n"]:>4}{f["speso"]:>7.0f}{f["valore"]:>9.0f}{f["resa"]:>6.2f}'
              f'{f["fm"]:>13.2f}{f["top"]:>6}{f["crediti_per_top"]:>22.1f}')
    print('  (la resa della fascia bassa e gonfiata: il FVMp minimo di un rincalzo e ~5)')
    print('\n=== SQUADRE ===')
    for s in sorted(squadre(T), key=lambda s: -s['top3']):
        print(f'  {s["squadra"][:20]:<21}top1 {s["top1"]:>4.0f}  primi3 {s["top3"] * 100:>3.0f}%  '
              f'30+: {s["da30"]}  1-2: {s["da1_2"]:>2}  '
              + ' '.join(f'{x}{s["reparti"][x]:>4.0f}' for x in 'PDCA') + f'  vale ora {s["valore"]:.0f}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
