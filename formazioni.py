# -*- coding: utf-8 -*-
"""formazioni - chi gioca DAVVERO adesso, non chi giocava l'anno scorso.

## Il difetto che questo modulo chiude

Il tool deduceva la titolarita' da due cose, entrambe indirette: le PRESENZE
della stagione passata e la QUOTAZIONE (proxy di consenso di mercato). Il
17/08/2026 la misura ha mostrato dove si rompe: fra il 10o e il 20o portiere
del listone i punti attesi crollano dell'83% (153 -> 26) mentre la fantamedia
resta piatta (5,11 -> 5,17). Il crollo e' tutto nelle presenze - cioe' il
modello non stava dicendo "e' piu' scarso", stava dicendo "l'anno scorso non
ha giocato". Un portiere promosso a titolare e uno retrocesso a riserva erano
indistinguibili, ed e' esattamente l'informazione che decide il suo valore.

## La fonte, e perche' UNA sola

`fantacalcio.it/probabili-formazioni-serie-a` da' modulo + XI delle 20 squadre
con i nomi nello **stesso formato del listone** ('Martinez L.', 'Varela G.'):
il join e' esatto, non fuzzy. Aggregare 5 testate darebbe un gradiente 0-5
invece di un binario, ma sono 5 parser fragili per un guadagno che non e' stato
misurato. Se un giorno servira' il gradiente, si aggiunge - non prima.

**Gli infortunati non hanno una fonte separata apposta**: un infortunato non
compare nella probabile formazione, quindi l'XI incorpora gia' l'informazione.
Quello che l'XI NON vede e' il lungodegente che rientra a novembre: per il tool
e' un non-titolare, che ai fini dell'asta e' l'approssimazione giusta.

## Cosa NON e'

Le probabili formazioni sono **opinione giornalistica**, non un fatto: sono la
migliore stima disponibile di chi scendera' in campo, e cambiano ogni giorno.
Il file si data da solo (mtime) e `fanta.py` stampa quanti giorni ha: un XI di
tre settimane fa e' peggio di niente, perche' sembra un dato.

Uso:
    python formazioni.py             # scarica e scrive titolari.csv
    python formazioni.py --stato     # quanti giorni ha il file
"""
import argparse
import csv
import datetime as dt
import html as _html
import os
import re
import sys
import urllib.request

URL = 'https://www.fantacalcio.it/probabili-formazioni-serie-a'
OUT = 'titolari.csv'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')

# Il blocco di una squadra: modulo, poi la lista dei titolari fino a </ul>.
RE_SQUADRA = re.compile(r'data-team-formation="([\d-]+)"(.*?)</ul>', re.S)
RE_GIOCATORE = re.compile(
    r'player-link"\s+href="https://www\.fantacalcio\.it/serie-a/squadre/'
    r'([^/]+)/[^/]+/\d+"[^>]*>.*?<span>([^<]+)</span>', re.S)


def scarica(url=URL):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'replace')


def estrai(html):
    """HTML -> [(squadra, modulo, [nomi])]. Zero squadre = fallito, e si dice."""
    out = []
    for modulo, corpo in RE_SQUADRA.findall(html):
        gioc = RE_GIOCATORE.findall(corpo)
        if not gioc:
            continue
        squadra = gioc[0][0].replace('-', ' ').title()
        # La pagina scrive gli accenti come entita' (&#xe8;): senza unescape
        # 'Soule' non accoppia col listone e sembra un giocatore mancante.
        out.append((squadra, modulo, [_html.unescape(n).strip() for _, n in gioc]))
    return out


def salva(squadre, path=OUT):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['Nome', 'Squadra', 'Modulo'])
        for squadra, modulo, nomi in squadre:
            for n in nomi:
                w.writerow([n, squadra, modulo])
    return path


def carica(path=OUT):
    """{nome_normalizzato: squadra} + eta' del file in giorni. None se non c'e'."""
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8', newline='') as f:
        righe = list(csv.DictReader(f, delimiter=';'))
    eta = (dt.date.today()
           - dt.date.fromtimestamp(os.path.getmtime(path))).days
    return {'titolari': {r['Nome'].strip().lower() for r in righe},
            'squadre': len({r['Squadra'] for r in righe}),
            'n': len(righe), 'giorni': eta}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--stato', action='store_true', help='eta del file, senza scaricare')
    ap.add_argument('--out', default=OUT)
    A = ap.parse_args()

    if A.stato:
        s = carica(A.out)
        if not s:
            print(f'{A.out} non esiste: lancia  python formazioni.py')
            return 1
        print(f'{A.out}: {s["n"]} titolari, {s["squadre"]} squadre, '
              f'aggiornato {s["giorni"]} giorni fa')
        return 0

    squadre = estrai(scarica())
    if len(squadre) < 20:
        # Meglio tenere il file vecchio che sovrascriverlo con meta' campionato.
        print(f'[!] estratte solo {len(squadre)} squadre su 20: la pagina e cambiata '
              f'o non e ancora pubblicata.\n    {A.out} NON e stato toccato.',
              file=sys.stderr)
        return 1
    tot = sum(len(n) for _, _, n in squadre)
    salva(squadre, A.out)
    print(f'{A.out}: {tot} titolari da {len(squadre)} squadre '
          f'({dt.date.today().isoformat()})')
    for s, m, n in squadre[:3]:
        print(f'    {s:<12} {m:<8} {", ".join(n[:4])} ...')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
