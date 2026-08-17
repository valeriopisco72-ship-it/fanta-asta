# -*- coding: utf-8 -*-
"""analisi - lettura calcistica dei dati avanzati, oltre il fantacalcio.

Il fantacalcio guarda gol, assist e voto: cioe' i RISULTATI. I dati avanzati
guardano il PROCESSO che li produce, ed e' il processo a ripetersi l'anno dopo.

## Le quattro domande a cui questo modulo risponde

1. **Chi ha segnato piu' di quanto avrebbe dovuto?** (gol - npxG)
   Il gol e' un evento raro: su 30 partite la fortuna pesa quanto la bravura.
   Chi ha un delta molto positivo quasi sempre regredisce, chi ce l'ha negativo
   rimbalza. E' l'informazione con il rapporto valore/sforzo piu' alto che
   esista nel calcio dei dati.

2. **Chi crea e non viene ripagato?** (xA vs assist)
   xA alto e assist bassi = il giocatore mette palloni buoni e i compagni li
   sbagliano. Cambia compagni, cambiano gli assist. E' vero l'opposto: assist
   molto sopra xA e' merito di chi ha segnato, non di chi ha passato.

3. **Chi fa gioco senza prendere bonus?** (xGBuildup)
   xGChain conta tutte le azioni-gol in cui il giocatore ha toccato palla;
   xGBuildup toglie tiri e assist. E' l'unica metrica che vede il regista che
   costruisce e non finalizza - invisibile al fantacalcio, decisivo alla lettura
   di una squadra.

4. **Chi tira bene e chi tira e basta?** (npxG/tiro)
   Un npxG/tiro alto significa arrivare in posizioni buone. Basso significa
   tirare da fuori: molti tiri, pochi gol attesi.

## Regola di casa

Il join fra Fantacalcio ('Martinez L.') e Understat ('Lautaro Martínez') e'
per cognome + iniziale. Se un nome e' AMBIGUO (due giocatori compatibili) il
modulo NON sceglie: lascia il buco e lo dichiara. Un accoppiamento sbagliato
in silenzio inquina ogni numero a valle, un buco lo vedi.

Uso:
    python analisi.py                          # panoramica generale
    python analisi.py --squadra Napoli         # una squadra
    python analisi.py --ruolo A --top 20
    python analisi.py --confronto              # sovra/sotto-performance
"""
import argparse
import csv
import unicodedata

MIN_MINUTI = 500          # sotto questa soglia i rate per 90' sono rumore
PUNTI_GOL = 3.0           # bonus fantacalcio standard
PUNTI_ASSIST = 1.0
PUNTI_AMM = -0.5


def norm(s):
    """Toglie accenti e punteggiatura: 'Højlund' -> 'hojlund', 'Soulè' -> 'soule'."""
    s = unicodedata.normalize('NFKD', str(s).strip().lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    for a, b in (('ø', 'o'), ('đ', 'd'), ('ł', 'l'), ('ß', 'ss'), ('’', "'")):
        s = s.replace(a, b)
    return ' '.join(s.replace('.', ' ').replace("'", ' ').split())


def leggi(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f, delimiter=';'))


def num(v, d=0.0):
    try:
        return float(str(v).replace(',', '.'))
    except (TypeError, ValueError):
        return d


# ------------------------------------------------------------ MATCHING

def _chiavi_fanta(nome):
    """'Esposito F.P.' -> (cognome 'esposito', iniziali ['f','p']).

    Fantacalcio scrive Cognome + iniziali del nome. Le iniziali sono la sola
    cosa che distingue i due Esposito, ed e' per questo che vanno usate e non
    buttate via.
    """
    t = norm(nome).split()
    if not t:
        return None, []
    # I token di 1-2 lettere in coda sono iniziali ('f', 'p', 'se', 'lo').
    iniz, cogn = [], []
    for tok in t:
        (iniz if len(tok) <= 2 and cogn else cogn).append(tok)
    return ' '.join(cogn), iniz


