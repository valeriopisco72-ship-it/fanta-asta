# -*- coding: utf-8 -*-
"""qa_scouting - schede qualitative, correzione delle stime, imbuto e verifica.

Stesso patto degli altri qa: dati sintetici, nomi finti, e per ogni regola la
domanda "se rompo il codice, questo test se ne accorge?".
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import nomi  # noqa: E402
import scouting  # noqa: E402

OK, KO = [], []


def t(nome, cond, dettaglio='', grave=True):
    (OK if cond else KO).append((nome, dettaglio, grave))
    print(f'  {"ok  " if cond else "FAIL"} {nome}' + (f'   [{dettaglio}]' if not cond and dettaglio else ''))


tmp = tempfile.mkdtemp(prefix='scouting_qa_')


def scheda(nome, **kpi):
    return {'nome': nome, 'data': '2026-09-28',
            'kpi': {k: {'voto': v, 'prova': f'prova su {k}', 'fonte': 'https://esempio.it/x'}
                    for k, v in kpi.items()}}


# ================================================== C1. scheda, validazione, indice
print('\n[C1] la scheda: 8 KPI con prova, fonte e data')

t('8 KPI coi pesi della spec', {k: p for k, (p, _) in scouting.KPI.items()} == {
    'spazio': 1.0, 'ruolo_tattico': 0.8, 'palle_inattive': 0.6, 'contesto': 0.6, 'allenatore': 0.5,
    'fisico': 0.5, 'traiettoria': 0.4, 'carattere': 0.3})
s_ok = scheda('Gioiello G.', spazio=2, ruolo_tattico=2, palle_inattive=1, contesto=2)
t('una scheda completa e valida', scouting.valida(s_ok) == [], str(scouting.valida(s_ok)))
s_nofonte = scheda('Chiacchiera C.', carattere=2)
s_nofonte['kpi']['carattere']['fonte'] = ''
t('un giudizio senza fonte non e valido (ne prova ne fonte: e una storia)', scouting.valida(s_nofonte) != [])
s_noprova = scheda('Vago V.', spazio=1)
s_noprova['kpi']['spazio']['prova'] = '  '
t('un giudizio senza prova non e valido', scouting.valida(s_noprova) != [])
t('voti fuori scala (-2..+2) rifiutati', scouting.valida(scheda('Esagerato E.', spazio=5)) != [])
t('voti non interi rifiutati', scouting.valida(scheda('Mezzo M.', spazio=1.5)) != [])
t('KPI sconosciuti rifiutati (niente campi inventati)', scouting.valida(scheda('Strano S.', simpatia=2)) != [])
t('senza nome: non valida', scouting.valida(dict(scheda('X', spazio=1), nome='')) != [])
t('data non ISO: non valida', scouting.valida(dict(scheda('Datato D.', spazio=1), data='28/09/2026')) != [])
t('giornata, se c e, e un intero', scouting.valida(dict(scheda('G G.', spazio=1), giornata='tre')) != [] and
  scouting.valida(dict(scheda('G G.', spazio=1), giornata=5)) == [])

i_ok, c_ok = scouting.indice(s_ok)
i_neg, _ = scouting.indice(scheda('Chiuso C.', spazio=-2, fisico=-2))
t('indice fra -1 e +1: positivo per il gioiello, negativo per il chiuso', 0 < i_ok <= 1 and -1 <= i_neg < 0,
  f'{i_ok:.2f} / {i_neg:.2f}')
tutti2 = scheda('Perfetto P.', **{k: 2 for k in scouting.KPI})
t('tutti +2 -> indice 1 e confidenza 1', scouting.indice(tutti2) == (1.0, 1.0), scouting.indice(tutti2))
t('indice = somma peso*voto / (2 * somma di TUTTI i pesi)',
  abs(scouting.indice(scheda('Uno U.', spazio=2))[0] - 2 * 1.0 / (2 * 4.7)) < 1e-12)
t('la confidenza cresce coi KPI documentati', c_ok > scouting.indice(scheda('Poco P.', spazio=2))[1])
t('CONTROPROVA: i KPI senza fonte non entrano nell indice',
  scouting.indice(s_nofonte) == (0.0, 0.0), scouting.indice(s_nofonte))
i_sx, c_sx = scouting.indice(scheda('Senza S.', spazio=2, ruolo_tattico=2), escludi=('spazio',))
t('escludi: toglie il KPI da numeratore e denominatore',
  abs(i_sx - 2 * 0.8 / (2 * 3.7)) < 1e-12 and abs(c_sx - 0.8 / 3.7) < 1e-12, (i_sx, c_sx))

sdir = os.path.join(tmp, 'scouting')
os.makedirs(sdir)


def salva(nome_file, s):
    with open(os.path.join(sdir, nome_file), 'w', encoding='utf-8') as f:
        json.dump(s, f)


salva('gioiello.json', s_ok)
salva('chiacchiera.json', s_nofonte)
salva('strano.json', scheda('Strano S.', simpatia=2))
salva('d1.json', {'nome': 'Doppio D.', 'data': '2026-09-01', 'kpi': {}})
salva('d2.json', dict(scheda('Doppio D.', spazio=2), data='2026-09-20'))
with open(os.path.join(sdir, 'rotto.json'), 'w') as f:
    f.write('{non json')
with open(os.path.join(sdir, 'leggimi.txt'), 'w') as f:
    f.write('non e una scheda')
Sc, err = scouting.carica(sdir)
t('carica: tiene le schede valide, per chiave del giocatore', nomi.giocatore('Gioiello G.') in Sc, sorted(Sc))
t('KPI senza fonte: il KPI e scartato e DETTO, la scheda resta (senza quel KPI)',
  nomi.giocatore('Chiacchiera C.') in Sc and not Sc[nomi.giocatore('Chiacchiera C.')]['kpi']
  and any('chiacchiera.json' in e for e in err), err)
t('KPI sconosciuto: la scheda intera e scartata e nominata',
  nomi.giocatore('Strano S.') not in Sc and any('strano.json' in e and 'simpatia' in e for e in err), err)
t('due schede dello stesso giocatore: vale la piu recente, e lo si dice',
  Sc[nomi.giocatore('Doppio D.')]['data'] == '2026-09-20' and any('Doppio' in e for e in err), err)
t('JSON rotto: scartato e nominato, le altre restano', any('rotto.json' in e for e in err) and Sc)
t('i file che non sono .json non si leggono', not any('leggimi' in e for e in err), err)
t('cartella assente: nessuna scheda, nessun errore', scouting.carica(os.path.join(tmp, 'non_esiste')) == ({}, []))


# ================================================== C2. correzione delle stime e segnali
print('\n[C2] lo scouting sposta le stime, di poco, e lo dice')
import datetime  # noqa: E402


def g_(nome, sq='MON', ruolo='A', mu=6.5, p=0.5):
    return {'k': nomi.giocatore(nome), 'nome': nome, 'ruolo': ruolo, 'squadra': sq, 'mu': mu, 'mv': 6.0, 'p': p,
            'sd': 2, 'sd_v': .6, 'fonte': 'listone'}


base = {x['k']: x for x in (g_('Gioiello G.'), g_('Chiuso C.', 'INT'), g_('Gonzalez N.', 'JUV'),
                            g_('Rossi A.', 'ROM'), g_('Rossi B.', 'LAZ'))}
base['_ruoli'] = {'A': {'mu': 6.0}}
sch = {nomi.giocatore('Gioiello G.'): s_ok, nomi.giocatore('Chiuso C.'): scheda('Chiuso C.', spazio=-2, fisico=-2)}
av = []
Eq = scouting.applica(base, sch, oggi='2026-09-30', avvisi=av)
gq, cq = Eq[nomi.giocatore('Gioiello G.')], Eq[nomi.giocatore('Chiuso C.')]
t('lo scouting alza mu e p del gioiello, abbassa quelli del chiuso',
  gq['mu'] > 6.5 and gq['p'] > 0.5 and cq['mu'] < 6.5 and cq['p'] < 0.5, (gq['mu'], gq['p'], cq['mu'], cq['p']))
i_ss = scouting.indice(s_ok, escludi=('spazio',))[0]
t('formula: p += 0.15*spazio/2, mu += 0.6*indice senza spazio',
  abs(gq['p'] - 0.65) < 1e-12 and abs(gq['mu'] - (6.5 + 0.6 * i_ss)) < 1e-12, (gq['p'], gq['mu']))
Emax = scouting.applica({'x': g_('Max M.', p=0.95)}, {'x': dict(tutti2, nome='Max M.')}, oggi='2026-09-30')['x']
t('correzione limitata: mai piu di +0.6 di fantavoto, p mai sopra 0.98',
  abs(Emax['mu'] - 7.1) < 1e-12 and Emax['p'] == 0.98, (Emax['mu'], Emax['p']))
t('ogni correzione e dichiarata nella fonte della stima', gq['fonte'] == 'listone + scouting (2026-09-28)', gq['fonte'])
t('CONTROPROVA: le stime originali non vengono toccate',
  base[nomi.giocatore('Gioiello G.')]['mu'] == 6.5 and base[nomi.giocatore('Gioiello G.')]['fonte'] == 'listone')
t('le chiavi di servizio restano', Eq['_ruoli'] == base['_ruoli'])
Evec = scouting.applica(base, sch, oggi='2026-12-30', avvisi=(av_v := []))
t('una scheda vecchia (oltre 60 giorni) non viene applicata, e lo si dice',
  Evec[nomi.giocatore('Gioiello G.')]['mu'] == 6.5 and any('scadut' in a for a in av_v), av_v)
t('CONTROPROVA: a 60 giorni esatti vale ancora',
  scouting.applica(base, sch, oggi='2026-11-27')[nomi.giocatore('Gioiello G.')]['mu'] > 6.5)
Efut = scouting.applica(base, sch, oggi='2026-09-01')
t('una scheda con data futura non si applica (niente futuro)', Efut[nomi.giocatore('Gioiello G.')]['mu'] == 6.5)
Eu = scouting.applica(base, {nomi.giocatore('Fantasma F.'): scheda('Fantasma F.', spazio=2)}, oggi='2026-09-30',
                      avvisi=(av_u := []))
t('scheda di un giocatore assente: ignorata e detta, nessuna chiave inventata',
  set(Eu) == set(base) and any('Fantasma' in a for a in av_u), av_u)
En = scouting.applica(base, {nomi.giocatore('N. Gonzalez'): scheda('N. Gonzalez', spazio=2)}, oggi='2026-09-30')
t('nome scritto diverso dal listone ("N. Gonzalez"): trovato se unico', En[nomi.giocatore('Gonzalez N.')]['p'] > 0.5)
Ea = scouting.applica(base, {nomi.giocatore('Rossi'): scheda('Rossi', spazio=2)}, oggi='2026-09-30',
                      avvisi=(av_a := []))
t('CONTROPROVA: nome ambiguo ("Rossi"): nessuno corretto, dichiarato ambiguo',
  all(Ea[k]['p'] == 0.5 for k in (nomi.giocatore('Rossi A.'), nomi.giocatore('Rossi B.')))
  and any('ambigu' in a for a in av_a), av_a)

seg = scouting.segnali({'ruolo': 'A', 'squadra': 'MON'}, neopromosse={'Monza'})
t('segnale strutturale: attaccante di neopromossa (4 colpi su 10 contro 2 su 16, lega 2026/27)',
  any('neopromossa' in x for x in seg), seg)
t('CONTROPROVA: il difensore di neopromossa no (difensori e portieri economici: 0 colpi su 41)',
  not scouting.segnali({'ruolo': 'D', 'squadra': 'Monza'}, neopromosse={'Monza'}))
t('CONTROPROVA: l attaccante di una squadra non neopromossa non ha il segnale',
  not any('neopromossa' in x for x in scouting.segnali({'ruolo': 'A', 'squadra': 'INT'}, neopromosse={'Monza'})))

# socio: carica scouting/ accanto a lega.json, applica e avvisa
import esempio  # noqa: E402
import socio  # noqa: E402
cart = esempio.genera_stagione(os.path.join(tmp, 'stagione'))
C0 = socio.Contesto(os.path.join(cart, 'lega.json'))
proiezioni_giocatori = {k: v for k, v in C0.E_base.items() if not k.startswith('_')}
scelto = sorted(proiezioni_giocatori)[0]
oggi = datetime.date.today().isoformat()
os.makedirs(os.path.join(cart, 'scouting'))
with open(os.path.join(cart, 'scouting', 'uno.json'), 'w', encoding='utf-8') as f:
    json.dump(dict(scheda(proiezioni_giocatori[scelto]['nome'], spazio=2, ruolo_tattico=2), data=oggi), f)
with open(os.path.join(cart, 'scouting', 'rotta.json'), 'w', encoding='utf-8') as f:
    f.write('{')
C1 = socio.Contesto(os.path.join(cart, 'lega.json'))
t('socio applica lo scouting a E_base ed E_ora, e lo dichiara nella fonte',
  'scouting' in C1.E_base[scelto]['fonte'] and 'scouting' in C1.E_ora[scelto]['fonte']
  and C1.E_base[scelto]['mu'] > C0.E_base[scelto]['mu'], (C1.E_base[scelto]['fonte'], scelto))
t('socio: le schede scartate finiscono negli avvisi', any('rotta.json' in a for a in C1.avvisi), C1.avvisi)
t('CONTROPROVA: senza cartella scouting niente cambia',
  not any('scouting' in g.get('fonte', '') for g in proiezioni_giocatori.values()))


# ================================================== C3. imbuto e gioielli
print('\n[C3] chi schedare fra i liberi, e il prezzo massimo dei gioielli')
lst = [{'nome': 'Punta N.', 'ruolo': 'A', 'squadra': 'MON', 'quota': 3, 'fvm': 10},
       {'nome': 'Terzino N.', 'ruolo': 'D', 'squadra': 'MON', 'quota': 3, 'fvm': 30},
       {'nome': 'Punta V.', 'ruolo': 'A', 'squadra': 'INT', 'quota': 3, 'fvm': 10},
       {'nome': 'Mediano N.', 'ruolo': 'C', 'squadra': 'MON', 'quota': 9, 'fvm': 10},
       {'nome': 'Preso P.', 'ruolo': 'A', 'squadra': 'MON', 'quota': 3, 'fvm': 50}]
cand = scouting.candidati(lst, occupati={nomi.giocatore('Preso P.')}, neopromosse={'Monza'})
t('i gia in rosa non sono candidati', 'Preso P.' not in [c['nome'] for c in cand])
t('attaccante di neopromossa davanti a tutti', cand[0]['nome'] == 'Punta N.' and cand[0]['segnali'], cand[:1])
t('ordine: A neopromossa > A > C neopromossa > resto',
  [c['nome'] for c in cand] == ['Punta N.', 'Punta V.', 'Mediano N.', 'Terzino N.'], [c['nome'] for c in cand])
t('n limita la lista', len(scouting.candidati(lst, set(), {'Monza'}, n=2)) == 2)
due = [{'nome': 'Scarso S.', 'ruolo': 'A', 'squadra': 'INT', 'quota': 1, 'fvm': 1},
       {'nome': 'Buono B.', 'ruolo': 'A', 'squadra': 'INT', 'quota': 9, 'fvm': 20}]
t('la quotazione bassa e informazione, non scavalca il FVM',
  [c['nome'] for c in scouting.candidati(due, set(), set())] == ['Buono B.', 'Scarso S.'])
cg = scouting.candidati(lst, {nomi.giocatore('Preso P.')}, {'Monza'}, guadagni={nomi.giocatore('Terzino N.'): 12.0})
t('i numeri contano: il difensore che migliora la tua formazione sale fra i candidati, e lo dice',
  [c['nome'] for c in cg].index('Terzino N.') < [c['nome'] for c in cg].index('Mediano N.')
  and any('tua formazione' in x for x in cg[[c['nome'] for c in cg].index('Terzino N.')]['segnali']),
  [(c['nome'], c['segnali']) for c in cg])
gi = scouting.gioielli([{'k': 'a', 'ruolo': 'A'}, {'k': 'b', 'ruolo': 'C'}, {'k': 'p', 'ruolo': 'P'}],
                       {'a': 30.0, 'b': 10.0, 'p': 20.0}, budget=100, slot=3)
# ordine per guadagno: a (1+97*30/60 = 49.5 -> 25), p (33.3 -> 5, portiere), b (1+97*10/60 = 17.2)
t('ordinati per guadagno', [g['k'] for g in gi] == ['a', 'p', 'b'], [g['k'] for g in gi])
t('tetto 25 per tutti, 5 per i portieri', [g['prezzo_max'] for g in gi] == [25, 5, 1 + 97 * 10 / 60],
  [g['prezzo_max'] for g in gi])
t('crediti tagliati dai tetti dichiarati', sum(g['prezzo_max'] for g in gi) < 100
  and abs(sum(g['tagliato'] for g in gi) - (49.5 - 25 + (1 + 97 * 20 / 60) - 5)) < 1e-9)
gi2 = scouting.gioielli([{'k': x, 'ruolo': 'C'} for x in 'abcd'], {'a': 4.0, 'b': 3.0, 'c': 2.0, 'd': 1.0},
                        budget=20, slot=2)
t('solo i primi S, a somma zero sul budget', [g['k'] for g in gi2] == ['a', 'b'] and
  abs(sum(g['prezzo_max'] for g in gi2) - 20) < 1e-9, gi2)
t('CONTROPROVA: guadagno nullo o negativo non e un gioiello',
  [g['k'] for g in scouting.gioielli([{'k': 'z', 'ruolo': 'A'}], {'z': 0.0}, 10, 1)] == [])

import subprocess  # noqa: E402


def lancia(*arg):
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                                     'socio.py')] + list(arg), capture_output=True, text=True, cwd=tmp)
    return r.returncode, r.stdout + r.stderr


lega_st = os.path.join(cart, 'lega.json')
rc, out = lancia('--lega', lega_st, 'scouting', 'candidati', '--n', '10')
t('socio scouting candidati: lista con segnali', rc == 0 and 'segnali' in out and out.count('\n  ') >= 10,
  out[-500:])
rc, out = lancia('--lega', lega_st, 'scouting', 'gioielli', '--budget', '60', '--slot', '3')
t('socio scouting gioielli: prezzo massimo e crediti tagliati dichiarati',
  rc == 0 and 'prezzo max' in out and 'tagliat' in out, out[-800:])
with open(os.path.join(tmp, 'lega_vuota.json'), 'w') as f:
    json.dump({'mia': 'X', 'file': {'listone': 'manca.csv'}}, f)
rc, out = lancia('--lega', os.path.join(tmp, 'lega_vuota.json'), 'scouting', 'candidati')
t('senza listone: messaggio, codice di errore, niente traceback',
  rc != 0 and 'listone' in out and 'Traceback' not in out, out[-300:])


# review finale: due schede dello stesso giocatore scritte diverse -> una sola correzione
due_nomi = {nomi.giocatore('Gonzalez N.'): dict(scheda('Gonzalez N.', spazio=2, ruolo_tattico=2, contesto=2),
                                               data='2026-09-01'),
            nomi.giocatore('N. Gonzalez'): dict(scheda('N. Gonzalez', spazio=2, ruolo_tattico=2, contesto=2),
                                               data='2026-09-20')}
Edn = scouting.applica(base, due_nomi, oggi='2026-09-30', avvisi=(av_dn := []))
gdn = Edn[nomi.giocatore('Gonzalez N.')]
t('due schede con nomi scritti diversi: una sola correzione (tetti rispettati), la piu recente, e lo si dice',
  gdn['mu'] - 6.5 <= scouting.MAX_MU + 1e-9 and gdn['p'] - 0.5 <= scouting.MAX_P + 1e-9
  and gdn['fonte'].count('scouting') == 1 and '2026-09-20' in gdn['fonte'] and any('Gonzalez' in a for a in av_dn),
  (gdn['mu'], gdn['p'], gdn['fonte'], av_dn))
Rv = scouting.risolvi(due_nomi, [nomi.giocatore('Gonzalez N.'), nomi.giocatore('Rossi A.')], [])
t('risolvi: le schede per chiave delle stime', list(Rv) == [nomi.giocatore('Gonzalez N.')], list(Rv))

# review finale: con la tabella dell'app le stime hanno solo i giocatori in rosa; una scheda di un
# LIBERO del listone non e' "ignorata" (serve a gioielli e candidati), una di nessuno si'
tabl = os.path.join(tmp, 'lega_tab')
os.makedirs(os.path.join(tabl, 'scouting'))
libero = next(r for r in __import__('fanta').carica(os.path.join(cart, 'listone.csv'))['giocatori'])
with open(os.path.join(tabl, 'tab.csv'), 'w', encoding='utf-8') as f:
    f.write('FantaSquadra;Nome;Ruolo;Squadra;MV;FM;Costo;FVMp\n')
    for r_, n_ in (('P', 3), ('D', 8), ('C', 8), ('A', 6)):
        for i in range(n_):
            f.write(f'Mia;M{r_}{i};{r_};Inter;6,0;6,{i};5;{5 + i}\n')
json.dump({'mia': 'Mia', 'giornate_giocate': 5,
           'file': {'tabella': 'tab.csv', 'rose': 'tab.csv', 'listone': os.path.join(cart, 'listone.csv')}},
          open(os.path.join(tabl, 'lega.json'), 'w'))
for nome_f, nome_g in (('libero.json', libero['nome']), ('nessuno.json', 'Nessuno Mai Visto')):
    with open(os.path.join(tabl, 'scouting', nome_f), 'w', encoding='utf-8') as f:
        json.dump(dict(scheda(nome_g, spazio=-2), data=oggi), f)
Ct = socio.Contesto(os.path.join(tabl, 'lega.json'))
t('tabella in uso: la scheda di un libero del listone non e dichiarata ignorata',
  not any(libero['nome'] in a and 'ignorat' in a for a in Ct.avvisi) and nomi.giocatore(libero['nome']) in Ct.schede,
  [a for a in Ct.avvisi if 'scouting' in a])
t('CONTROPROVA: la scheda di un nome che non esiste da nessuna parte si',
  any('Nessuno Mai Visto' in a for a in Ct.avvisi), Ct.avvisi)


# ================================================== C4. verifica per KPI
print('\n[C4] ogni KPI misurato, solo sulle giornate DOPO la scheda')
import verifica  # noqa: E402


def rec_(g, nome, fv):
    return {'giornata': g, 'nome': nome, 'ruolo': 'A', 'squadra': 'X', 'voto': 6.0, 'fv': fv,
            'gf': 0, 'gs': 0, 'rp': 0, 'rs': 0, 'rf': 0, 'au': 0, 'amm': 0, 'esp': 0, 'ass': 0}


stime_uguali = {nomi.giocatore(n): {'mu': 6.5} for n in ('Alto A.', 'Basso B.')}
rec = [rec_(g, 'Alto A.', 8.0) for g in range(1, 6)] + [rec_(g, 'Basso B.', 5.0) for g in range(1, 6)]
sch = {nomi.giocatore('Alto A.'): dict(scheda('Alto A.', spazio=2), data='2026-09-10', giornata=3),
       nomi.giocatore('Basso B.'): dict(scheda('Basso B.', spazio=-2), data='2026-09-10', giornata=3)}
V = {r['kpi']: r for r in verifica.verifica_kpi(sch, rec, stime_uguali)}
t('una riga per ognuno degli 8 KPI', set(V) == set(scouting.KPI))
t('KPI predittivo: scarto positivo (alto +1.5, basso -1.5 -> 3)', abs(V['spazio']['scarto'] - 3.0) < 1e-9,
  V['spazio'])
t('conta i giocatori per gruppo', V['spazio']['n_alti'] == 1 and V['spazio']['n_bassi'] == 1)
fut = [dict(r, fv=r['fv'] + (50 if r['giornata'] <= 3 else 0)) for r in rec]
t('CONTROPROVA: le giornate fino a quella della scheda non contano',
  V['spazio']['scarto'] == {r['kpi']: r for r in verifica.verifica_kpi(sch, fut, stime_uguali)}['spazio']['scarto'])
fut2 = [dict(r, fv=r['fv'] + (50 if r['giornata'] > 3 and r['nome'] == 'Basso B.' else 0)) for r in rec]
t('CONTROPROVA: le giornate dopo contano eccome',
  {r['kpi']: r for r in verifica.verifica_kpi(sch, fut2, stime_uguali)}['spazio']['scarto'] < 0)
t('KPI senza casi: nessun dato, non zero', V['carattere']['scarto'] is None and V['carattere']['n_alti'] == 0)
presto = {k: dict(v, giornata=5) for k, v in sch.items()}
t('scheda senza giornate dopo: nessun dato ancora', {r['kpi']: r for r in
  verifica.verifica_kpi(presto, rec, stime_uguali)}['spazio']['scarto'] is None)
t('a parita di stima numerica: lo scarto e contro la stima, non contro zero',
  abs({r['kpi']: r for r in verifica.verifica_kpi(sch, rec, {nomi.giocatore('Alto A.'): {'mu': 8.0},
       nomi.giocatore('Basso B.'): {'mu': 5.0}})}['spazio']['scarto']) < 1e-9)
sv_ = rec + [dict(rec_(4, 'Alto A.', 0), fv=None)]
t('i senza voto (fv None) non entrano nella media',
  {r['kpi']: r for r in verifica.verifica_kpi(sch, sv_, stime_uguali)}['spazio']['scarto'] == V['spazio']['scarto'])
senza_g = {k: {kk: vv for kk, vv in v.items() if kk != 'giornata'} for k, v in sch.items()}
t('scheda senza giornata: non entra nella verifica (confine sconosciuto)',
  {r['kpi']: r for r in verifica.verifica_kpi(senza_g, rec, stime_uguali)}['spazio']['scarto'] is None)

altri = sorted(k for k in proiezioni_giocatori if k != scelto)[:2]
for i, (k, v) in enumerate(zip(altri, (2, -2))):
    with open(os.path.join(cart, 'scouting', f'g{i}.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(scheda(proiezioni_giocatori[k]['nome'], spazio=v), data=oggi, giornata=2), f)
rc, out = lancia('--lega', lega_st, 'verifica', '--scouting')
t('socio verifica --scouting: una riga per KPI, e quante schede sono misurabili',
  rc == 0 and 'VERIFICA DELLO SCOUTING' in out and 'carattere' in out and 'misurabili' in out, out[-900:])


# ================================================== C5. validazione da riga di comando (per la skill)
print('\n[C5] python scouting.py --valida')
QUI_ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def valida_cli(*files):
    r = subprocess.run([sys.executable, os.path.join(QUI_, 'scouting.py'), '--valida'] + list(files),
                       capture_output=True, text=True, cwd=tmp)
    return r.returncode, r.stdout + r.stderr


rc, out = valida_cli(os.path.join(sdir, 'gioiello.json'))
t('scheda valida: codice 0, lo dice, con indice e confidenza', rc == 0 and 'valida' in out and 'confidenza' in out,
  out)
rc, out = valida_cli(os.path.join(sdir, 'chiacchiera.json'), os.path.join(sdir, 'rotto.json'))
t('scheda con errori: codice 1 e ogni errore scritto', rc == 1 and 'senza fonte' in out and 'rotto.json' in out, out)
rc, out = valida_cli(os.path.join(tmp, 'non_esiste.json'))
t('file mancante: codice 1, niente traceback', rc == 1 and 'Traceback' not in out, out)


# ================================================== esito
print('\n' + '=' * 74)
gravi = sum(1 for _, _, g in KO if g)
print(f'  RISULTATO: {len(OK)}/{len(OK) + len(KO)} pass   .   {len(KO)} FAIL ({gravi} gravi)')
sys.exit(1 if KO else 0)
