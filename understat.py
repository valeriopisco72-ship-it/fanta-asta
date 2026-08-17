# -*- coding: utf-8 -*-
"""Scarica i dati avanzati (xG, npxG, xA, xGChain, xGBuildup) da Understat.

Understat non ha un'API: i dati stanno dentro la pagina, in una variabile
JavaScript `var playersData = JSON.parse('...')` con gli escape esadecimali.
Si estrae con una regex e si decodifica. E' fragile per costruzione - se un
giorno cambiano il nome della variabile, questo file smette di funzionare e
deve dirlo forte invece di restituire una lista vuota.

## Perche' questi dati valgono piu' di gol e assist

- **npxG** (non-penalty expected goals): quanti gol "avrebbe dovuto" segnare su
  azione. Toglie i rigori, che dipendono da chi li calcia e non da quanto e'
  bravo a smarcarsi. E' la misura di qualita' delle occasioni che si crea.
- **xA**: quanti assist "avrebbe dovuto" fare, dalla qualita' dei passaggi.
- **xGChain**: xG di tutte le azioni in cui il giocatore ha toccato palla.
- **xGBuildup**: xGChain TOGLIENDO tiri e assist -> misura il contributo di chi
  costruisce e non finalizza. E' l'unica metrica che vede il regista che al
  fantacalcio non prende mai bonus.
- **time**: MINUTI, non presenze. Venti spezzoni da dieci minuti non sono venti
  partite, e al fantacalcio (che assegna il voto solo con >=25 minuti circa) la
  differenza e' tutto.

Uso:
    python understat.py                      # stagione corrente
    python understat.py --stagione 2024      # 2024/25
    python understat.py --lega EPL           # altri campionati
"""
import argparse
import csv
import json
import re
import urllib.request

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')
CAMPI = ['player_name', 'team_title', 'position', 'games', 'time', 'goals',
         'npg', 'xG', 'npxG', 'assists', 'xA', 'shots', 'key_passes',
         'xGChain', 'xGBuildup', 'yellow_cards', 'red_cards']


class ScaricoFallito(Exception):
    """Meglio un errore rumoroso di un CSV vuoto che sembra un campionato senza gol."""


def scarica(lega='Serie_A', stagione='2025', variabile='playersData'):
    url = f'https://understat.com/league/{lega}/{stagione}'
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        html = urllib.request.urlopen(req, timeout=45).read().decode('utf-8')
    except Exception as e:
        raise ScaricoFallito(f'{url} non risponde: {e}')

    m = re.search(r"var\s+%s\s*=\s*JSON\.parse\('(.*?)'\)" % variabile, html, re.S)
    if not m:
        raise ScaricoFallito(
            f"nella pagina non trovo 'var {variabile} = JSON.parse(...)'.\n"
            '   Understat ha probabilmente cambiato struttura: va aggiornata la regex.')
    try:
        dati = json.loads(m.group(1).encode('utf-8').decode('unicode_escape'))
    except Exception as e:
        raise ScaricoFallito(f'il blocco trovato non e JSON valido: {e}')
    if not dati:
        raise ScaricoFallito('lista vuota: stagione inesistente o non ancora iniziata')
    return dati


def salva(dati, path):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(CAMPI)
        for d in dati:
            w.writerow([round(float(d[c]), 3) if c in
                        ('xG', 'npxG', 'xA', 'xGChain', 'xGBuildup') else d.get(c, '')
                        for c in CAMPI])
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lega', default='Serie_A')
    ap.add_argument('--stagione', default='2025', help='2025 = stagione 2025/26')
    ap.add_argument('--out', default=None)
    A = ap.parse_args()

    out = A.out or f'understat_{A.lega}_{A.stagione}.csv'
    try:
        dati = scarica(A.lega, A.stagione)
    except ScaricoFallito as e:
        raise SystemExit(f'\n[!] {e}\n')
    salva(dati, out)

    minuti = sum(int(d['time']) for d in dati)
    print(f'scritto {out}')
    print(f'  {len(dati)} giocatori · {minuti:,} minuti totali · '
          f'{sum(int(d["goals"]) for d in dati)} gol')
    print(f'  xG totale: {sum(float(d["xG"]) for d in dati):.1f}  '
          f'(se e molto diverso dai gol, il campionato ha over/under-performato)')


if __name__ == '__main__':
    main()
