# -*- coding: utf-8 -*-
"""qa_socio - le invarianti del socio di stagione, ognuna con la sua controprova.

Stesso patto di qa_fanta.py: la domanda non e' "funziona?" ma "se rompo il
codice, questo test se ne accorge?". Dati sintetici, nomi finti apposta.
"""
import csv
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import regole  # noqa: E402

OK, KO = [], []


def t(nome, cond, dettaglio='', grave=False):
    (OK if cond else KO).append((nome, dettaglio, grave))
    print(f'  {"ok  " if cond else "FAIL"} {nome}' + (f'   [{dettaglio}]' if not cond and dettaglio else ''))


def scrivi_csv(path, righe, sep=';'):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        csv.writer(f, delimiter=sep).writerows(righe)
    return path


tmp = tempfile.mkdtemp(prefix='socio_qa_')
R = regole.carica_lega(None)

# ================================================== 1. regole
print('\n[1] regole: fantavoto, fasce gol, modificatore, cartellini')

base = {'voto': 6.5, 'gf': 1, 'gs': 0, 'rp': 0, 'rs': 0, 'rf': 0, 'au': 0,
        'amm': 1, 'esp': 0, 'ass': 1}
t('fantavoto = voto + bonus - malus', regole.fantavoto(base, 'A', R) == 6.5 + 3 + 1 - 0.5,
  str(regole.fantavoto(base, 'A', R)), grave=True)
t('senza voto non c e fantavoto (non e uno zero)',
  regole.fantavoto(dict(base, voto=None), 'A', R) is None, grave=True)
por = dict(base, gf=0, ass=0, amm=0, gs=2, rp=1)
t('portiere: -1 per gol subito, +3 per rigore parato',
  regole.fantavoto(por, 'P', R) == 6.5 - 2 + 3, str(regole.fantavoto(por, 'P', R)), grave=True)
t('CONTROPROVA: il gol subito NON pesa sui difensori',
  regole.fantavoto(dict(por, rp=0), 'D', R) == 6.5, grave=True)

R_inv = regole.carica_lega(None, {'bonus': {'porta_inviolata': 1}})
t('porta inviolata solo se attivata in lega.json',
  regole.fantavoto(dict(por, gs=0, rp=0), 'P', R_inv) == 7.5
  and regole.fantavoto(dict(por, gs=0, rp=0), 'P', R) == 6.5, grave=True)
R_dif = regole.carica_lega(None, {'bonus': {'gol': {'D': 4.5}}})
t('bonus gol per ruolo configurabile senza perdere gli altri default',
  regole.fantavoto(dict(base, amm=0, ass=0), 'D', R_dif) == 11.0
  and R_dif['bonus']['gol']['A'] == 3, grave=True)

t('65.5 punti = 0 gol', regole.gol(65.5, R) == 0, grave=True)
t('66 punti = 1 gol (la soglia e inclusa)', regole.gol(66, R) == 1, grave=True)
t('71.5 = 1 gol, 72 = 2 gol, 84 = 4 gol',
  (regole.gol(71.5, R), regole.gol(72, R), regole.gol(84, R)) == (1, 2, 4),
  str((regole.gol(71.5, R), regole.gol(72, R), regole.gol(84, R))), grave=True)
R_tab = regole.carica_lega(None, {'soglie': [66, 72, 77, 81, 85, 89]})
t('fasce a tabella esplicita (72,77,81...) rispettate',
  (regole.gol(76.5, R_tab), regole.gol(77, R_tab), regole.gol(95, R_tab)) == (2, 3, 7),
  str((regole.gol(76.5, R_tab), regole.gol(77, R_tab), regole.gol(95, R_tab))))

t('modificatore: media 5.99 -> 0',
  regole.modificatore(6.0, [6.0, 6.0, 5.96, 5.0], R) == 0, grave=True)
t('modificatore: media 6.00 -> +1', regole.modificatore(6.0, [6.0, 6.0, 6.0, 4.0], R) == 1, grave=True)
t('modificatore: 6.49 -> +1, 6.50 -> +3, 7.00 -> +6',
  (regole.modificatore(6.5, [6.5, 6.5, 6.46, 5], R),
   regole.modificatore(6.5, [6.5, 6.5, 6.5, 5], R),
   regole.modificatore(7.0, [7, 7, 7, 5], R)) == (1, 3, 6), grave=True)
t('modificatore: usa i 3 MIGLIORI difensori, non i primi tre',
  regole.modificatore(7.0, [5.0, 7.0, 7.0, 7.0], R) == 6, grave=True)
t('CONTROPROVA: con 3 difensori il modificatore non scatta',
  regole.modificatore(7.0, [7.0, 7.0, 7.0], R) == 0, grave=True)
t('senza portiere a referto il modificatore non scatta',
  regole.modificatore(None, [7.0, 7.0, 7.0, 7.0], R) == 0)
R_nomod = regole.carica_lega(None, {'modificatore': {'attivo': False}})
t('modificatore spento da lega.json', regole.modificatore(7.0, [7] * 4, R_nomod) == 0)

t('moduli: 3-4-3 -> P1 D3 C4 A3',
  regole.modulo('3-4-3') == {'P': 1, 'D': 3, 'C': 4, 'A': 3}, grave=True)
t('ogni modulo di default fa 11 giocatori',
  all(sum(regole.modulo(m).values()) == 11 for m in R['moduli']), grave=True)