def accoppia(fanta_nome, indice_understat):
    """Restituisce (record, motivo). record=None se non trovato o ambiguo."""
    cognome, iniz = _chiavi_fanta(fanta_nome)
    if not cognome:
        return None, 'nome vuoto'

    cand = indice_understat.get(cognome, [])
    if not cand:
        # Cognome composto: prova l'ultimo pezzo ('van der brempt' -> 'brempt')
        pezzi = cognome.split()
        if len(pezzi) > 1:
            cand = indice_understat.get(pezzi[-1], [])
    if not cand:
        return None, 'nessun riscontro'
    if len(cand) == 1:
        return cand[0], 'cognome unico'

    # Piu' candidati: si discrimina con le iniziali del nome.
    if iniz:
        pref = ''.join(iniz)
        stretti = [c for c in cand
                   if any(t.startswith(pref) or t.startswith(iniz[0])
                          for t in c['_tokens'] if t != cognome)]
        if len(stretti) == 1:
            return stretti[0], 'cognome + iniziale'
        if len(stretti) > 1:
            return None, f'AMBIGUO ({len(stretti)} compatibili)'
    return None, f'AMBIGUO ({len(cand)} omonimi)'


def indicizza(avanzate):
    """Indice cognome -> lista di record Understat."""
    idx = {}
    for r in avanzate:
        tok = norm(r['Nome']).split()
        r['_tokens'] = tok
        # Il cognome puo' essere l'ultimo token, gli ultimi due, o - nei nomi
        # spagnoli e sudamericani - uno in mezzo: Fantacalcio scrive "Soulè",
        # Understat "Matìas Soulè Malvano". Si indicizzano quindi tutti i token
        # tranne il primo (di norma il nome proprio). Le collisioni che questo
        # produce non sono un problema: diventano AMBIGUO e vengono dichiarate,
        # che e' esattamente il comportamento voluto.
        chiavi = set()
        if tok:
            chiavi.add(tok[-1])
            if len(tok) == 1:
                chiavi.add(tok[0])
            if len(tok) >= 2:
                chiavi.add(' '.join(tok[-2:]))
            for t_ in tok[1:-1]:
                if len(t_) >= 4:
                    chiavi.add(t_)
        for k in chiavi:
            idx.setdefault(k, []).append(r)
    return idx


# ------------------------------------------------------------ METRICHE

def arricchisci(r):
    """Aggiunge le metriche derivate a un record Understat."""
    m = num(r['Min'])
    n90 = m / 90.0 if m else 0.0
    gol, npg = num(r['Gol']), num(r['NPG'])
    npxg, xa = num(r['npxG']), num(r['xA'])
    tiri = num(r['Tiri'])

    r['min'] = m
    r['n90'] = n90
    r['npxg90'] = npxg / n90 if n90 else 0.0
    r['xa90'] = xa / n90 if n90 else 0.0
    r['buildup90'] = num(r['xGBuildup']) / n90 if n90 else 0.0
    r['chain90'] = num(r['xGChain']) / n90 if n90 else 0.0
    r['keypass90'] = num(r['KeyPass']) / n90 if n90 else 0.0
    # Finalizzazione: gol su azione meno gol attesi su azione.
    r['delta_gol'] = npg - npxg
    r['delta_assist'] = num(r['Assist']) - xa
    r['xg_per_tiro'] = npxg / tiri if tiri else 0.0
    r['rigorista'] = gol - npg          # gol su rigore segnati
    # Bonus attesi al fantacalcio: la parte modellabile della fantamedia.
    r['bonus_attesi'] = npxg * PUNTI_GOL + xa * PUNTI_ASSIST + num(r['Amm']) * PUNTI_AMM
    r['bonus_attesi90'] = r['bonus_attesi'] / n90 if n90 else 0.0
    return r


def carica(path='statistiche_avanzate.csv'):
    dati = [arricchisci(r) for r in leggi(path)]
    return dati


