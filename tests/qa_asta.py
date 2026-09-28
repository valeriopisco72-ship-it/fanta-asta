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

# i fissati da soli sforano il budget: nessuna rosa valida (bug trovato rigiocando l'asta vera: speso 501 su 500)
tutti_fissi = [k for r in 'PDCA' for k in sorted(k for k in E4 if E4[k]['ruolo'] == r)[:slot[r]]]
costo_fissi = sum(prezzi[k] for k in tutti_fissi)
try:
    piano_asta.ottimizza(E4, prezzi, Rm, costo_fissi - 1, slot, vinc, fissati=tutti_fissi)
    ok = False
except ValueError:
    ok = True
t('fissati che da soli sforano il budget: errore, non una rosa fuori budget', ok)
t('CONTROPROVA: con budget giusto i fissati bastano',
  piano_asta.ottimizza(E4, prezzi, Rm, costo_fissi, slot, vinc, fissati=tutti_fissi)['costo'] == costo_fissi)
ultimo = tutti_fissi[-1]
t('tetto dell ultimo slot = i crediti che restano',
  piano_asta.tetto(ultimo, E4, dict(prezzi, **{ultimo: 1.0}), Rm, costo_fissi - prezzi[ultimo] + 1, slot, vinc,
                   fissati=tutti_fissi[:-1]) == 1.0)

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
t('senza tetto = fuori piano o gia tuo', all((r['tetto'] is None) == (r['etichetta'] in ('fuori piano', 'tuo')) for r in righe))
t('alternative dello stesso ruolo e fuori dalla rosa del piano',
  all(E4[a]['ruolo'] == E4[r['k']]['ruolo'] and a not in P_['rosa'] for r in righe for a in r['alternative']))
t('i reparti seguono l ordine di chiamata', list(P_['reparti']) == ['P', 'D', 'C', 'A'])
# piu' attaccanti fuori rosa: uno quasi come A0 ma carissimo, due scarsi da 1 credito (i migliori per credito)
E7 = dict(E4, A3=G('A3', 'A', 8.2, prezzo=45), A4=G('A4', 'A', 5.0, prezzo=1), A5=G('A5', 'A', 4.9, prezzo=1))
P7 = piano_asta.piano(E7, forchette_finte(E7), Rm, 60, slot, vinc, candidati=4)
righe7 = [r for rep in P7['reparti'].values() for r in rep['bersagli'] + rep['altri']]


def _vic(k, a):
    return abs(E7[a]['mu'] * E7[a]['p'] - E7[k]['mu'] * E7[k]['p'])


def _alt_ok(r):
    fuori = [x for x in E7 if E7[x]['ruolo'] == E7[r['k']]['ruolo'] and x not in P7['rosa'] and x != r['k']]
    lim = max((_vic(r['k'], a) for a in r['alternative']), default=-1)
    return len(r['alternative']) == min(2, len(fuori)) and \
        all(_vic(r['k'], x) >= lim - 1e-12 for x in fuori if x not in r['alternative'])


t('alternative: i 2 fuori rosa piu vicini per valore (se lo perdi, vai su di loro)',
  all(_alt_ok(r) for r in righe7), [(r['k'], r['alternative']) for r in righe7 if not _alt_ok(r)])
coppie_A = {tuple(r['alternative']) for r in P7['reparti']['A']['bersagli'] + P7['reparti']['A']['altri']}
t('CONTROPROVA: non la stessa coppia per tutto il reparto', len(coppie_A) > 1, coppie_A)

t('i bersagli sono esattamente la rosa del piano',
  sorted(r['k'] for rep in P_['reparti'].values() for r in rep['bersagli']) == sorted(P_['rosa']))

# review finale: il piano usa lo scouting quando c'e' (spec par. 4) e lo scouting >= 0,3 apre la fascia media (par. 5)
def scheda_(nome, **kpi):
    return {'nome': nome, 'data': '2026-09-28', 'giornata': 5,
            'kpi': {k: {'voto': v, 'prova': 'p', 'fonte': 'f'} for k, v in kpi.items()}}


Es_, vs_ = piano_asta.con_scouting(E4, dict(vinc), {'A1': scheda_('A1', spazio=2, ruolo_tattico=2, contesto=2),
                                                     'A2': scheda_('A2', spazio=1)}, oggi='2026-09-30')
t('piano con scouting: le stime corrette entrano nel valore', Es_['A1']['mu'] > E4['A1']['mu']
  and 'scouting' in Es_['A1'].get('fonte', ''))
