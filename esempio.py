# -*- coding: utf-8 -*-
"""Genera un listone FINTO per provare il tool prima di avere quello vero.

I nomi sono inventati apposta ('AGiocatore007'): se un giorno questo file
finisce aperto per sbaglio al posto delle quotazioni vere, si deve vedere a
colpo d'occhio che non sono dati reali.

    python esempio.py            -> scrive esempio_quotazioni.csv
    python esempio.py --no-storico   (per vedere come il tool dichiara di non sapere)
"""
import csv
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


if __name__ == '__main__':
    genera(con_storico='--no-storico' not in sys.argv)