# ------------------------------------------------------------ VISTE

def _tab(righe, cols, titolo, nota=''):
    print(f'\n=== {titolo} ===')
    if nota:
        print(f'    {nota}')
    intest = '    ' + f'{"giocatore":<26s}{"squadra":<20s}'
    intest += ''.join(f'{c[0]:>10s}' for c in cols)
    print(intest)
    for r in righe:
        s = '    ' + f'{r["Nome"][:25]:<26s}{r["Squadra"][:19]:<20s}'
        s += ''.join(f'{c[1](r):>10s}' for c in cols)
        print(s)


def sovraperformance(dati, n=12):
    """Chi ha segnato molto piu' o molto meno dei gol attesi."""
    v = [r for r in dati if r['min'] >= MIN_MINUTI and num(r['npxG']) >= 2]
    cols = [('gol', lambda r: f'{num(r["NPG"]):.0f}'),
            ('npxG', lambda r: f'{num(r["npxG"]):.1f}'),
            ('delta', lambda r: f'{r["delta_gol"]:+.1f}'),
            ('min', lambda r: f'{r["min"]:.0f}')]
    _tab(sorted(v, key=lambda r: -r['delta_gol'])[:n], cols,
         'HANNO SEGNATO PIU DEL DOVUTO (attesi in calo)',
         'gol su azione meno gol attesi: il delta positivo raramente si ripete')
    _tab(sorted(v, key=lambda r: r['delta_gol'])[:n], cols,
         'HANNO SEGNATO MENO DEL DOVUTO (attesi in rimbalzo)',
         'creano occasioni e non le concretizzano: di solito e sfortuna, non incapacita')


def creatori(dati, n=12):
    v = [r for r in dati if r['min'] >= MIN_MINUTI]
    cols = [('xA', lambda r: f'{num(r["xA"]):.1f}'),
            ('assist', lambda r: f'{num(r["Assist"]):.0f}'),
            ('delta', lambda r: f'{r["delta_assist"]:+.1f}'),
            ('KP/90', lambda r: f'{r["keypass90"]:.1f}')]
    _tab(sorted(v, key=lambda r: r['delta_assist'])[:n], cols,
         'CREANO E NON VENGONO RIPAGATI (assist attesi in aumento)',
         'mettono palloni buoni che i compagni sbagliano: cambia chi finalizza, cambiano gli assist')


def registi(dati, n=12):
    v = [r for r in dati if r['min'] >= MIN_MINUTI]
    cols = [('build/90', lambda r: f'{r["buildup90"]:.2f}'),
            ('chain/90', lambda r: f'{r["chain90"]:.2f}'),
            ('gol+ass', lambda r: f'{num(r["Gol"]) + num(r["Assist"]):.0f}'),
            ('min', lambda r: f'{r["min"]:.0f}')]
    _tab(sorted(v, key=lambda r: -r['buildup90'])[:n], cols,
         'I REGISTI INVISIBILI (alto contributo, pochi bonus)',
         'xGBuildup = azioni-gol toccate, TOLTI tiri e assist. Il fantacalcio non li vede mai')


def finalizzatori(dati, n=12):
    v = [r for r in dati if r['min'] >= MIN_MINUTI and num(r['Tiri']) >= 20]
    cols = [('npxG/tiro', lambda r: f'{r["xg_per_tiro"]:.3f}'),
            ('tiri', lambda r: f'{num(r["Tiri"]):.0f}'),
            ('npxG/90', lambda r: f'{r["npxg90"]:.2f}'),
            ('min', lambda r: f'{r["min"]:.0f}')]
    _tab(sorted(v, key=lambda r: -r['xg_per_tiro'])[:n], cols,
         'ARRIVANO IN POSIZIONI BUONE (npxG per tiro alto)',
         'tirano poco ma da dove si segna')
    _tab(sorted(v, key=lambda r: r['xg_per_tiro'])[:n], cols,
         'TIRANO DA FUORI (npxG per tiro basso)',
         'volume alto, qualita bassa: molti tiri, pochi gol attesi')


