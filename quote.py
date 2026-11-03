# -*- coding: utf-8 -*-
"""Quote dei bookmaker -> contesto di ogni partita della giornata.

    python quote.py                                    # prossime partite (football-data, fixtures.csv)
    python quote.py --rosa rosa_mia.csv                # + i giocatori della tua rosa coinvolti
    python quote.py --dal 31/10/2026 --al 02/11/2026   # RIFA una giornata gia' giocata, senza guardare avanti

Per ogni partita: gol attesi delle due squadre (ricavati da 1X2 + over/under 2,5 con due Poisson
indipendenti), probabilita' di porta inviolata e di gol, e di quanto spostano il fantavoto rispetto al
contesto ABITUALE della squadra (media dei gol attesi nelle ultime 38 partite). E' uno spareggio per
giocatori vicini, non una classifica: i minuti restano quelli delle probabili formazioni.

Fonte: football-data.co.uk, quote medie di mercato pre-partita (colonne Avg*). Dati di terzi: non stanno
nel repo, si scaricano a ogni lancio. Le quote della giornata escono pochi giorni prima: se
fixtures.csv non ha partite di Serie A il programma lo dice e basta, non inventa niente.

## Cosa e' stato misurato (03/11/2026)

[calcolato] training 2023-24..2025-26 (21.032 titolari con voto), test 2026-27 (2.161 titolari da 100
partite, mai viste dal modello). y = fantavoto di lega - previsione di schiera.py (storico con peso
n/(n+26) verso il serbatoio); x = gol attesi dalle quote in QUELLA partita - media dei gol attesi della
squadra nelle ultime 38 (dev. standard 0,32 propri, 0,37 concessi). Fantavoto per +1 gol atteso:

    P+D   propri +0,24 [+0,12, +0,40]   concessi -0,32 [-0,43, -0,18]   (test: +0,15 / -0,48)
    C     propri +0,36                  concessi -0,20                   (test: +1,04 / +0,33  -> instabile)
    A     propri +0,87 [+0,47, +1,27]   concessi ~0                      (test: +0,92 / -0,47, IC larghi)

Errore di previsione del fantavoto sul test: -2,2% di MSE [-0,7%, -3,8%] (P+D -2,3%, A -2,9%, C -1,5% e
NON significativo). Una dev. standard di contesto sposta il fantavoto di ~0,15 (P+D) e ~0,28 (A).

Limiti: 10 giornate di test (rifare a 20); neopromosse senza storico escluse; il voto e il modificatore
difesa non sono stati validati; le quote sono un'istantanea pre-partita.
"""
import argparse
import csv
import datetime as dt
import io
import math
import sys
import urllib.request

URL_I1 = 'https://www.football-data.co.uk/mmz4281/{}/I1.csv'
URL_FIX = 'https://www.football-data.co.uk/fixtures.csv'
FINESTRA = 38        # partite che definiscono il contesto abituale di una squadra
MIN_STORICO = 10     # sotto, la squadra non ha un contesto abituale (neopromosse)

# Fantavoto per +1 gol atteso rispetto al contesto abituale: (gol attesi propri, gol attesi concessi).
# ponytail: C a 0 -- fuori campione il centrocampo non regge (test +1,04/+0,33 contro training +0,36/-0,20);
# sale a coefficiente pieno quando la validazione a 20 giornate lo conferma.
COEFF = {'PD': (0.24, -0.32), 'C': (0.0, 0.0), 'A': (0.87, 0.0)}
GRUPPO = {'P': 'PD', 'D': 'PD', 'C': 'C', 'A': 'A'}


class QuoteNonDisponibili(Exception):
    """Meglio un messaggio chiaro di una scheda vuota che sembra una giornata senza gol."""


def scarica(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'fanta-asta'})
        with urllib.request.urlopen(req, timeout=30) as r:         # segue il reindirizzamento www
            testo = r.read().decode('utf-8-sig')
    except Exception as e:
        raise QuoteNonDisponibili(f'{url} non risponde: {e}')
    return list(csv.DictReader(io.StringIO(testo)))


def codice_stagione(d):
    """2026-11-03 -> '2627' (la stagione cambia a luglio)."""
    y = d.year if d.month >= 7 else d.year - 1
    return f'{y % 100:02d}{(y + 1) % 100:02d}'


def data_riga(r):
    s = r['Date']
    return dt.datetime.strptime(s, '%d/%m/%Y' if len(s) == 10 else '%d/%m/%y').date()


def quote_riga(r):
    """[1, X, 2, over 2,5, under 2,5] medie di mercato, o None se manca qualcosa."""
    try:
        return [float(r[c]) for c in ('AvgH', 'AvgD', 'AvgA', 'Avg>2.5', 'Avg<2.5')]
    except (KeyError, ValueError, TypeError):
        return None


_TAB = []


def _tabella():
    """(P1, PX, P2, POver2.5, lambda casa, lambda trasferta) su una griglia 0,2-3,5 passo 0,05."""
    if not _TAB:
        grid = [0.2 + 0.05 * i for i in range(67)]
        pm = [[math.exp(-g) * g ** k / math.factorial(k) for k in range(11)] for g in grid]
        for i, lh in enumerate(grid):
            for j, la in enumerate(grid):
                p1 = sum(pm[i][a] * pm[j][b] for a in range(11) for b in range(a))
                px = sum(pm[i][a] * pm[j][a] for a in range(11))
                po = 1 - sum(pm[i][a] * pm[j][b] for a in range(11) for b in range(11) if a + b <= 2)
                _TAB.append((p1, px, 1 - p1 - px, po, lh, la))
    return _TAB