t('4 gialli = diffidato, 5 = squalificato, 6 = pulito',
  [regole.cartellini(n) for n in (3, 4, 5, 6)] == ['', 'diffidato', 'squalificato', ''],
  str([regole.cartellini(n) for n in (3, 4, 5, 6)]), grave=True)
t('soglie successive: 9 diffidato, 10 squalificato, 13 diffidato, 14 squalificato',
  [regole.cartellini(n) for n in (9, 10, 13, 14)]
  == ['diffidato', 'squalificato', 'diffidato', 'squalificato'])

lj = os.path.join(tmp, 'lega.json')
json.dump({'formula': 'punti', 'squadre': 8, 'soglie': {'prima': 60, 'passo': 4}},
          open(lj, 'w', encoding='utf-8'))
R_file = regole.carica_lega(lj)
t('lega.json sovrascrive solo cio che dichiara',
  R_file['formula'] == 'punti' and R_file['squadre'] == 8 and regole.gol(64, R_file) == 2
  and R_file['bonus']['assist'] == R['bonus']['assist'], grave=True)

# ================================================== 2. nomi e voti
import nomi  # noqa: E402
import voti  # noqa: E402
print('\n[2] nomi comuni e archivio voti della stagione')

t('squadra: sigla, nome esteso e prefisso societario -> stessa chiave',
  nomi.squadra('MIL') == nomi.squadra('AC Milan') == nomi.squadra('Milan')
  and nomi.squadra('Parma Calcio 1913') == nomi.squadra('PAR')
  and nomi.squadra('Hellas Verona') == nomi.squadra('Verona'), grave=True)
t('CONTROPROVA: squadre sconosciute NON collassano sulle prime tre lettere',
  nomi.squadra('Team01') != nomi.squadra('Team02'), grave=True)
t('giocatore: accenti e maiuscole non contano',
  nomi.giocatore('Soulé M.') == nomi.giocatore('soule m.'), grave=True)

# Formato Fantacalcio.it: righe di titolo, riga-squadra, "6*" = senza voto.
g3 = scrivi_csv(os.path.join(tmp, 'voti_giornata_3.csv'), [
    ['Voti Fantacalcio - Giornata 3'],
    [],
    ['Cod.', 'Ruolo', 'Nome', 'Voto', 'Gf', 'Gs', 'Rp', 'Rs', 'Rf', 'Au', 'Amm', 'Esp', 'Ass'],
    ['ATALANTA'],
    ['1', 'P', 'Portiere A.', '6', '0', '2', '1', '0', '0', '0', '0', '0', '0'],
    ['2', 'A', 'Punta B.', '7,5', '2', '0', '0', '0', '0', '0', '1', '0', '1'],
    ['3', 'C', 'Mezzala C.', '6*', '0', '0', '0', '0', '0', '0', '0', '0', '0'],
    ['INTER'],
    ['4', 'D', 'Terzino D.', '5.5', '0', '0', '0', '0', '0', '0', '0', '1', '0'],
])
L = voti.leggi_giornata(g3, R=R)
t('legge solo le righe-giocatore (4), salta titoli e righe-squadra',
  len(L) == 4, str(len(L)), grave=True)
t('giornata dedotta dal nome del file', all(r['giornata'] == 3 for r in L), grave=True)
t('squadra presa dalla riga-squadra che precede',
  [nomi.squadra(r['squadra']) for r in L] == [nomi.squadra('Atalanta')] * 3 + [nomi.squadra('Inter')],
  grave=True)
sv = next(r for r in L if r['nome'] == 'Mezzala C.')
t('"6*" = senza voto: voto None, fantavoto None', sv['voto'] is None and sv['fv'] is None, grave=True)
pb = next(r for r in L if r['nome'] == 'Punta B.')
t('virgola decimale e fantavoto calcolato con le regole della lega',
  pb['voto'] == 7.5 and pb['fv'] == 7.5 + 6 + 1 - 0.5, str(pb['fv']), grave=True)

g4 = scrivi_csv(os.path.join(tmp, 'g4.csv'), [
    ['Giornata', 'Nome', 'Ruolo', 'Squadra', 'Voto', 'Gf', 'Gs', 'Ass', 'Amm', 'Esp'],
    ['4', 'Portiere A.', 'P', 'Atalanta', '6.5', '0', '0', '0', '0', '0'],
    ['4', 'Punta B.', 'A', 'Atalanta', '6', '0', '0', '0', '1', '0'],
    ['4', 'Mezzala C.', 'C', 'Atalanta', '6.5', '0', '0', '0', '0', '0'],
])
S = voti.stagione(voti.leggi_giornata(g3, R=R) + voti.leggi_giornata(g4, R=R))
t('formato alternativo (colonna Giornata, squadra per riga) accettato',
  S['giornate'] == [3, 4], str(S['giornate']), grave=True)
pb = S['giocatori'][nomi.giocatore('Punta B.')]
t('presenze = partite CON voto', pb['presenze'] == 2, grave=True)
mz = S['giocatori'][nomi.giocatore('Mezzala C.')]
t('CONTROPROVA: il senza voto NON e una presenza', mz['presenze'] == 1, str(mz['presenze']), grave=True)
t('gialli sommati sulla stagione', pb['gialli'] == 2, grave=True)
td = S['giocatori'][nomi.giocatore('Terzino D.')]
t('espulsione registrata con la giornata', td['espulso_in'] == 3, grave=True)
t('partite giocate dalla squadra contate per squadra',
  S['partite_squadra'][nomi.squadra('Atalanta')] == 2
  and S['partite_squadra'][nomi.squadra('Inter')] == 1, str(S['partite_squadra']))