t('scouting >= 0.3 apre la fascia media, sotto no', 'A1' in vs_['scouting_ok'] and 'A2' not in vs_['scouting_ok'],
  vs_.get('scouting_ok'))
t('CONTROPROVA: senza schede niente cambia', piano_asta.con_scouting(E4, dict(vinc), {}, oggi='2026-09-30')[0] == E4)

print('\n[B5] asta live: termometro e ricalcolo')
stato = {'venduti': [{'nome': E4[stella]['nome'], 'prezzo': 2 * prezzi[stella], 'mio': False}], 'mio_budget': 60, 'miei': []}
t('termometro: pagato il doppio del previsto -> 2.0',
  abs(piano_asta.termometro(stato['venduti'], forchette_finte(E4), E4) - 2.0) < 1e-9)
t('termometro senza vendite = 1', piano_asta.termometro([], forchette_finte(E4), E4) == 1.0)
t('termometro tagliato fra 0.5 e 2', piano_asta.termometro(
  [{'nome': E4[stella]['nome'], 'prezzo': 100 * prezzi[stella], 'mio': False}], forchette_finte(E4), E4) == 2.0)
Pl = piano_asta.ricalcola(stato, E4, forchette_finte(E4), Rm, vinc, slot=slot, candidati=2)
t('venduto ad altri: mai nel piano', stella not in Pl['rosa'])
mio = {'venduti': [{'nome': E4[stella]['nome'], 'prezzo': 10, 'mio': True}], 'mio_budget': 50,
       'miei': [{'nome': E4[stella]['nome'], 'prezzo': 10}]}
Pm = piano_asta.ricalcola(mio, E4, forchette_finte(E4), Rm, vinc, slot=slot, candidati=2)
t('comprato da me: sempre nel piano, al prezzo pagato', stella in Pm['rosa'] and
  next(r for r in Pm['reparti']['A']['bersagli'] if r['k'] == stella)['forchetta'] == (10, 10, 10))
t('il budget del piano e il mio residuo + quanto ho gia speso', Pm['costo'] <= 60)
r_mio = next(r for r in Pm['reparti']['A']['bersagli'] if r['k'] == stella)
t('comprato da me: etichetta tuo, nessun tetto', r_mio['etichetta'] == 'tuo' and r_mio['tetto'] is None, r_mio)
t('CONTROPROVA: nel piano senza acquisti nessuno e tuo',
  all(r['etichetta'] != 'tuo' for rep in P_['reparti'].values() for r in rep['bersagli'] + rep['altri']))
# somma zero: chi strapaga brucia crediti -> il resto costa MENO (fanta.mercato, e i dati della lega)
Rl = regole.carica_lega(None, {'squadre': 2, 'budget': 60})
caro = {'venduti': [{'nome': E4[stella]['nome'], 'prezzo': 50, 'mio': False}], 'mio_budget': 60, 'miei': []}
scon = {'venduti': [{'nome': E4[stella]['nome'], 'prezzo': 1, 'mio': False}], 'mio_budget': 60, 'miei': []}
f_caro = piano_asta.fattore_residuo(caro, forchette_finte(E4), E4, Rl, slot)
f_scon = piano_asta.fattore_residuo(scon, forchette_finte(E4), E4, Rl, slot)
t('somma zero: se gli altri strapagano, il resto costera MENO', f_caro < 1.0, f'{f_caro:.2f}')
t('CONTROPROVA: se comprano a sconto, il resto costera DI PIU', f_scon > f_caro, f'{f_scon:.2f} vs {f_caro:.2f}')
# nomi scritti a mano nello stato live (review finale): "Gonzalez" deve trovare "Gonzalez N."
Eg = dict(E4, **{'gonzalez n': dict(G('gonzalez n', 'A', 9.5, prezzo=5.0), nome='Gonzalez N.')})
Pg = piano_asta.ricalcola({'venduti': [{'nome': 'Gonzalez', 'prezzo': 9, 'mio': False},
                                       {'nome': 'Sconosciuto X.', 'prezzo': 3, 'mio': False}], 'mio_budget': 60},
                          Eg, forchette_finte(Eg), Rm, vinc, slot=slot, candidati=0, partenze=1)
t('live: nome parziale ("Gonzalez") trovato se unico, e mai piu proposto', 'gonzalez n' not in Pg['rosa'] and
  all(r['k'] != 'gonzalez n' and 'gonzalez n' not in r['alternative']
      for rep in Pg['reparti'].values() for r in rep['bersagli'] + rep['altri']))