def per_squadra(dati, squadra=None):
    """Aggrega per squadra: chi crea, chi finalizza, chi e sopra o sotto."""
    sq = {}
    for r in dati:
        s = r['Squadra']
        if squadra and norm(squadra) not in norm(s):
            continue
        d = sq.setdefault(s, {'npxG': 0.0, 'gol': 0.0, 'xA': 0.0, 'ass': 0.0, 'n': 0})
        d['npxG'] += num(r['npxG'])
        d['gol'] += num(r['NPG'])
        d['xA'] += num(r['xA'])
        d['ass'] += num(r['Assist'])
        d['n'] += 1
    print('\n=== SQUADRE: produzione attesa vs reale ===')
    print('    delta positivo = ha segnato piu del dovuto (occhio, di solito rientra)')
    print(f'    {"squadra":<22s}{"npxG":>8s}{"gol":>7s}{"delta":>8s}{"xA":>8s}{"assist":>8s}')
    for s, d in sorted(sq.items(), key=lambda x: -(x[1]['gol'] - x[1]['npxG'])):
        print(f'    {s[:21]:<22s}{d["npxG"]:>8.1f}{d["gol"]:>7.0f}'
              f'{d["gol"] - d["npxG"]:>+8.1f}{d["xA"]:>8.1f}{d["ass"]:>8.0f}')


def bonus(dati, n=15):
    v = [r for r in dati if r['min'] >= MIN_MINUTI]
    cols = [('bon/90', lambda r: f'{r["bonus_attesi90"]:.2f}'),
            ('npxG/90', lambda r: f'{r["npxg90"]:.2f}'),
            ('xA/90', lambda r: f'{r["xa90"]:.2f}'),
            ('min', lambda r: f'{r["min"]:.0f}')]
    _tab(sorted(v, key=lambda r: -r['bonus_attesi90'])[:n], cols,
         'BONUS ATTESI PER 90 MINUTI (la parte modellabile della fantamedia)',
         f'npxG x{PUNTI_GOL:.0f} + xA x{PUNTI_ASSIST:.0f} + ammonizioni x{PUNTI_AMM}')


def main():
    global MIN_MINUTI
    ap = argparse.ArgumentParser()
    ap.add_argument('--stat', default='statistiche_avanzate.csv')
    ap.add_argument('--squadra', default=None)
    ap.add_argument('--top', type=int, default=12)
    ap.add_argument('--min-minuti', type=int, default=500)
    ap.add_argument('--solo', choices=['sovra', 'creatori', 'registi', 'tiri',
                                       'squadre', 'bonus'], default=None)
    A = ap.parse_args()
    MIN_MINUTI = A.min_minuti

    dati = carica(A.stat)
    if A.squadra:
        dati = [r for r in dati if norm(A.squadra) in norm(r['Squadra'])]
        if not dati:
            raise SystemExit(f'nessun giocatore per la squadra "{A.squadra}"')

    tot_min = sum(r['min'] for r in dati)
    print('=' * 78)
    print(f'  analisi avanzata · {len(dati)} giocatori · {tot_min:,.0f} minuti · '
          f'soglia {MIN_MINUTI} min')
    print('=' * 78)

    viste = {'sovra': lambda: sovraperformance(dati, A.top),
             'creatori': lambda: creatori(dati, A.top),
             'registi': lambda: registi(dati, A.top),
             'tiri': lambda: finalizzatori(dati, A.top),
             'squadre': lambda: per_squadra(dati),
             'bonus': lambda: bonus(dati, A.top)}
    if A.solo:
        viste[A.solo]()
    else:
        for k in ('sovra', 'creatori', 'registi', 'tiri', 'bonus'):
            viste[k]()
        if not A.squadra:
            per_squadra(dati)
    print()


if __name__ == '__main__':
    main()
