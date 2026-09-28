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

# ================================================== B. piano d'asta
import itertools  # noqa: E402
import regole  # noqa: E402
import piano_asta  # noqa: E402


def G(k, ruolo, mu, p=1.0, prezzo=1.0):
    return {'k': k, 'nome': k, 'ruolo': ruolo, 'mu': mu, 'mv': min(mu, 6.3), 'p': p,
            'sd': 1.0, 'sd_v': 0.5, 'stato': '', 'prezzo': prezzo}


def rosa_sintetica():   # 3/8/8/6 decrescenti + extra 'XA0'..'XA7' (attaccanti liberi, mu 5.0..8.5)
    r = [G(f'P{i}', 'P', 5.5 - .5 * i) for i in range(3)] + [G(f'D{i}', 'D', 6.6 - .2 * i) for i in range(8)]
    r += [G(f'C{i}', 'C', 7.0 - .2 * i) for i in range(8)] + [G(f'A{i}', 'A', 7.5 - .3 * i) for i in range(6)]
    return r + [G(f'XA{i}', 'A', 5.0 + .5 * i) for i in range(8)]


def pool_piccolo():     # 3P 4D 4C 3A, prezzi 1..30, un solo attaccante nettamente migliore ('A0')
    P = [G(f'P{i}', 'P', 5.0 + .3 * i, prezzo=1 + 4 * i) for i in range(3)]
    D = [G(f'D{i}', 'D', 5.8 + .3 * i, prezzo=1 + 3 * i) for i in range(4)]
    C = [G(f'C{i}', 'C', 6.0 + .4 * i, prezzo=1 + 5 * i) for i in range(4)]
    A = [G('A0', 'A', 8.5, prezzo=20), G('A1', 'A', 6.2, prezzo=4), G('A2', 'A', 6.0, prezzo=1)]
    return {g['k']: g for g in P + D + C + A}


def combinazioni(E, slot):   # tutte le rose con esattamente slot[r] giocatori per ruolo
    per = {r: [k for k in E if E[k]['ruolo'] == r] for r in slot}
    return (sum(c, ()) for c in itertools.product(*(itertools.combinations(per[r], slot[r]) for r in 'PDCA')))


def forchette_finte(E, k=1.0):   # q25/q50/q75 = prezzo * (0.8, 1, 1.25) * k
    return {x: (g['prezzo'] * .8 * k, g['prezzo'] * k, g['prezzo'] * 1.25 * k) for x, g in E.items()}


print('\n[B1] valore dei giocatori e della rosa')
R = regole.carica_lega(None)
E = {g['k']: g for g in rosa_sintetica()}
base = [k for k in E if not k.startswith('X')]    # la rosa completa
v0 = piano_asta.valore_rosa(base, E, R)
migliore = max((k for k in E if k.startswith('XA')), key=lambda k: E[k]['mu'])
peggiore_a = min((k for k in base if E[k]['ruolo'] == 'A'), key=lambda k: E[k]['mu'])
v1 = piano_asta.valore_rosa([k for k in base if k != peggiore_a] + [migliore], E, R)
t('sostituire il peggior attaccante con uno migliore alza il valore', v1 > v0)
t('rosa senza portieri: valore 0', piano_asta.valore_rosa([k for k in base if E[k]['ruolo'] != 'P'], E, R) == 0.0)
t('il valore scala con le giornate', abs(piano_asta.valore_rosa(base, E, R, 33) - 33 * v0) < 1e-6)
Rlunga = regole.carica_lega(None, {'panchina': 25})
Ep = {k: dict(g, p=0.7 if i % 3 else 1.0) for i, (k, g) in enumerate(E.items())}
t('valutazione rapida = esatta quando la panchina e lunga',
  abs(piano_asta.valore_rapido(base, Ep, Rlunga) - piano_asta.valore_rosa(base, Ep, Rlunga)) < 1e-9,
  f'{piano_asta.valore_rapido(base, Ep, Rlunga):.4f} vs {piano_asta.valore_rosa(base, Ep, Rlunga):.4f}')
