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


# ================================================== esito
print('\n' + '=' * 74)
gravi = sum(1 for _, _, g in KO if g)
print(f'  RISULTATO: {len(OK)}/{len(OK) + len(KO)} pass   .   {len(KO)} FAIL ({gravi} gravi)')
sys.exit(1 if KO else 0)