t('live: nome non riconosciuto di un avversario -> dichiarato', Pg.get('ignoti') == ['Sconosciuto X.'], Pg.get('ignoti'))
try:
    piano_asta.ricalcola({'venduti': [{'nome': 'Sconosciuto X.', 'prezzo': 3, 'mio': True}], 'mio_budget': 57},
                         Eg, forchette_finte(Eg), Rm, vinc, slot=slot, candidati=0, partenze=1)
    ok = False
except ValueError as e:
    ok = 'Sconosciuto X.' in str(e)
t('live: un MIO acquisto non riconosciuto ferma il piano e lo nomina (non libera uno slot finto)', ok)
# live veloce (review finale): i tetti solo per il reparto in chiamata
portieri_miei = sorted(k for k in E4 if E4[k]['ruolo'] == 'P')[:slot['P']]
Pv = piano_asta.ricalcola({'venduti': [{'nome': k, 'prezzo': 1, 'mio': True} for k in portieri_miei],
                           'mio_budget': 60 - len(portieri_miei)},
                          E4, forchette_finte(E4), Rm, vinc, slot=slot, candidati=3, partenze=1)
t('live: tetti solo nel primo reparto ancora aperto (D), gli altri "dopo"',
  Pv['reparto_aperto'] == 'D'
  and all(r['tetto'] is not None for r in Pv['reparti']['D']['bersagli'])
  and all(r['tetto'] is None for x in 'CA' for r in Pv['reparti'][x]['bersagli'] + Pv['reparti'][x]['altri'])
  and all(r['etichetta'] == 'dopo' for x in 'CA' for r in Pv['reparti'][x]['bersagli']),
  [(x, r['k'], r['etichetta']) for x in 'CA' for r in Pv['reparti'][x]['bersagli'] + Pv['reparti'][x]['altri']])
# fine asta (review finale): 9 crediti e 5 slot, i rimasti costano 1. La somma zero non deve
# alzare il credito minimo, ne' portarlo sotto 1
Ef = {'star': G('star', 'A', 8.5, prezzo=30)}
for r_ in 'PDCA':
    for i in range(6):
        Ef[f'{r_}{i}'] = G(f'{r_}{i}', r_, 5.5 + .1 * i, p=0.8, prezzo=1.0)
Ff = forchette_finte(Ef)
fine = {'mio_budget': 9, 'venduti': [{'nome': 'star', 'prezzo': 51, 'mio': True},
                                     {'nome': 'A5', 'prezzo': 1, 'mio': False}]}
try:
    Pf = piano_asta.ricalcola(fine, Ef, Ff, Rl, {}, slot=slot, candidati=0, partenze=2)
    ok = len(Pf['rosa']) == sum(slot.values()) and Pf['costo'] <= 60
except ValueError as e:
    ok, Pf = False, str(e)
t('fine asta con pochi crediti: il piano chiude la rosa coi giocatori da 1, non fallisce', ok, Pf)
Rsc = regole.carica_lega(None, {'squadre': 2, 'budget': 60})
molti = {'venduti': [{'nome': E4[stella]['nome'], 'prezzo': 55, 'mio': False}], 'mio_budget': 60}
f_m = piano_asta.fattore_residuo(molti, forchette_finte(E4), E4, Rsc, slot)
Pm2 = piano_asta.ricalcola(molti, E4, forchette_finte(E4), Rsc, vinc, slot=slot, candidati=0, partenze=1)
minimi = [g['forchetta'][0] for rep in Pm2['reparti'].values() for g in rep['bersagli'] + rep['altri']]
t('CONTROPROVA: con fattore sotto 1 nessun prezzo scende sotto 1 credito', f_m < 1 and min(minimi) >= 1.0,
  (f_m, min(minimi)))

print('\n[B6] rigiocare l asta con i soli dati di agosto')
acq = [dict(k=k, nome=E4[k]['nome'], ruolo=E4[k]['ruolo'], squadra='', fvm=10.0, quota=None,
            pagato=prezzi[k] if i % 2 else None, fantasquadra='Altri' if i % 2 else None) for i, k in enumerate(E4)]