t('la rapida non sottovaluta mai (la panchina corta toglie, non aggiunge)',
  piano_asta.valore_rapido(base, Ep, R) >= piano_asta.valore_rosa(base, Ep, R) - 1e-9)

print('\n[B2] ottimizzatore della rosa')
Rm = regole.carica_lega(None, {'moduli': ['1-1-1'], 'modificatore': {'attivo': False}, 'panchina': 25})
slot = {'P': 1, 'D': 2, 'C': 2, 'A': 1}
E4 = pool_piccolo()
prezzi = {k: g['prezzo'] for k, g in E4.items()}
vinc = {'portieri_max': 99, 'fascia_media': (25, 49), 'fascia_media_max': 99, 'scouting_ok': set()}
ris = piano_asta.ottimizza(E4, prezzi, Rm, 60, slot, vinc)
bruta = max((c for c in combinazioni(E4, slot) if sum(prezzi[k] for k in c) <= 60),
            key=lambda c: piano_asta.valore_rapido(list(c), E4, Rm))
t('su istanza piccola trova l ottimo della forza bruta',
  abs(ris['valore'] - piano_asta.valore_rapido(list(bruta), E4, Rm)) < 1e-9,
  f"{ris['valore']:.3f} vs {piano_asta.valore_rapido(list(bruta), E4, Rm):.3f}")
t('rispetta budget e slot', ris['costo'] <= 60 and sorted(E4[k]['ruolo'] for k in ris['rosa']) == sorted('PDDCCA'))
t('deterministico a parita di seme', piano_asta.ottimizza(E4, prezzi, Rm, 60, slot, vinc, seme=4) ==
  piano_asta.ottimizza(E4, prezzi, Rm, 60, slot, vinc, seme=4))
vp = dict(vinc, portieri_max=2)
t('vincolo portieri rispettato', sum(prezzi[k] for k in piano_asta.ottimizza(E4, prezzi, Rm, 60, slot, vp)['rosa']
                                     if E4[k]['ruolo'] == 'P') <= 2)
fis = [next(k for k in E4 if E4[k]['ruolo'] == 'D')]
t('i fissati restano, gli esclusi non entrano',
  set(fis) <= set(piano_asta.ottimizza(E4, prezzi, Rm, 60, slot, vinc, fissati=fis)['rosa']) and
  not set(fis) & set(piano_asta.ottimizza(E4, prezzi, Rm, 60, slot, vinc, esclusi=fis)['rosa']))
t('budget minimo: 6 slot con 6 crediti -> tutti da 1 credito se esistono, nessuna eccezione',
  piano_asta.ottimizza(E4, {k: 1.0 for k in E4}, Rm, 6, slot, vinc)['costo'] == 6)
vm = dict(vinc, fascia_media=(15, 49), fascia_media_max=0)
t('vincolo fascia media: nessuno fra 15 e 49 se il massimo e 0',
  all(not 15 <= prezzi[k] <= 49 for k in piano_asta.ottimizza(E4, prezzi, Rm, 60, slot, vm)['rosa']))
try:
    piano_asta.ottimizza(E4, prezzi, Rm, 3, slot, vinc)
    ok = False
except ValueError as e:
    ok = 'budget' in str(e) or 'reparto' in str(e)
t('budget impossibile: errore che dice perche, non una rosa incompleta', ok)

print('\n[B3] tetto come prezzo di indifferenza')
B = 40                                    # budget che morde (la rosa migliore ne costa 73) ma basta per la stella
stella = max((k for k in E4 if E4[k]['ruolo'] == 'A'), key=lambda k: E4[k]['mu'])
t_stella = piano_asta.tetto(stella, E4, prezzi, Rm, B, slot, vinc)
t('la stella unica ha tetto sopra il suo prezzo previsto', t_stella > prezzi[stella], f'{t_stella} vs {prezzi[stella]}')
E5 = dict(E4)
E5['clone'] = dict(E4[stella], k='clone', nome='clone', mu=E4[stella]['mu'] - 0.5)
prezzi5 = dict(prezzi, clone=3.0)
t_clone = piano_asta.tetto(stella, E5, prezzi5, Rm, B, slot, vinc)
t('con un clone quasi uguale da 3 crediti, il tetto della stella crolla', t_clone < t_stella, f'{t_clone} vs {t_stella}')
morto = next(k for k in E4 if E4[k]['ruolo'] == 'C')
E6 = dict(E4)
E6[morto] = dict(E4[morto], p=0.0)
E6['tappa'] = G('tappa', 'C', 5.0, prezzo=1.0)          # c'e' sempre un tappabuco da 1 credito
t('chi non gioca mai ha tetto 1 (se esiste un tappabuco da 1)',
  piano_asta.tetto(morto, E6, dict(prezzi, tappa=1.0), Rm, B, slot, vinc) == 1.0)
