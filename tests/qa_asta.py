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

# ================================================== A2. modello per cella
print('\n[A2] modello per cella scelto dal leave-one-out')

rng = random.Random(3)
lin = [{'k': f'a{i}', 'nome': f'a{i}', 'ruolo': 'A', 'squadra': '', 'fvm': f, 'quota': None,
        'pagato': 0.6 * f * rng.uniform(0.9, 1.1), 'fantasquadra': 'X'} for i, f in enumerate(range(20, 200, 6))]
M = mercato_asta.stima(lin)
q25, q50, q75 = mercato_asta.prevedi(M, 'A', 100)
t('dati proporzionali: previsto vicino a 0.6*FVM', abs(q50 - 60) < 6, f'{q50:.1f}')
t('forchetta ordinata e mai sotto 1', 1 <= q25 <= q50 <= q75, f'{q25:.1f} {q50:.1f} {q75:.1f}')
logd = [dict(x, k=f'l{i}', ruolo='C', fvm=f, pagato=max(1.0, 0.02 * f ** 1.8)) for i, (x, f) in
        enumerate(zip(lin, range(5, 50)))]
M2 = mercato_asta.stima(lin + logd)
t('dati convessi sotto FVM 50: vince il logaritmico', M2[('C', 1)]['tipo'] == 'log', str(M2[('C', 1)]['tipo']))
t('cella con meno di 5 acquisti: baseline', mercato_asta.stima(lin[:3])[('A', 1)]['tipo'] == 'baseline')  # FVM 20-32
t('ruolo mai visto: previsione dalla baseline, senza eccezione', mercato_asta.prevedi(M, 'P', 50)[1] >= 1)
solo = [dict(lin[0], k='unico', ruolo='D', fvm=240.0, pagato=70.0)]
Ms = mercato_asta.stima(lin + solo)
q = mercato_asta.prevedi(Ms, 'D', 240.0)
t('cella con un solo acquisto: la forchetta NON collassa sul suo prezzo (usa i rapporti della lega)',
  q[0] < q[2], f'{q}')
# CONTROPROVA leave-one-out: cambiare il prezzo di un giocatore non cambia il SUO previsto loo
x = lin[5]
prima = mercato_asta.previsto_loo(lin, x['k'])
dopo = mercato_asta.previsto_loo([dict(y, pagato=999.0) if y['k'] == x['k'] else y for y in lin], x['k'])
t('CONTROPROVA: il previsto leave-one-out di un giocatore ignora il suo stesso prezzo', abs(prima - dopo) < 1e-9)
t('fasce: 19 -> 0, 20 -> 1, 99 -> 2, 100 -> 3',
  [mercato_asta.fascia(f) for f in (19, 20, 99, 100)] == [0, 1, 2, 3])

# ================================================== A3. probabilita di acquisto e manie
print('\n[A3] probabilita di acquisto e manie della lega')

pool = [dict(lin[0], k=f'n{i}', fvm=8.0, pagato=None) for i in range(8)] + \
       [dict(lin[0], k=f'c{i}', fvm=8.0, pagato=1.0) for i in range(2)]
t('probabilita di acquisto con Laplace: 2 comprati su 10 -> 0.25',
  abs(mercato_asta.p_acquisto(pool, 'A', 8.0) - 3 / 12) < 1e-9)
porta = [dict(lin[0], k=f'p{i}', ruolo='P', fvm=50.0, pagato=40.0, squadra='INT') for i in range(6)]
milan = [dict(lin[0], k=f'm{i}', fvm=60.0, pagato=30.0, squadra='MIL') for i in range(3)]
man = {(m['dimensione'], m['valore']): m for m in mercato_asta.manie(lin + porta + milan,
                                                                        mercato_asta.stima(lin + porta + milan))}
t('mania per ruolo: i portieri si pagano sopra la baseline', man[('ruolo', 'P')]['scarto'] > 0.2,
  str(man.get(('ruolo', 'P'))))
t('squadra con almeno 5 acquisti compare', ('squadra', 'INT') in man)
t('CONTROPROVA: squadra con meno di 5 acquisti non compare, squadra vuota mai',
  ('squadra', 'MIL') not in man and ('squadra', '') not in man)
t('le manie per fascia ci sono', any(d == 'fascia' for d, _ in man))

# ================================================== A4. CLI
print('\n[A4] CLI del prezzo di mercato')
import subprocess  # noqa: E402
QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lancia(script, *arg, cwd=None):
    r = subprocess.run([sys.executable, os.path.join(QUI, script)] + list(arg),
                       capture_output=True, text=True, cwd=cwd or tmp)
    return r.returncode, r.stdout + r.stderr


rc, out = lancia('mercato_asta.py', '--prezzi', p, '--listone', l)
t('CLI: gira, mostra i modelli per cella e le forchette', rc == 0 and 'baseline' in out and 'forchetta' in out,
  out[-300:])
rc, out = lancia('mercato_asta.py', '--prezzi', os.path.join(tmp, 'non_esiste.csv'), '--listone', l)
t('CLI: file mancante -> messaggio, codice di errore, niente traceback',
  rc != 0 and 'Traceback' not in out and 'non_esiste' in out, out[-300:])

# ================================================== esito
print('\n' + '=' * 74)
gravi = sum(1 for _, _, g in KO if g)
print(f'  RISULTATO: {len(OK)}/{len(OK) + len(KO)} pass   .   {len(KO)} FAIL ({gravi} gravi)')
sys.exit(1 if KO else 0)