cart = os.path.join(tmp, 'voti')
os.makedirs(cart)
for src in (g3, g4):
    os.replace(src, os.path.join(cart, os.path.basename(src)))
# stessa giornata ricaricata (file riscaricato): non deve contare doppio
shutil.copy(os.path.join(cart, 'g4.csv'), os.path.join(cart, 'g4_bis.csv'))
S2 = voti.stagione(voti.archivio(cart, R=R))
t('la stessa giornata caricata due volte NON conta doppio',
  S2['giocatori'][nomi.giocatore('Punta B.')]['presenze'] == 2, grave=True)

# ================================================== 3. calendario
import calendario  # noqa: E402
print('\n[3] calendario: forza delle squadre, difficolta, griglia portieri')

cal_csv = scrivi_csv(os.path.join(tmp, 'calendario.csv'), [
    ['Giornata', 'Casa', 'Trasferta', 'GolCasa', 'GolTrasferta'],
    ['1', 'Alfa', 'Delta', '3', '0'], ['1', 'Beta', 'Gamma', '1', '1'],
    ['2', 'Delta', 'Beta', '0', '2'], ['2', 'Gamma', 'Alfa', '0', '2'],
    ['3', 'Alfa', 'Beta', '2', '0'], ['3', 'Gamma', 'Delta', '2', '1'],
    ['4', 'Delta', 'Alfa', '', ''], ['4', 'Gamma', 'Beta', '', ''],
    ['5', 'Beta', 'Alfa', '', ''], ['5', 'Delta', 'Gamma', '', ''],
])
P_ = calendario.carica(cal_csv)
t('legge 10 partite, 6 giocate e 4 da giocare',
  len(P_) == 10 and sum(1 for p in P_ if p['giocata']) == 6, grave=True)
t('prossima giornata = la prima con partite non giocate', calendario.prossima(P_) == 4, grave=True)
F = calendario.forze(P_)
a, d = F['squadre'][nomi.squadra('Alfa')], F['squadre'][nomi.squadra('Delta')]
t('chi segna tanto ha attacco > 1, chi subisce poco difesa < 1',
  a['att'] > 1 and a['dif'] < 1, str(a), grave=True)
t('e il contrario per chi perde', d['att'] < 1 and d['dif'] > 1, str(d), grave=True)
t('shrinkage: 3 partite non bastano per valori estremi',
  0.5 < a['dif'] < 1 and 1 < a['att'] < 2, str(a))
F0 = calendario.forze([dict(p, giocata=False) for p in P_])
t('CONTROPROVA: senza risultati tutte le squadre valgono 1 e lo si dichiara',
  all(v['att'] == 1 and v['dif'] == 1 for v in F0['squadre'].values())
  and 'nessun' in F0['fonte'], F0['fonte'], grave=True)

xg_casa = calendario.xg('Beta', 'Gamma', True, F)
xg_fuori = calendario.xg('Beta', 'Gamma', False, F)
t('fattore campo: stessa partita, in casa si segna di piu', xg_casa > xg_fuori, grave=True)
t('contro una difesa peggiore si segna di piu',
  calendario.xg('Beta', 'Delta', True, F) > calendario.xg('Beta', 'Alfa', True, F), grave=True)
t('partita di una squadra in una giornata: avversario e campo',
  calendario.partita(P_, 'Alfa', 4) == (nomi.squadra('Delta'), False), grave=True)
t('nessuna partita -> None, non un avversario inventato',
  calendario.partita(P_, 'Alfa', 9) is None)

# Griglia portieri: due squadre con calendari complementari (una ha il match
# facile quando l'altra ha il difficile) battono due squadre col calendario uguale.
Fg = {'squadre': {nomi.squadra(x): {'att': v, 'dif': 1.0} for x, v in
                  (('Top', 2.0), ('Low', 0.5), ('P1', 1.0), ('P2', 1.0), ('P3', 1.0))},
      'media': 1.3, 'casa': 1.0, 'fonte': 'test'}
cg = []
for gg in range(1, 7):
    forte, debole = ('Top', 'Low') if gg % 2 else ('Low', 'Top')
    cg += [{'giornata': gg, 'casa': nomi.squadra('P1'), 'trasferta': nomi.squadra(forte), 'giocata': False},
           {'giornata': gg, 'casa': nomi.squadra('P2'), 'trasferta': nomi.squadra(debole), 'giocata': False},
           {'giornata': gg, 'casa': nomi.squadra('P3'), 'trasferta': nomi.squadra(forte), 'giocata': False}]
gr = calendario.griglia(cg, Fg, ['P1', 'P2', 'P3'], range(1, 7))
coppie = {frozenset(c['coppia']): c['gs_attesi'] for c in gr}
t('griglia: la coppia complementare subisce meno della coppia gemella',
  coppie[frozenset([nomi.squadra('P1'), nomi.squadra('P2')])]
  < coppie[frozenset([nomi.squadra('P1'), nomi.squadra('P3')])], str(coppie), grave=True)
t('CONTROPROVA: la coppia gemella vale quanto una squadra sola',
  abs(coppie[frozenset([nomi.squadra('P1'), nomi.squadra('P3')])]
      - sum(calendario.xg('Top' if gg % 2 else 'Low', 'P1', False, Fg) for gg in range(1, 7))) < 1e-9)

# ================================================== 4. proiezioni
import proiezioni  # noqa: E402
print('\n[4] proiezioni: shrinkage, probabilita di giocare, squalifiche')


