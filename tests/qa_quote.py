# -*- coding: utf-8 -*-
"""qa_quote - le invarianti di quote.py, senza rete (righe sintetiche, squadre finte).

Le quote 'giuste' (nessun margine) di due Poisson note devono restituire quei gol attesi; e il margine
del book, che e' rumore, non deve spostarli.
"""
import datetime as dt
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import quote  # noqa: E402

KO = []


def t(nome, cond, dettaglio=''):
    if not cond:
        KO.append(nome)
    print(f'  {"ok  " if cond else "FAIL"} {nome}' + (f'   [{dettaglio}]' if not cond and dettaglio else ''))


def quote_esatte(lh, la, margine=1.0):
    """[1, X, 2, over, under] di due Poisson indipendenti; `margine` > 1 accorcia tutte le quote."""
    pm = [[math.exp(-g) * g ** k / math.factorial(k) for k in range(15)] for g in (lh, la)]
    p1 = sum(pm[0][i] * pm[1][j] for i in range(15) for j in range(i))
    px = sum(pm[0][i] * pm[1][i] for i in range(15))
    po = 1 - sum(pm[0][i] * pm[1][j] for i in range(15) for j in range(15) if i + j <= 2)
    return [m / margine for m in (1 / p1, 1 / px, 1 / (1 - p1 - px), 1 / po, 1 / (1 - po))]


def riga(h, a, q, data='03/11/2026'):
    return {'Div': 'I1', 'Date': data, 'Time': '20:45', 'HomeTeam': h, 'AwayTeam': a,
            'AvgH': q[0], 'AvgD': q[1], 'AvgA': q[2], 'Avg>2.5': q[3], 'Avg<2.5': q[4]}


print('\n[1] dalle quote ai gol attesi')
for lh, la in ((1.5, 1.0), (2.0, 0.8), (1.0, 1.0), (2.6, 0.9)):
    g = quote.gol_attesi(quote_esatte(lh, la))
    t(f'quote esatte di ({lh}, {la}) tornano a meno del passo di griglia',
      abs(g[0] - lh) <= 0.06 and abs(g[1] - la) <= 0.06, f'ottenuto {g}')
g0 = quote.gol_attesi(quote_esatte(1.5, 1.0))
for margine in (1.06, 1.12):
    gm = quote.gol_attesi(quote_esatte(1.5, 1.0, margine=margine))
    t(f'un margine del book del {round((margine - 1) * 100)}% non sposta i gol attesi (stessa cella della griglia)',
      gm == g0, f'{g0} contro {gm}')
t('quote_riga: manca una colonna -> None', quote.quote_riga({'AvgH': '2.0'}) is None)
t('quote_riga: valore vuoto -> None', quote.quote_riga(riga('A', 'B', ['', 3, 3, 2, 2])) is None)
t('quote_riga: numeri letti come numeri', quote.quote_riga(riga('A', 'B', ['2.1', '3.3', '3.5', '1.9', '1.9'])) == [2.1, 3.3, 3.5, 1.9, 1.9])

print('\n[2] contesto abituale e spostamento del fantavoto')
dodici = [riga('TeamA', 'TeamB', quote_esatte(1.5, 1.0), f'{d:02d}/09/2026') for d in range(1, 13)]
ab = quote.abituale(dodici)
t('con 12 partite entrambe le squadre hanno un contesto abituale', set(ab) == {'TeamA', 'TeamB'}, str(ab))
t('con 9 partite nessuna squadra lo ha (neopromosse)', quote.abituale(dodici[:9]) == {})
t('TeamA segna di piu di TeamB nel proprio contesto', ab['TeamA'][0] > ab['TeamB'][0])
d = quote.delta_fv(1.5, 0.8, (1.0, 1.0))
t('P+D: +0,24*0,5 -0,32*(-0,2) = +0,184', abs(d['PD'] - 0.184) < 1e-9, str(d))
t('A: +0,87*0,5 = +0,435', abs(d['A'] - 0.435) < 1e-9, str(d))
t('C resta a 0 finche non regge fuori campione', d['C'] == 0.0)
t('contesto uguale all abituale -> nessuno spostamento', all(abs(v) < 1e-12 for v in quote.delta_fv(1.2, 0.7, (1.2, 0.7)).values()))

print('\n[3] la scheda di una partita')
sch = quote.scheda(riga('TeamA', 'TeamB', quote_esatte(2.2, 0.8)), ab)
t('la favorita ha piu probabilita di porta inviolata', sch['TeamA']['p_cs'] > sch['TeamB']['p_cs'])
t('la favorita ha piu probabilita di segnare', sch['TeamA']['p_gol'] > sch['TeamB']['p_gol'])
t('porta inviolata di A = esp(-gol attesi di B)', abs(sch['TeamA']['p_cs'] - math.exp(-sch['TeamB']['lam_own'])) < 1e-12)
t('favorita meglio del suo solito: P+D e A salgono', sch['TeamA']['delta']['PD'] > 0 < sch['TeamA']['delta']['A'])
t('senza quote la scheda e None, non una scheda di zeri', quote.scheda(riga('TeamA', 'TeamB', ['', '', '', '', '']), ab) is None)
t('squadra senza storico: delta None, non zero', quote.scheda(riga('TeamNuova', 'TeamB', quote_esatte(1.4, 1.1)), ab)['TeamNuova']['delta'] is None)

print('\n[4] nomi, stagioni e rumore')
t('COM -> Como se univoco', quote.squadra_di('COM', ['Como', 'Torino']) == 'Como')
t('codice ambiguo -> None, non la squadra sbagliata', quote.squadra_di('TO', ['Torino', 'Tondela']) is None)
t('codice sconosciuto -> None', quote.squadra_di('XXX', ['Como']) is None)
t('3 novembre 2026 -> stagione 2627', quote.codice_stagione(dt.date(2026, 11, 3)) == '2627')
t('1 marzo 2027 -> ancora 2627', quote.codice_stagione(dt.date(2027, 3, 1)) == '2627')
t('30 giugno 2026 -> 2526', quote.codice_stagione(dt.date(2026, 6, 30)) == '2526')
t('date con anno a due cifre lette', quote.data_riga({'Date': '03/11/26'}) == dt.date(2026, 11, 3))
try:
    quote.prossime([{'Div': 'B1'}, {'Div': 'E1'}])
    t('fixtures senza Serie A: errore chiaro', False)
except quote.QuoteNonDisponibili as e:
    t('fixtures senza Serie A: errore chiaro, non una lista vuota', 'Serie A' in str(e))

print(f'\n{"TUTTO OK" if not KO else "FALLITI: " + ", ".join(KO)}')
sys.exit(1 if KO else 0)