t('CONTROPROVA: senza tappabuco da 1, chi non gioca vale quanto fa risparmiare',
  piano_asta.tetto(morto, {k: v for k, v in E6.items() if k != 'tappa'}, prezzi, Rm, B, slot, vinc) > 1.0)
interni = [(k, piano_asta.tetto(k, E4, prezzi, Rm, B, slot, vinc)) for k in sorted(E4) if E4[k]['ruolo'] != 'A']
# un titolare (il migliore del suo reparto) con tetto interno: per lui il fantavoto conta
titolari_ = {max((k for k in E4 if E4[k]['ruolo'] == r), key=lambda k: E4[k]['mu']) for r in 'PDC'}
k_int, t_int = next((k, x) for k, x in interni if k in titolari_ and 1 < x < t_stella)
# il tetto e' a gradini: pagare di piu' costringe a rinunciare a un rinforzo intero altrove
t_poco = piano_asta.tetto(k_int, {**E4, k_int: dict(E4[k_int], mu=E4[k_int]['mu'] + 0.5)}, prezzi, Rm, B, slot, vinc)
t_tanto = piano_asta.tetto(k_int, {**E4, k_int: dict(E4[k_int], mu=E4[k_int]['mu'] + 2)}, prezzi, Rm, B, slot, vinc)
t('CONTROPROVA: piu fantavoto atteso -> il tetto non scende mai, e sale oltre il gradino',
  t_poco >= t_int and t_tanto > t_int, f'{k_int}: {t_int} -> {t_poco} -> {t_tanto}')
t('il tetto e un intero fra 1 e il budget meno gli altri slot da 1',
  all(1 <= x <= B - (sum(slot.values()) - 1) and x == int(x) for x in (t_stella, t_clone, t_poco, t_tanto)))

print('\n[B4] il piano per reparto')
P_ = piano_asta.piano(E4, forchette_finte(E4), Rm, 60, slot, vinc, candidati=3)
righe = [r for rep in P_['reparti'].values() for r in rep['bersagli'] + rep['altri']]
t('budget di reparto = somma mediane dei bersagli x 1.10',
  all(abs(rep['budget'] - 1.10 * sum(r['forchetta'][1] for r in rep['bersagli'])) < 1e-6 for rep in P_['reparti'].values()))
t('etichette secondo il tetto e la forchetta', all(
  (r['etichetta'] == 'affare') == (r['tetto'] is not None and r['tetto'] > r['forchetta'][2]) for r in righe))
t('fuori piano = senza tetto', all((r['tetto'] is None) == (r['etichetta'] == 'fuori piano') for r in righe))
t('alternative dello stesso ruolo e fuori dalla rosa del piano',
  all(E4[a]['ruolo'] == E4[r['k']]['ruolo'] and a not in P_['rosa'] for r in righe for a in r['alternative']))
t('i reparti seguono l ordine di chiamata', list(P_['reparti']) == ['P', 'D', 'C', 'A'])
t('i bersagli sono esattamente la rosa del piano',
  sorted(r['k'] for rep in P_['reparti'].values() for r in rep['bersagli']) == sorted(P_['rosa']))

# ================================================== esito
print('\n' + '=' * 74)
gravi = sum(1 for _, _, g in KO if g)
print(f'  RISULTATO: {len(OK)}/{len(OK) + len(KO)} pass   .   {len(KO)} FAIL ({gravi} gravi)')
sys.exit(1 if KO else 0)