def rec(g, nome, ruolo, voto, sq='Alfa', **kw):
    r = {'giornata': g, 'nome': nome, 'ruolo': ruolo, 'squadra': sq, 'voto': voto}
    for k in ('gf', 'gs', 'rp', 'rs', 'rf', 'au', 'amm', 'esp', 'ass'):
        r[k] = kw.get(k, 0)
    r['fv'] = regole.fantavoto(r, ruolo, R)
    return r


arch = []
for gg in range(1, 11):
    arch.append(rec(gg, 'Costante C.', 'C', 6.5, ass=1))                  # fv 7.5 per 10 volte
    arch.append(rec(gg, 'Panchinaro P.', 'C', None if gg > 1 else 6.0, gf=2 if gg == 1 else 0))
    for i in range(6):
        arch.append(rec(gg, f'Riempitivo{i} R.', 'C', 6.0 + 0.1 * i))
arch.append(rec(10, 'Rosso R.', 'D', 5.0, esp=1))
for gg in range(6, 10):
    arch.append(rec(gg, 'Giallo G.', 'D', 6.0, amm=1))                    # 4 gialli: diffidato
arch.append(rec(10, 'Squalif S.', 'D', 6.0, amm=1))
for gg in range(1, 5):
    arch.append(rec(gg, 'Squalif S.', 'D', 6.0, amm=1))                   # 5o giallo alla 10
S = voti.stagione(arch)
E = proiezioni.stima(S=S, R=R)
cst, pan = E[nomi.giocatore('Costante C.')], E[nomi.giocatore('Panchinaro P.')]
t('una partita da 12 NON batte dieci partite da 7.5 (shrinkage)',
  cst['mu'] > pan['mu'], f"{cst['mu']:.2f} vs {pan['mu']:.2f}", grave=True)
t('ma la partita da 12 alza comunque la stima sopra la media di ruolo',
  pan['mu'] > E['_ruoli']['C']['mu'], grave=True)
t('dieci partite spostano la stima quasi fino al dato',
  abs(cst['mu'] - 7.5) < abs(pan['mu'] - 12.0) and cst['mu'] > 7.0, f"{cst['mu']:.2f}", grave=True)
t('chi gioca sempre ha probabilita alta, chi ha giocato 1 su 10 bassa',
  cst['p'] > 0.8 and pan['p'] < 0.3, f"{cst['p']:.2f} / {pan['p']:.2f}", grave=True)
t('la dispersione non e mai zero, neanche con dieci voti identici', cst['sd'] > 0.3, f"{cst['sd']:.2f}")

tit = {nomi.giocatore('Panchinaro P.'), nomi.giocatore('Rosso R.')}
Et = proiezioni.stima(S=S, R=R, titolari=tit)
t('con le probabili: nell XI 0.9, fuori 0.15 (osservato batte storico)',
  Et[nomi.giocatore('Panchinaro P.')]['p'] == proiezioni.P_XI
  and Et[nomi.giocatore('Costante C.')]['p'] == proiezioni.P_FUORI, grave=True)
t('espulso all ultima giornata: probabilita 0 anche se e nelle probabili',
  Et[nomi.giocatore('Rosso R.')]['p'] == 0 and Et[nomi.giocatore('Rosso R.')]['stato'] == 'squalificato',
  grave=True)
t('quinto giallo all ultima giornata: squalificato',
  E[nomi.giocatore('Squalif S.')]['stato'] == 'squalificato' and E[nomi.giocatore('Squalif S.')]['p'] == 0,
  grave=True)
Ef = proiezioni.stima(S=S, R=R, prossima=False)
t('la squalifica vale UNA giornata: per le successive il giocatore torna disponibile',
  Ef[nomi.giocatore('Rosso R.')]['p'] > 0 and Ef[nomi.giocatore('Squalif S.')]['p'] > 0, grave=True)
t('quattro gialli: diffidato, ma gioca', E[nomi.giocatore('Giallo G.')]['stato'] == 'diffidato'
  and E[nomi.giocatore('Giallo G.')]['p'] > 0, grave=True)

# prior dal listone: chi non ha ancora giocato non vale la media di ruolo se
# l'anno scorso faceva 7.5
listone = [{'nome': 'Nuovo N.', 'ruolo': 'A', 'squadra': 'Beta', 'quota': 30, 'fm': 7.8, 'mv': 6.6, 'pres': 32},
           {'nome': 'Scarso S.', 'ruolo': 'A', 'squadra': 'Beta', 'quota': 2, 'fm': 5.8, 'mv': 5.8, 'pres': 30},
           {'nome': 'Arrivato A.', 'ruolo': 'A', 'squadra': 'Beta', 'quota': 28, 'fm': None, 'mv': None, 'pres': None}]
listone += [{'nome': f'Medio{i} M.', 'ruolo': 'A', 'squadra': 'Beta', 'quota': 5 + i, 'fm': 6.2 + 0.05 * i,
             'mv': 6.0, 'pres': 25} for i in range(8)]
El = proiezioni.stima(S=None, listone=listone, R=R)
t('senza stagione, il prior viene dalla fantamedia dell anno scorso',
  El[nomi.giocatore('Nuovo N.')]['mu'] > El[nomi.giocatore('Scarso S.')]['mu'] + 1, grave=True)