def gol_attesi(q):
    """(gol attesi casa, trasferta) che riproducono le quote, margine del book tolto.

    ponytail: Poisson indipendenti, non Dixon-Coles -- sbaglia un po' 0-0 e 1-1; basta per un contesto.
    """
    i1, ix, i2 = 1 / q[0], 1 / q[1], 1 / q[2]
    z = i1 + ix + i2
    io, iu = 1 / q[3], 1 / q[4]
    p1, px, p2, po = i1 / z, ix / z, i2 / z, io / (io + iu)
    t = min(_tabella(), key=lambda x: (x[0] - p1) ** 2 + (x[1] - px) ** 2 + (x[2] - p2) ** 2 + (x[3] - po) ** 2)
    return t[4], t[5]


def abituale(giocate):
    """squadra -> (gol attesi propri medi, concessi medi) sulle ultime FINESTRA partite con quote."""
    per = {}
    for r in sorted(giocate, key=data_riga):
        q = quote_riga(r)
        if q is None:
            continue
        lh, la = gol_attesi(q)
        per.setdefault(r['HomeTeam'], []).append((lh, la))
        per.setdefault(r['AwayTeam'], []).append((la, lh))
    out = {}
    for sq, L in per.items():
        if len(L) >= MIN_STORICO:
            L = L[-FINESTRA:]
            out[sq] = (sum(x[0] for x in L) / len(L), sum(x[1] for x in L) / len(L))
    return out


def delta_fv(lam_own, lam_opp, ab):
    """Spostamento del fantavoto per gruppo (PD, C, A) rispetto al contesto abituale `ab`."""
    do, dc = lam_own - ab[0], lam_opp - ab[1]
    return {g: c[0] * do + c[1] * dc for g, c in COEFF.items()}


def scheda(r, abit):
    """squadra -> contesto della partita `r` (None se non ci sono quote)."""
    q = quote_riga(r)
    if q is None:
        return None
    lh, la = gol_attesi(q)
    out = {}
    for sq, lo, lc in ((r['HomeTeam'], lh, la), (r['AwayTeam'], la, lh)):
        out[sq] = dict(lam_own=lo, lam_opp=lc, p_cs=math.exp(-lc), p_gol=1 - math.exp(-lo),
                       delta=delta_fv(lo, lc, abit[sq]) if sq in abit else None)
    return out


def squadra_di(codice, nomi):
    """'COM' -> 'Como' (il listone usa tre lettere); None se non e' univoco."""
    c = [n for n in nomi if n.upper().startswith(codice.upper())]
    return c[0] if len(c) == 1 else None


def prossime(righe):
    s = [r for r in righe if r.get('Div') == 'I1']
    if not s:
        raise QuoteNonDisponibili(
            'fixtures.csv non ha partite di Serie A: le quote escono pochi giorni prima della giornata. '
            'Riprova a ridosso (di solito giovedi-venerdi).')
    return s


def stampa(r, sch, rosa):
    print(f'\n{r["HomeTeam"]} - {r["AwayTeam"]}   {r["Date"]} {r.get("Time", "")}')
    if sch is None:
        print('   senza quote')
        return
    for sq, c in sch.items():
        d = c['delta']
        fv = ('P/D %+.2f  A %+.2f' % (d['PD'], d['A'])) if d else 'n.d. (squadra senza contesto abituale)'
        print(f'   {sq:<12} gol attesi {c["lam_own"]:.2f} · porta inviolata {100 * c["p_cs"]:.0f}% · '
              f'segna {100 * c["p_gol"]:.0f}%   fv {fv}')
        for p in rosa.get(sq, []):
            g = GRUPPO[p['Ruolo']]
            val = 'n.d.' if not d else 'n.v. (centrocampo non validato)' if g == 'C' else f'{d[g]:+.2f}'
            print(f'      tua rosa: {p["Nome"]} ({p["Ruolo"]})  {val}')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--rosa', help='CSV della tua rosa (Nome;Ruolo;Squadra a tre lettere)')
    ap.add_argument('--dal', help='GG/MM/AAAA: rifa una giornata gia giocata')
    ap.add_argument('--al', help='GG/MM/AAAA (default: dal + 3 giorni)')
    A = ap.parse_args()
    try:
        oggi = dt.date.today()
        corrente = codice_stagione(oggi)
        precedente = codice_stagione(oggi.replace(year=oggi.year - 1))
        giocate = [r for s in (precedente, corrente) for r in scarica(URL_I1.format(s)) if r.get('FTHG')]
        if A.dal:
            dal = dt.datetime.strptime(A.dal, '%d/%m/%Y').date()
            al = dt.datetime.strptime(A.al, '%d/%m/%Y').date() if A.al else dal + dt.timedelta(days=3)
            partite = [r for r in giocate if dal <= data_riga(r) <= al]
            giocate = [r for r in giocate if data_riga(r) < dal]
            if not partite:
                raise QuoteNonDisponibili(f'nessuna partita giocata fra {A.dal} e {al:%d/%m/%Y}.')
        else:
            partite = prossime(scarica(URL_FIX))
    except QuoteNonDisponibili as e:
        raise SystemExit(f'\n[!] {e}\n')
    abit = abituale(giocate)
    nomi = sorted({r[k] for r in partite for k in ('HomeTeam', 'AwayTeam')})
    rosa = {}
    if A.rosa:
        with open(A.rosa, encoding='utf-8-sig', newline='') as f:
            for p in csv.DictReader(f, delimiter=';'):
                sq = squadra_di(p['Squadra'], nomi)
                if sq:
                    rosa.setdefault(sq, []).append(p)
    print(f'{len(partite)} partite · contesto abituale per {len(abit)} squadre · fonte football-data.co.uk')
    for r in partite:
        stampa(r, scheda(r, abit), rosa)


if __name__ == '__main__':
    main()