rg = piano_asta.rigioca(acq, E4, forchette_finte(E4), Rm, vinc, slot=slot)
t('rosa completa e budget mai negativo', len(rg['rosa']) == 6 and rg['speso'] <= Rm['budget'], str(rg))
t('ogni decisione e nel log: preso, perso o libero',
  rg['log'] and all(('preso' in x) or ('perso' in x) or ('libero' in x) for x in rg['log']), str(rg['log']))
t('un giocatore mai comprato si prende a 1', all(x.endswith(' 1') for x in rg['log'] if x.startswith('libero')))
caro = [dict(a, pagato=1000.0, fantasquadra='Altri') if a['k'] == stella else a for a in acq]
rgc = piano_asta.rigioca(caro, E4, forchette_finte(E4), Rm, vinc, slot=slot)
t('CONTROPROVA: chi e stato pagato piu del tetto si perde, e si passa oltre',
  stella not in rgc['rosa'] and any(x.startswith('perso ' + E4[stella]['nome']) for x in rgc['log']), str(rgc['log']))
import inspect  # noqa: E402
t('il rigioco non puo leggere dati 2026/27: la firma non li prende',
  not {'S', 'voti', 'tabella', 'records'} & set(inspect.signature(piano_asta.rigioca).parameters))

print('\n[B7] socio.py asta: piano, rigioco, file mancanti')
import json  # noqa: E402
lega_b7 = os.path.join(tmp, 'lega_b7')
os.makedirs(lega_b7)
rng7 = random.Random(7)
righe_l = [['Nome', 'Ruolo', 'Squadra', 'Quotazione', 'FVM', 'Fantamedia', 'Presenze']]
righe_p = [['FantaSquadra', 'Nome', 'Ruolo', 'Pagato', 'FVM']]
for r, n in (('P', 7), ('D', 18), ('C', 18), ('A', 14)):
    for i in range(n):
        fvm = max(1, int(120 * (1 - i / n) ** 2))
        nome = f'{r}Gioc{i:02d}'
        righe_l.append([nome, r, f'T{i % 10:02d}', max(1, fvm // 5), fvm, f'{5.5 + 2 * (1 - i / n):.2f}', 20 + i % 15])
        if i % 2 == 0:
            righe_p.append(['Altri' if i % 4 else 'Mia', nome, r, max(1, int(fvm * 0.4 * rng7.uniform(0.7, 1.3))), fvm])
scrivi_csv(os.path.join(lega_b7, 'listone.csv'), righe_l)
scrivi_csv(os.path.join(lega_b7, 'prezzi.csv'), righe_p)
json.dump({'mia': 'Mia', 'squadre': 2, 'file': {'listone': 'listone.csv', 'prezzi': 'prezzi.csv'},
           'asta': {'portieri_max': 40}}, open(os.path.join(lega_b7, 'lega.json'), 'w'))
rc, out = lancia('socio.py', '--lega', os.path.join(lega_b7, 'lega.json'), 'asta', '--candidati', '2')
pos = [out.find(f'REPARTO {r}') for r in 'PDCA']
t('socio asta: il piano esce reparto per reparto nell ordine di chiamata',
  rc == 0 and all(x >= 0 for x in pos) and pos == sorted(pos), out[-600:])
t('socio asta: ogni candidato ha un etichetta', rc == 0 and any(e in out for e in ('affare', 'da giocare', 'lascia')))
rc, out = lancia('socio.py', '--lega', os.path.join(lega_b7, 'lega.json'), 'asta', '--rigioca')
t('socio asta --rigioca: log delle decisioni e confronto con la rosa vera',
  rc == 0 and 'CONFRONTO' in out and ('preso' in out or 'libero' in out), out[-600:])
t('socio asta --rigioca: dichiara che le forchette sono tarate sulla stessa asta (ottimismo in piu)',
  'stessa asta' in out, out[:900])
json.dump({'mia': 'Mia', 'file': {'listone': 'manca.csv', 'prezzi': 'prezzi.csv'}},
          open(os.path.join(lega_b7, 'lega_rotta.json'), 'w'))
rc, out = lancia('socio.py', '--lega', os.path.join(lega_b7, 'lega_rotta.json'), 'asta')
t('socio asta senza listone: messaggio, codice di errore, niente traceback',
  rc != 0 and 'Traceback' not in out and 'listone' in out, out[-300:])

# ================================================== esito
print('\n' + '=' * 74)
gravi = sum(1 for _, _, g in KO if g)
print(f'  RISULTATO: {len(OK)}/{len(OK) + len(KO)} pass   .   {len(KO)} FAIL ({gravi} gravi)')
sys.exit(1 if KO else 0)