t('chi arriva senza storico prende il prior dalla quotazione (percentile nel ruolo)',
  El[nomi.giocatore('Arrivato A.')]['mu'] > El['_ruoli']['A']['mu'],
  f"{El[nomi.giocatore('Arrivato A.')]['mu']:.2f} vs media {El['_ruoli']['A']['mu']:.2f}", grave=True)
t('ogni stima dichiara da dove viene', El[nomi.giocatore('Arrivato A.')]['fonte'] == 'quotazione'
  and El[nomi.giocatore('Nuovo N.')]['fonte'] == 'listone')

# matchup: l'attaccante contro la difesa peggiore vale di piu, il portiere
# che affronta l'attacco migliore vale di meno
Em = {'x': dict(mu=8.0, mv=6.5, sd=2.0, sd_v=0.6, p=0.9, ruolo='A', squadra=nomi.squadra('Beta'), nome='X'),
      'y': dict(mu=5.0, mv=6.0, sd=1.3, sd_v=0.6, p=0.9, ruolo='P', squadra=nomi.squadra('Beta'), nome='Y')}
g4_ = proiezioni.per_giornata(Em, P_, F, 4, R)      # Beta in trasferta a Gamma
g5_ = proiezioni.per_giornata(Em, P_, F, 5, R)      # Beta in casa con Alfa (fortissima)
t('attaccante: la partita facile vale piu di quella difficile',
  g4_['x']['mu'] > g5_['x']['mu'], f"{g4_['x']['mu']:.2f} vs {g5_['x']['mu']:.2f}", grave=True)
t('la correzione tocca solo i bonus: il voto base resta', g4_['x']['mv'] == 6.5)
t('portiere contro l attacco piu forte perde punti attesi',
  g5_['y']['mu'] < Em['y']['mu'], f"{g5_['y']['mu']:.2f}", grave=True)
t('CONTROPROVA: le stime originali non vengono modificate', Em['x']['mu'] == 8.0, grave=True)

arch_top = [rec(gg, 'Fenomeno F.', 'C', 7.0, gf=1) for gg in range(1, 11)]
Et2 = proiezioni.stima(S=voti.stagione(arch + arch_top), R=R)
t('CONTROPROVA del taglio delle code: dieci partite da 10 restano sopra dieci da 7.5',
  Et2[nomi.giocatore('Fenomeno F.')]['mu'] > Et2[nomi.giocatore('Costante C.')]['mu'] + 1,
  f"{Et2[nomi.giocatore('Fenomeno F.')]['mu']:.2f}", grave=True)

# ================================================== 5. schiera
import schiera  # noqa: E402
print('\n[5] schiera: formazione, panchina, simulazione, rischio')


def G(k, ruolo, mu, p=1.0, sd=1.0, mv=None, sd_v=0.4):
    return {'k': k, 'nome': k, 'ruolo': ruolo, 'mu': mu, 'p': p, 'sd': sd,
            'mv': mv if mv is not None else min(mu, 6.5), 'sd_v': sd_v, 'stato': ''}


a_, b_, c_ = G('a', 'A', 9, p=0.3), G('b', 'A', 7, p=0.6), G('c', 'A', 5, p=0.9)
atteso = 0.3 * 9 + 0.7 * 0.6 * 7 + 0.7 * 0.4 * 0.9 * 5
t('valore di ruolo = esatto (primo che gioca, nell ordine)',
  abs(schiera.valore_ruolo([a_, b_, c_], 1) - atteso) < 1e-9,
  f'{schiera.valore_ruolo([a_, b_, c_], 1):.4f} vs {atteso:.4f}', grave=True)
t('con tutti sicuri = somma dei migliori k',
  abs(schiera.valore_ruolo([G('x', 'A', 8), G('y', 'A', 7), G('z', 'A', 6)], 2) - 15) < 1e-9, grave=True)


def rosa_base():
    r = [G('P1', 'P', 5.5, mv=6.2), G('P2', 'P', 4.8, mv=6.0), G('P3', 'P', 4.0, mv=5.8)]
    r += [G(f'D{i}', 'D', 6.8 - 0.2 * i, mv=6.3 - 0.05 * i) for i in range(8)]
    r += [G(f'C{i}', 'C', 7.2 - 0.25 * i, mv=6.2) for i in range(8)]
    r += [G(f'A{i}', 'A', 8.0 - 0.4 * i, mv=6.2) for i in range(6)]
    return r


RS = rosa_base()
f = schiera.formazione(RS, '3-4-3', R)
cont = {r: sum(1 for g in f['titolari'] if g['ruolo'] == r) for r in 'PDCA'}
t('rispetta il modulo', cont == {'P': 1, 'D': 3, 'C': 4, 'A': 3}, str(cont), grave=True)
ids = [g['k'] for g in f['titolari'] + f['panchina']]
t('nessun giocatore due volte, panchina fuori dai titolari', len(ids) == len(set(ids)), grave=True)
t('panchina lunga quanto la lega', len(f['panchina']) == R['panchina'], str(len(f['panchina'])))
t('in panchina c e un portiere', any(g['ruolo'] == 'P' for g in f['panchina']), grave=True)
t('titolari = i migliori per ruolo',
  {g['k'] for g in f['titolari'] if g['ruolo'] == 'A'} == {'A0', 'A1', 'A2'}, grave=True)

RS2 = rosa_base()
next(g for g in RS2 if g['k'] == 'A0')['p'] = 0.0
next(g for g in RS2 if g['k'] == 'A0')['stato'] = 'squalificato'
best = schiera.consiglia(RS2, R, n=600)['migliore']
t('lo squalificato non parte titolare',
  'A0' not in {g['k'] for g in best['titolari']}, grave=True)

