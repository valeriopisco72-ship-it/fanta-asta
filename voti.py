# -*- coding: utf-8 -*-
"""voti - l'archivio della stagione in corso, giornata per giornata.

L'asta si fa con i dati dell'anno scorso perche' non ce ne sono altri. Da
settembre in poi non e' piu' vero: ogni giornata aggiunge 20 partite di dati
sui giocatori che hai davvero in rosa, nel ruolo che hanno davvero adesso, con
l'allenatore che hanno adesso. Questo modulo li raccoglie.

## Il file

Quello dei voti di giornata di Fantacalcio.it (sezione Voti, "scarica excel"),
salvato in una cartella `voti/` - uno per giornata, .xlsx o .csv. Il formato:

    righe di titolo...
    Cod. | Ruolo | Nome | Voto | Gf | Gs | Rp | Rs | Rf | Au | Amm | Esp | Ass
    ATALANTA                          <- riga-squadra
    ...  | P     | Carnesecchi | 6 | 0 | 1 | ...
    ...  | C     | Tizio       | 6* | ...   <- "6*" = senza voto

Viene accettato anche un CSV "piatto" con le colonne Giornata e Squadra su
ogni riga. La giornata si prende, nell'ordine, dalla colonna Giornata, dal
nome del file (il primo numero: 'voti_giornata_5.xlsx' -> 5), altrimenti il
file viene scartato e lo si dice.

## Regola di casa

Senza voto non e' zero: e' "non ha giocato abbastanza" e in Classic entra la
panchina. Qui resta None fino in fondo, e non conta come presenza.

Uso:
    python voti.py                   # riepilogo della cartella voti/
    python voti.py --cartella altro/ --top 20
"""
import argparse
import csv
import os
import re

import fanta
import nomi
import regole

COLONNE = {
    'giornata': ['giornata', 'g', 'gg', 'turno'],
    'nome': ['nome', 'giocatore', 'calciatore'],
    'ruolo': ['ruolo', 'r'],
    'squadra': ['squadra', 'team', 'club', 'sq'],
    'voto': ['voto', 'v', 'vt', 'votopuro'],
    'gf': ['gf', 'golfatti', 'gol'],
    'gs': ['gs', 'golsubiti'],
    'rp': ['rp', 'rigoriparati'],
    'rs': ['rs', 'rigorisbagliati'],
    'rf': ['rf', 'rigorifatti', 'rigorisegnati'],
    'au': ['au', 'aut', 'autogol', 'autoreti'],
    'amm': ['amm', 'ammonizioni', 'ammonito'],
    'esp': ['esp', 'espulsioni', 'espulso'],
    'ass': ['ass', 'assist'],
}
SENZA_VOTO = {'', '-', 'sv', 's.v.', 's.v', 'nv', 'n.v.'}


def _voto(v):
    """'6*' e 's.v.' -> None. '7,5' -> 7.5."""
    s = str(v if v is not None else '').strip().lower()
    if s in SENZA_VOTO or s.endswith('*'):
        return None
    try:
        return float(s.replace(',', '.'))
    except ValueError:
        return None


def _intestazione(righe):
    """Indice della riga di intestazione: la prima con 'nome' e 'voto'."""
    for i, r in enumerate(righe[:15]):
        n = {fanta._norm(c) for c in r if c is not None}
        if n & set(COLONNE['nome']) and n & set(COLONNE['voto']):
            return i
    return None


def _giornata_da_file(path):
    m = re.search(r'(\d+)', os.path.basename(path))
    return int(m.group(1)) if m else None


def _righe(path):
    """Tutte le righe del file. Per i CSV il separatore si sceglie contando su
    tutto il campione: il Sniffer di `csv` si fa ingannare dalle righe di
    titolo che i file di Fantacalcio.it hanno in testa."""
    if os.path.splitext(path)[1].lower() not in ('.csv', '.txt'):
        intest, resto = fanta._righe_da_file(path)
        return [intest] + resto
    with open(path, encoding='utf-8-sig', newline='') as f:
        testo = f.read()
    sep = max(';\t,', key=testo.count)
    return [r for r in csv.reader(testo.splitlines(), delimiter=sep)
            if any(c.strip() for c in r)]


