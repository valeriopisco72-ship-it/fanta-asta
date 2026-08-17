# -*- coding: utf-8 -*-
"""estero - i giocatori arrivati da fuori, e quanto valgono i loro numeri qui.

E' il buco che il tool dichiarava da tre iterazioni: 144 giocatori del listone
2026/27 non hanno storico di Serie A, e pesano il 17% del listone a valore. Sono
i nuovi acquisti - cioe' spesso i piu' cari, quelli su cui l'asta si vince o si
perde. Un modello costruito sulla Serie A e' cieco esattamente li'.

## Cosa fa questo modulo

Prende i dati Understat degli altri campionati e li riporta su scala Serie A con
un **fattore di forza del campionato**. Un gol in Ligue 1 e uno in Premier non
sono la stessa cosa, e sommarli senza correzione e' peggio che non averli.

## 🔴 Il numero piu' fragile di tutto il progetto

I coefficienti qui sotto vengono da **UNA fonte secondaria** (un'analisi
pubblicata su Medium che li ricava da coefficienti UEFA, Elo e modelli xG).
Non sono uno standard, non sono peer-reviewed, e nessuno li ha validati su
Serie A. Li uso perche' un ordine di grandezza dichiarato e' meglio di un
confronto implicito a 1.00 - che e' quello che fai se non correggi niente - ma
vanno trattati per quello che sono: **[STIMA] da fonte singola**.

Chi volesse farlo sul serio: la strada e' misurare i giocatori che hanno
CAMBIATO campionato e confrontare npxG/90 prima e dopo. Serve uno storico di
piu' stagioni, ed e' esattamente il lavoro che qui non c'e'.

Uso:
    python estero.py                    # chi arriva, con i numeri convertiti
    python estero.py --confronto        # effetto della conversione
"""
import argparse
import csv
import os

# [STIMA - fonte singola] Forza relativa dei campionati. Piu' alto = piu' forte.
FORZA = {'EPL': 2.00, 'Serie_A': 1.83, 'La_Liga': 1.80,
         'Bundesliga': 1.76, 'Ligue_1': 1.67}
DESTINAZIONE = 'Serie_A'

# Sotto questi minuti il campione e' troppo piccolo perche' la conversione
# significhi qualcosa: si riporta il dato ma con un avviso.
MIN_AFFIDABILE = 900


def fattore(campionato):
    """Quanto vanno scalati i numeri di quel campionato per leggerli in Serie A.

    >1 = campionato piu' forte dell'Italia, quindi qui farebbe DI PIU'.
    <1 = campionato piu' debole, i numeri vanno ridimensionati.
    """
    f_orig = FORZA.get(campionato)
    if not f_orig:
        return None
    return f_orig / FORZA[DESTINAZIONE]


def num(v, d=0.0):
    try:
        return float(str(v).replace(',', '.'))
    except (TypeError, ValueError):
        return d


def carica(path='estero_2025-26.csv'):
    if not os.path.exists(path):
        raise SystemExit(f'[!] file non trovato: {path}')
    with open(path, encoding='utf-8-sig', newline='') as f:
        dati = list(csv.DictReader(f, delimiter=';'))
    for r in dati:
        m = num(r['Min'])
        f = fattore(r['Campionato'])
        r['min'] = m
        r['n90'] = m / 90.0 if m else 0.0
        r['fattore'] = f
        if f is None:
            r['stato'] = 'CAMPIONATO IGNOTO: nessuna conversione'
            continue
        # I totali si convertono; i rate per 90' anche, ed e' su quelli che si
        # ragiona (chi ha giocato 400 minuti non e' paragonabile a chi ne ha 2500).
        r['npxg_conv'] = num(r['npxG']) * f
        r['xa_conv'] = num(r['xA']) * f
        r['npxg90_conv'] = r['npxg_conv'] / r['n90'] if r['n90'] else 0.0
        r['xa90_conv'] = r['xa_conv'] / r['n90'] if r['n90'] else 0.0
        r['delta_gol'] = num(r['NPG']) - num(r['npxG'])
        r['stato'] = ('ok' if m >= MIN_AFFIDABILE
                      else f'CAMPIONE PICCOLO ({m:.0f} min)')
    return dati


def stampa(dati):
    print('\n=== ARRIVATI DALL ESTERO — numeri riportati su scala Serie A ===')
    print('    npxG/90 e xA/90 sono gia convertiti col fattore del campionato di origine')
    print(f'    {"giocatore":<26s}{"da":<22s}{"lega":<12s}{"min":>6s}'
          f'{"npxG/90":>9s}{"xA/90":>8s}{"gol-npxG":>10s}')
    for r in sorted(dati, key=lambda x: -(x.get('npxg90_conv', 0) + x.get('xa90_conv', 0))):
        if r.get('fattore') is None:
            continue
        avviso = '  !' if r['min'] < MIN_AFFIDABILE else ''
        print(f'    {r["Nome"][:25]:<26s}{r["SquadraEstera"][:21]:<22s}'
              f'{r["Campionato"]:<12s}{r["min"]:>6.0f}'
              f'{r["npxg90_conv"]:>9.2f}{r["xa90_conv"]:>8.2f}'
              f'{r["delta_gol"]:>+10.1f}{avviso}')
    print('    ! = sotto i 900 minuti: campione piccolo, il rate per 90 e rumoroso')


def confronto(dati):
    print('\n=== EFFETTO DELLA CONVERSIONE ===')
    print('    fattori [STIMA, fonte singola]: ' +
          ' · '.join(f'{k} {fattore(k):.3f}' for k in FORZA if k != DESTINAZIONE))
    print(f'\n    {"giocatore":<26s}{"npxG grezzo":>13s}{"npxG in Serie A":>17s}{"scarto":>9s}')
    for r in sorted(dati, key=lambda x: -num(x['npxG'])):
        if r.get('fattore') is None:
            continue
        g, c = num(r['npxG']), r['npxg_conv']
        print(f'    {r["Nome"][:25]:<26s}{g:>13.2f}{c:>17.2f}{c - g:>+9.2f}')
    print('\n    Lettura: la correzione e piccola (max ~9%) e NON e la parte difficile.')
    print('    La parte difficile e che questi numeri vengono da un altro contesto')
    print('    tattico, con altri compagni e un altro allenatore. Il fattore di')
    print('    campionato non cattura niente di tutto questo: e un aggiustamento')
    print('    di scala, non una previsione.')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', default='estero_2025-26.csv')
    ap.add_argument('--confronto', action='store_true')
    A = ap.parse_args()
    dati = carica(A.file)
    print('=' * 80)
    print(f'  arrivati dall estero · {len(dati)} giocatori con dati Understat')
    print('=' * 80)
    if A.confronto:
        confronto(dati)
    else:
        stampa(dati)
        confronto(dati)
    print()


if __name__ == '__main__':
    main()