# simulazione: con sd minuscola e tutti sicuri, la media torna al conto a mano
fisso = [dict(g, sd=0.01, sd_v=0.01) for g in rosa_base()]
f433 = schiera.formazione(fisso, '4-3-3', R)
E_ = schiera.estrazioni(fisso, 300, seme=3)
tot = schiera.punteggi(f433, E_, R)
mano = sum(g['mu'] for g in f433['titolari'])
mv_d = sorted((g['mv'] for g in f433['titolari'] if g['ruolo'] == 'D'), reverse=True)[:3]
mano += regole.modificatore(next(g['mv'] for g in f433['titolari'] if g['ruolo'] == 'P'), mv_d + [0] , R)
t('simulazione deterministica = somma dei fantavoti + modificatore',
  abs(sum(tot) / len(tot) - mano) < 0.1, f'{sum(tot) / len(tot):.2f} vs {mano:.2f}', grave=True)

# sostituzioni: 4 titolari che non giocano mai, tetto 3 cambi
buchi = [dict(g, sd=0.01, sd_v=0.01) for g in rosa_base()]
f_ = schiera.formazione(buchi, '3-4-3', R)
for g in f_['titolari']:
    if g['ruolo'] == 'C':
        g['p'] = 0.0
E_ = schiera.estrazioni(buchi, 200, seme=5)
tot = schiera.punteggi(f_, E_, R)
panch_c = [g for g in f_['panchina'] if g['ruolo'] == 'C']
t('entrano al massimo 3 dalla panchina, anche se ne mancano 4',
  abs(sum(tot) / len(tot) - (sum(g['mu'] for g in f_['titolari'] if g['ruolo'] != 'C')
                              + sum(g['mu'] for g in panch_c[:3]))) < 0.2 or len(panch_c) < 3,
  f'{sum(tot) / len(tot):.2f}', grave=True)
R5 = regole.carica_lega(None, {'max_sostituzioni': 5, 'panchina': 12})
buchi5 = [dict(g, sd=0.01, sd_v=0.01) for g in rosa_base()]   # copie nuove: niente alias
f5 = schiera.formazione(buchi5, '3-4-3', R5)
for g in f5['titolari']:
    if g['ruolo'] == 'C':
        g['p'] = 0.0
t5 = schiera.punteggi(f5, schiera.estrazioni(buchi5, 200, seme=5), R5)
t('CONTROPROVA: con 5 cambi e panchina lunga ne entrano 4',
  sum(t5) / len(t5) > sum(tot) / len(tot) + 3, f'{sum(t5) / len(t5):.2f} vs {sum(tot) / len(tot):.2f}',
  grave=True)

# modificatore: difesa a 4 con voti alti lo prende, difesa a 3 no
mod = [dict(g, sd=0.01, sd_v=0.01, mv=7.1) if g['ruolo'] in 'PD' else dict(g, sd=0.01, sd_v=0.01)
       for g in rosa_base()]
E_ = schiera.estrazioni(mod, 50, seme=1)
f4 = schiera.formazione(mod, '4-4-2', R)
f3 = schiera.formazione(mod, '3-4-3', R)
m4 = sum(schiera.punteggi(f4, E_, R)) / 50 - sum(g['mu'] for g in f4['titolari'])
m3 = sum(schiera.punteggi(f3, E_, R)) / 50 - sum(g['mu'] for g in f3['titolari'])
t('modificatore +6 con 4 difensori da 7, zero con 3', abs(m4 - 6) < 0.1 and abs(m3) < 0.1,
  f'{m4:.2f} / {m3:.2f}', grave=True)

# rischio: stesso mu, dispersione diversa, ultimo posto in attacco
def rosa_rischio():
    r = [dict(g, sd=0.5) for g in rosa_base() if g['k'] not in ('A2', 'A3', 'A4', 'A5')]
    r += [G('Sicuro', 'A', 6.9, sd=0.3), G('Mina', 'A', 6.9, sd=4.5),
          G('A8', 'A', 5.0, sd=0.5), G('A9', 'A', 4.5, sd=0.5)]
    return r


RR = rosa_rischio()
mia_media = schiera.valore_atteso(schiera.formazione(RR, '3-4-3', R))
forte = [dict(g, mu=g['mu'] + 1.1, sd=0.3) for g in rosa_base()]
debole = [dict(g, mu=g['mu'] - 1.1, sd=0.3) for g in rosa_base()]
Rs = regole.carica_lega(None, {'moduli': ['3-4-3'], 'modificatore': {'attivo': False}})
sf = schiera.consiglia(RR, Rs, avversario=forte, n=4000)
sd_ = schiera.consiglia(RR, Rs, avversario=debole, n=4000)
t('da SFAVORITO sceglie il giocatore piu imprevedibile',
  'Mina' in {g['k'] for g in sf['migliore']['titolari']}, grave=True)
t('da FAVORITO sceglie il giocatore piu affidabile',
  'Sicuro' in {g['k'] for g in sd_['migliore']['titolari']}, grave=True)
t('la probabilita di vittoria e coerente: favorito > sfavorito',
  sd_['migliore']['p_v'] > sf['migliore']['p_v'] + 0.3,
  f"{sd_['migliore']['p_v']:.2f} vs {sf['migliore']['p_v']:.2f}", grave=True)