def leggi_giornata(path, giornata=None, R=None):
    """File di una giornata -> lista di righe-giocatore con fantavoto calcolato."""
    R = R or regole.carica_lega(None)
    righe = _righe(path)
    h = _intestazione(righe)
    if h is None:
        raise fanta.DatoMancante(f'{path}: non trovo le colonne Nome e Voto')
    norm = [fanta._norm(c) for c in righe[h]]
    col = {}
    for campo, cand in COLONNE.items():
        col[campo] = next((norm.index(c) for c in cand if c in norm), None)

    g_file = giornata if giornata is not None else _giornata_da_file(path)
    out, squadra = [], ''
    for r in righe[h + 1:]:
        r = list(r)

        def get(campo):
            i = col[campo]
            return r[i] if i is not None and i < len(r) else None

        nome = str(get('nome') or '').strip()
        ruolo = str(get('ruolo') or '').strip().upper()
        ruolo = ruolo if ruolo in regole.RUOLI else fanta.MANTRA.get(ruolo)
        if not nome or ruolo is None:
            # riga-squadra: una sola cella di testo non numerica
            piene = [str(c).strip() for c in r if c is not None and str(c).strip()]
            if len(piene) == 1 and not re.fullmatch(r'[\d.,]+', piene[0]):
                squadra = piene[0]
            continue
        g = get('giornata')
        g = int(float(g)) if g not in (None, '') else g_file
        if g is None:
            raise fanta.DatoMancante(
                f'{path}: non so che giornata sia (ne colonna Giornata, ne numero nel nome)')
        rec = {'giornata': g, 'nome': nome, 'ruolo': ruolo,
               'squadra': str(get('squadra') or squadra).strip(),
               'voto': _voto(get('voto'))}
        for k in ('gf', 'gs', 'rp', 'rs', 'rf', 'au', 'amm', 'esp', 'ass'):
            rec[k] = regole._n(get(k))
        rec['fv'] = regole.fantavoto(rec, ruolo, R)
        out.append(rec)
    return out


def archivio(cartella='voti', R=None):
    """Tutti i file della cartella. Una giornata riscaricata sostituisce la
    vecchia invece di sommarsi: (giornata, giocatore) e' la chiave."""
    if not cartella or not os.path.isdir(cartella):
        return []
    tutti = {}
    for f in sorted(os.listdir(cartella)):
        if os.path.splitext(f)[1].lower() not in ('.csv', '.txt', '.xlsx', '.xlsm'):
            continue
        for rec in leggi_giornata(os.path.join(cartella, f), R=R):
            tutti[(rec['giornata'], nomi.giocatore(rec['nome']))] = rec
    return sorted(tutti.values(), key=lambda x: (x['giornata'], x['nome']))


def stagione(records):
    """Righe di giornata -> un riepilogo per giocatore e le partite di ogni squadra."""
    G, partite = {}, {}
    squadre_giornata = set()
    for rec in sorted(records, key=lambda x: x['giornata']):
        k = nomi.giocatore(rec['nome'])
        sq = nomi.squadra(rec['squadra']) if rec['squadra'] else ''
        if sq:
            squadre_giornata.add((sq, rec['giornata']))
        g = G.setdefault(k, {'nome': rec['nome'], 'ruolo': rec['ruolo'], 'squadra': sq,
                             'presenze': 0, 'fv': [], 'voti': [], 'giornate': [],
                             'gialli': 0, 'giallo_in': None, 'espulso_in': None,
                             'ultima': None})
        # la squadra piu' recente vince: chi cambia maglia a gennaio cambia contesto
        if sq:
            g['squadra'] = sq
        g['ultima'] = rec['giornata']
        if rec['amm']:
            g['gialli'] += int(rec['amm'])
            g['giallo_in'] = rec['giornata']
        if rec['esp']:
            g['espulso_in'] = rec['giornata']
        if rec['voto'] is not None:
            g['presenze'] += 1
            g['voti'].append(rec['voto'])
            g['fv'].append(rec['fv'])
            g['giornate'].append(rec['giornata'])
    for sq, _ in squadre_giornata:
        partite[sq] = partite.get(sq, 0) + 1
    return {'giocatori': G, 'partite_squadra': partite,
            'giornate': sorted({r['giornata'] for r in records})}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--cartella', default='voti')
    ap.add_argument('--lega', default='lega.json')
    ap.add_argument('--top', type=int, default=15)
    A = ap.parse_args()
    R = regole.carica_lega(A.lega)
    rec = archivio(A.cartella, R=R)
    if not rec:
        print(f'nessun file voti in {A.cartella}/ - scarica i voti di giornata da '
              'fantacalcio.it e salvali li (uno per giornata)')
        return 1
    S = stagione(rec)
    print(f'giornate caricate: {S["giornate"]} | {len(S["giocatori"])} giocatori')
    for r in regole.RUOLI:
        L = [g for g in S['giocatori'].values() if g['ruolo'] == r and g['presenze'] >= 2]
        L.sort(key=lambda g: -sum(g['fv']) / g['presenze'])
        print(f'\n  {r}  fantamedia (almeno 2 presenze)')
        for g in L[:A.top]:
            print(f'    {g["nome"][:22]:<23s}{g["squadra"][:6]:<7s}'
                  f'{sum(g["fv"]) / g["presenze"]:>6.2f}  in {g["presenze"]}')
    diff = [g for g in S['giocatori'].values() if regole.cartellini(g['gialli']) == 'diffidato']
    if diff:
        print('\n  DIFFIDATI (al prossimo giallo saltano una giornata):')
        print('    ' + ', '.join(sorted(g['nome'] for g in diff)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
