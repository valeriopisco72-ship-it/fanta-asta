# -*- coding: utf-8 -*-
"""qa_asta - prezzo di mercato della lega e piano d'asta, con le controprove.

Stesso patto di qa_fanta.py e qa_socio.py: dati sintetici, nomi finti, e per
ogni regola la domanda "se rompo il codice, questo test se ne accorge?".
"""
import csv
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fanta  # noqa: E402
import mercato_asta  # noqa: E402

OK, KO = [], []


def t(nome, cond, dettaglio='', grave=True):
    (OK if cond else KO).append((nome, dettaglio, grave))
    print(f'  {"ok  " if cond else "FAIL"} {nome}' + (f'   [{dettaglio}]' if not cond and dettaglio else ''))


def scrivi_csv(path, righe, sep=';'):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        csv.writer(f, delimiter=sep).writerows(righe)
    return path


tmp = tempfile.mkdtemp(prefix='asta_qa_')

# ================================================== A1. carica e unisci
print('\n[A1] carica: prezzi pagati + listone')

p = scrivi_csv(os.path.join(tmp, 'prezzi.csv'), [['FantaSquadra', 'Nome', 'Ruolo', 'Pagato', 'FVM'],
    ['X', 'Alfa A.', 'A', '40', '100'], ['Y', 'Beta B.', 'D', '10', '20']])
l = scrivi_csv(os.path.join(tmp, 'listone.csv'), [['Nome', 'Ruolo', 'Squadra', 'Quotazione', 'FVM'],
    ['Alfa A.', 'A', 'INT', '20', '100'], ['Beta B.', 'D', 'MIL', '8', '20'], ['Gamma G.', 'C', 'ROM', '3', '5']])
A = mercato_asta.carica(p, l)
t('unisce comprati e non comprati', len(A) == 3 and sum(1 for a in A if a['pagato'] is None) == 1)
al = next(a for a in A if a['nome'] == 'Alfa A.')
t('i comprati portano prezzo, squadra e fantasquadra',
  (al['pagato'], al['squadra'], al['fantasquadra'], al['fvm']) == (40.0, 'INT', 'X', 100.0))
bad = scrivi_csv(os.path.join(tmp, 'prezzi_bad.csv'), [['FantaSquadra', 'Nome', 'Ruolo', 'Pagato', 'FVM'],
    ['X', 'Nessuno N.', 'A', '5', '10']])
try:
    mercato_asta.carica(bad, l)
    ok = False
except fanta.DatoMancante as e:
    ok = 'Nessuno N.' in str(e)
t('CONTROPROVA: un comprato assente dal listone ferma tutto e lo nomina', ok)
t('senza listone: solo i comprati', len(mercato_asta.carica(p, None)) == 2)

# ================================================== esito
print('\n' + '=' * 74)
gravi = sum(1 for _, _, g in KO if g)
print(f'  RISULTATO: {len(OK)}/{len(OK) + len(KO)} pass   .   {len(KO)} FAIL ({gravi} gravi)')
print('=' * 74)
sys.exit(1 if KO else 0)