monco = [g for g in rosa_base() if g['ruolo'] != 'P']
rm = schiera.consiglia(RR, Rs, avversario=monco, n=300)
t('avversario con rosa incompleta: si ottimizza la media e lo si dice, niente crash',
  rm['obiettivo'] == 'media' and 'avviso' in rm, str(rm.get('avviso')), grave=True)
Rp = regole.carica_lega(None, {'formula': 'punti', 'moduli': ['3-4-3'], 'modificatore': {'attivo': False}})
pp = schiera.consiglia(RR, Rp, avversario=forte, n=2000)
t('CONTROPROVA: a somma punti il rischio non si compra (obiettivo = media)',
  pp['obiettivo'] == 'media' and 'p_v' not in pp['migliore'], grave=True)

# ================================================== 6. mercato
import mercato  # noqa: E402
print('\n[6] mercato: scambi e svincolati sul valore della TUA formazione')

rosa_m = rosa_base()
liberi = [G('Pstar', 'P', 7.5, mv=6.8), G('Dbuono', 'D', 6.7), G('Cbuono', 'C', 7.3),
          G('Cinutile', 'C', 4.0), G('Arotto', 'A', 9.0, p=0.0), G('Cmedio', 'C', 6.0)]
Es = [{g['k']: g for g in rosa_m + liberi}] * 2      # due giornate identiche
mia = [g['k'] for g in rosa_m]

# il portiere titolare (5.5) per un centrocampista da 6.0: sulla carta +0.5 a
# giornata, in campo perdi il portiere e il centrocampista resta in panchina
sc = mercato.scambio(mia, dai=['P1'], ricevi=['Cmedio'], Es=Es, R=R)
t('lo scambio "vince" sulla somma dei valori...', sc['delta_grezzo'] > 0,
  f"{sc['delta_grezzo']:.2f}", grave=True)
t('...ma PEGGIORA la tua formazione: il nuovo non gioca, il portiere si',
  sc['delta'] < 0 and sc['delta'] < sc['delta_grezzo'] - 1, f"{sc['delta']:.2f} vs grezzo {sc['delta_grezzo']:.2f}", grave=True)
sc2 = mercato.scambio(mia, dai=['P3'], ricevi=['Dbuono'], Es=Es, R=R)
t('CONTROPROVA: il terzo portiere per un difensore da titolare migliora la formazione',
  sc2['delta'] > 0.5, f"{sc2['delta']:.2f}", grave=True)
t('uno scambio impossibile (giocatore non in rosa) si ferma e lo dice',
  'errore' in mercato.scambio(mia, dai=['Nessuno'], ricevi=['Dbuono'], Es=Es, R=R))

occupati = set(mia)
sv = mercato.svincolati(mia, occupati, Es, R)
chi = [x['k'] for x in sv]
t('gli svincolati non comprendono giocatori gia in una rosa',
  not (set(chi) & occupati), grave=True)
t('il centrocampista che entra in formazione e in cima', chi and chi[0] in ('Cbuono', 'Pstar'),
  str(chi[:3]), grave=True)
t('chi non migliorerebbe la formazione non viene proposto', 'Cinutile' not in chi, str(chi))
t('chi non gioca (p=0) non viene proposto, anche con mu altissimo', 'Arotto' not in chi, str(chi))
cb = next(x for x in sv if x['k'] == 'Cbuono')
t('per ogni svincolato dice CHI tagliare, dello stesso ruolo',
  cb['taglia'] in [g['k'] for g in rosa_m if g['ruolo'] == 'C'], str(cb['taglia']))

# ================================================== 7. socio end-to-end
import subprocess  # noqa: E402
import esempio  # noqa: E402
import socio  # noqa: E402
print('\n[7] socio.py end-to-end sulla lega finta')

cart_st = esempio.genera_stagione(os.path.join(tmp, 'stagione'))
lega_st = os.path.join(cart_st, 'lega.json')
C = socio.Contesto(lega_st)
t('il contesto trova tutti i dati della lega finta', not C.avvisi, str(C.avvisi), grave=True)
t('giornata = prima non giocata del calendario', C.g == 6, str(C.g), grave=True)
t('la rosa mia e completa (25)', C.mia and len(C.mia) == 25, str(len(C.mia or [])), grave=True)
E6 = C.stime_giornata(6)
t('le stime della giornata hanno l avversario vero',
  all(E6[k].get('avv') for k in C.mia), grave=True)
ris = schiera.consiglia(C.rosa(C.mia, E6), C.R, avversario=C.rosa(C._rosa_di('FC Beta'), E6), n=500)
t('la formazione consigliata e fatta solo di giocatori miei',
  {g['k'] for g in ris['migliore']['titolari'] + ris['migliore']['panchina']} <= set(C.mia), grave=True)
t('negli scontri diretti restituisce le probabilita di esito',
  abs(ris['migliore']['p_v'] + ris['migliore']['p_n'] + ris['migliore']['p_s'] - 1) < 1e-9, grave=True)
t('le probabili valgono per la prossima giornata, non per quelle dopo',
  C.stime_giornata(6)[C.mia[0]]['p'] in (proiezioni.P_XI, proiezioni.P_FUORI, 0.0)
  and C.stime_giornata(7)[C.mia[0]].get('fonte_p') != 'probabili', grave=True)

qui = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lancia(*arg, cwd=None):
    r = subprocess.run([sys.executable, os.path.join(qui, 'socio.py')] + list(arg),
                       capture_output=True, text=True, cwd=cwd or tmp)
    return r.returncode, r.stdout + r.stderr


