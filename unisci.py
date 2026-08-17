# -*- coding: utf-8 -*-
"""Unisce le quotazioni 2026/27 con le statistiche della stagione precedente.

Il join e' per NOME, ed e' la parte fragile: due fonti diverse scrivono lo stesso
giocatore in modi diversi. Qui le fonti sono entrambe Fantacalcio.it, quindi la
resa e' alta - ma il modulo NON nasconde chi non ha trovato: chi resta senza
storico esce in un elenco, perche' sono proprio i giocatori che contano.

## Perche' quell'elenco e' la cosa piu' utile di questo script

Chi non matcha non e' rumore: sono i **nuovi arrivati dall'estero e dalla Serie B**.
Cioe' spesso i piu' costosi del listone. Un modello costruito sullo storico
italiano e' strutturalmente cieco proprio dove si vince o si perde l'asta, e
saperlo vale piu' che avere il numero.

Uso:
    python unisci.py
    python unisci.py --quot quotazioni_ufficiali.csv --stat statistiche_2025-26.csv \
                     --out listone_completo.csv
"""
import argparse
import csv
import unicodedata


def chiave(nome):
    """Normalizza il nome per il confronto: accenti, maiuscole, spazi, punti.

    'Soulè' e 'Soule', 'Martinez L.' e 'MARTINEZ L' devono cadere sulla stessa
    chiave. Cio' che NON facciamo e' il match fuzzy: preferiamo un buco
    dichiarato a un accoppiamento sbagliato in silenzio (Esposito F.P. e
    Esposito Se. sono due persone diverse, e un fuzzy le fonderebbe).
    """
    s = unicodedata.normalize('NFKD', nome.strip().lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return ' '.join(s.replace('.', ' ').replace("'", "'").split())


def leggi(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f, delimiter=';'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quot', default='quotazioni_ufficiali.csv')
    ap.add_argument('--stat', default='statistiche_2025-26.csv')
    ap.add_argument('--out', default='listone_completo.csv')
    A = ap.parse_args()

    quot, stat = leggi(A.quot), leggi(A.stat)
    idx = {chiave(r['Nome']): r for r in stat}

    righe = [['Nome', 'Ruolo', 'Squadra', 'Quotazione', 'FVM',
              'Fantamedia', 'Presenze', 'Gol', 'Assist', 'Rigori']]
    trovati, mancanti = 0, []
    for q in quot:
        s = idx.get(chiave(q['Nome']))
        if s and float(s['Presenze'].replace(',', '.') or 0) > 0:
            trovati += 1
            righe.append([q['Nome'], q['Ruolo'], q['Squadra'], q['Quotazione'],
                          q.get('FVM', ''), s['Fantamedia'], s['Presenze'],
                          s['Gol'], s['Assist'], s['Rigori']])
        else:
            mancanti.append(q)
            righe.append([q['Nome'], q['Ruolo'], q['Squadra'], q['Quotazione'],
                          q.get('FVM', ''), '', '', '', '', ''])

    with open(A.out, 'w', encoding='utf-8', newline='') as f:
        csv.writer(f, delimiter=';').writerows(righe)

    tot = len(quot)
    print(f'scritto {A.out}')
    print(f'  {trovati}/{tot} con storico Serie A ({100 * trovati / tot:.0f}%)')
    print(f'  {len(mancanti)} SENZA storico\n')

    # I senza-storico che costano: sono il buco che conta.
    cari = sorted(mancanti, key=lambda r: -float(r['Quotazione']))[:20]
    print('  I PIU CARI SENZA STORICO SERIE A')
    print('  (nuovi dall estero o dalla B: nessun modello statistico li vede)')
    print(f'  {"giocatore":<24s}{"ruolo":<7s}{"squadra":<9s}{"quot.":>6s}')
    for r in cari:
        print(f'  {r["Nome"][:23]:<24s}{r["Ruolo"]:<7s}{r["Squadra"]:<9s}'
              f'{r["Quotazione"]:>6s}')

    spesa_cieca = sum(float(r['Quotazione']) for r in mancanti)
    spesa_tot = sum(float(r['Quotazione']) for r in quot)
    print(f'\n  quota del listone (a valore) su cui il modello e cieco: '
          f'{100 * spesa_cieca / spesa_tot:.0f}%')


if __name__ == '__main__':
    main()