rc, out = lancia('--lega', lega_st, 'settimana', '--sim', '400')
t('settimana: gira e stampa formazione, esito e portieri',
  rc == 0 and 'FORMAZIONE CONSIGLIATA' in out and 'VITTORIA' in out and 'PORTIERI' in out,
  out[-300:], grave=True)
rc, out = lancia('--lega', lega_st, 'rosa')
t('rosa: gira', rc == 0 and 'LA TUA ROSA' in out, out[-300:])
mio_p = C.E_base[C.mia[0]]['nome']
libero = next(g['nome'] for k, g in proiezioni.giocatori(C.E_base).items()
              if k not in {x for v in C.rose.values() for x in v} and g['ruolo'] == 'D')
rc, out = lancia('--lega', lega_st, 'scambio', '--dai', mio_p, '--ricevi', libero)
t('scambio: stampa sia la somma grezza sia l effetto sulla formazione',
  rc == 0 and 'sulla carta' in out and 'TUA formazione' in out, out[-300:], grave=True)
rc, out = lancia('--lega', lega_st, 'scambio', '--dai', 'Inesistente X.', '--ricevi', libero)
t('scambio con un giocatore non tuo: errore chiaro, niente traceback',
  rc != 0 and 'non in rosa' in out and 'Traceback' not in out, out[-300:], grave=True)
rc, out = lancia('--lega', lega_st, 'svincolati', '--ruolo', 'C')
t('svincolati: gira', rc == 0 and 'SVINCOLATI' in out, out[-300:])
rc, out = lancia('--lega', lega_st, 'portieri', '--giornate', '4')
t('portieri: gira', rc == 0 and 'gol subiti attesi' in out, out[-300:])

vuota = os.path.join(tmp, 'vuota')
os.makedirs(vuota)
rc, out = lancia('settimana', cwd=vuota)
t('senza nessun dato: dice cosa manca, non crasha',
  rc != 0 and 'Traceback' not in out and 'rose' in out, out[-400:], grave=True)

# ================================================== 8. verifica (backtest)
import verifica  # noqa: E402
print('\n[8] verifica: backtest senza sbirciare nel futuro')

cart8 = esempio.genera_stagione(os.path.join(tmp, 'stagione8'), giocate=8, seme=3)
C8 = socio.Contesto(os.path.join(cart8, 'lega.json'))
rec8 = voti.archivio(C8.file['voti'], R=C8.R)
bt = verifica.backtest(rec8, C8.listone, C8.partite, C8.R, C8.mia)
t('una riga per ogni giornata dalla terza in poi', [r['giornata'] for r in bt] == list(range(3, 9)),
  str([r['giornata'] for r in bt]), grave=True)
# CONTROPROVA anti-futuro: stravolgo i voti della giornata 6. Le stime usate PER
# la giornata 6 non devono cambiare (i punti veri si', perche' sono il risultato).
falsi = [dict(r, fv=(r['fv'] + 5 if r['fv'] is not None else None)) if r['giornata'] == 6 else r
         for r in rec8]
bt_f = verifica.backtest(falsi, C8.listone, C8.partite, C8.R, C8.mia)
r6, f6 = next(r for r in bt if r['giornata'] == 6), next(r for r in bt_f if r['giornata'] == 6)
r5, f5 = next(r for r in bt if r['giornata'] == 5), next(r for r in bt_f if r['giornata'] == 5)
t('CONTROPROVA: cambiare la giornata 6 non cambia niente della giornata 5',
  r5 == f5, grave=True)
_, Ev = verifica.stime_prima(rec8, C8.listone, C8.partite, C8.R, 6)
_, Ef6 = verifica.stime_prima(falsi, C8.listone, C8.partite, C8.R, 6)
t('le stime PER la giornata 6 sono identiche anche stravolgendo la 6',
  all(Ev[k]['mu'] == Ef6[k]['mu'] for k in proiezioni.giocatori(Ev)), grave=True)
t('alla 6 cambia solo il risultato vero (piu punti veri, piu errore)',
  f6['punti_socio'] > r6['punti_socio'] and f6['mae_socio'] > r6['mae_socio'] + 2,
  f"{f6['mae_socio']:.2f} vs {r6['mae_socio']:.2f}", grave=True)
_, Ef7 = verifica.stime_prima(falsi, C8.listone, C8.partite, C8.R, 7)
_, Ev7 = verifica.stime_prima(rec8, C8.listone, C8.partite, C8.R, 7)
t('CONTROPROVA: la giornata 7 invece la vede (il test sa accorgersene)',
  any(abs(Ev7[k]['mu'] - Ef7[k]['mu']) > 0.1 for k in proiezioni.giocatori(Ev7)), grave=True)
m_s = sum(r['mae_socio'] for r in bt) / len(bt)
m_f = sum(r['mae_finora'] for r in bt) / len(bt)
t('[misura, dati finti] lo shrinkage sbaglia meno della fantamedia finora', m_s < m_f,
  f'{m_s:.2f} vs {m_f:.2f}')
rc, out = lancia('--lega', os.path.join(cart8, 'lega.json'), 'verifica')
t('socio.py verifica: gira', rc == 0 and 'VERIFICA' in out, out[-300:])

# ================================================== esito
print('\n' + '=' * 74)
gravi = sum(1 for _, _, g in KO if g)
print(f'  RISULTATO: {len(OK)}/{len(OK) + len(KO)} pass   .   {len(KO)} FAIL ({gravi} gravi)')
print('=' * 74)
sys.exit(1 if KO else 0)
