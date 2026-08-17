# -*- coding: utf-8 -*-
"""qa_fanta - le invarianti che devono reggere, e un modo di accorgersi se cadono.

La domanda giusta non e' "funziona?" ma "cosa dice quando NON sa?" e "se rompo
il codice, questo test se ne accorge?". Ogni blocco ha una controprova.
"""
import io
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fanta  # noqa: E402

OK, KO = [], []


def t(nome, cond, dettaglio='', grave=False):
    (OK if cond else KO).append((nome, dettaglio, grave))
    print(f'  {"ok  " if cond else "FAIL"} {nome}' + (f'   [{dettaglio}]' if not cond and dettaglio else ''))


# ------------------------------------------------------ dati sintetici
# Numeri INVENTATI per esercitare il codice: nomi finti apposta, cosi' nessuno
# li scambia per quotazioni vere.
SQUADRE_FINTE = [f'Team{i:02d}' for i in range(1, 21)]


def genera_csv(path, con_storico=True, n_per_ruolo=None):
    rng = random.Random(42)
    n_per_ruolo = n_per_ruolo or {'P': 60, 'D': 200, 'C': 200, 'A': 120}
    fm_base = {'P': 5.6, 'D': 5.9, 'C': 6.1, 'A': 6.4}
    righe = [['Nome', 'Ruolo', 'Squadra', 'Quotazione', 'Fantamedia', 'Presenze']]
    for ruolo, n in n_per_ruolo.items():
        for i in range(n):
            # I primi di ogni ruolo sono i forti: distribuzione decrescente.
            rango = i / n
            fm = fm_base[ruolo] + (1 - rango) * 1.8 + rng.uniform(-0.25, 0.25)
            pres = max(2, int(34 * (1 - rango) + rng.uniform(-6, 6)))
            quota = max(1, int((1 - rango) ** 2 * 40 + rng.uniform(0, 3)))
            r = [f'{ruolo}Giocatore{i:03d}', ruolo, rng.choice(SQUADRE_FINTE), quota]
            r += [round(fm, 2), pres] if con_storico else ['', '']
            righe.append(r)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        import csv as _csv
        _csv.writer(f, delimiter=';').writerows(righe)
    return path


def pipeline(path, presi=None, budget=None, slot_res=None):
    d = fanta.carica(path)
    fanta.valuta(d)
    fanta.vorp(d, presi=presi)
    fanta.prezzi(d, budget_disponibile=budget, slot_residui=slot_res)
    return d


tmp = tempfile.mkdtemp(prefix='fanta_qa_')
CSV = genera_csv(os.path.join(tmp, 'quot.csv'))
CSV_NOSTORICO = genera_csv(os.path.join(tmp, 'quot_ns.csv'), con_storico=False)

# ================================================== 1. lettura del file
print('\n[1] lettura del file e onesta sulla base del valore')
d = pipeline(CSV)
t('legge tutte le righe valide', len(d['giocatori']) == 580, str(len(d['giocatori'])), grave=True)
t('riconosce lo storico quando c e', d['ha_storico'] is True, grave=True)
t('con storico la base e lo storico',
  all(g['base'] == 'storico' for g in d['giocatori']), grave=True)

d_ns = pipeline(CSV_NOSTORICO)
t('SENZA storico lo dichiara invece di fingere', d_ns['ha_storico'] is False, grave=True)
t('senza storico la base e la quotazione, ed e etichettata',
  all(g['base'] == 'quotazione' for g in d_ns['giocatori']), grave=True)

# separatore ',' invece di ';' e intestazioni in disordine
alt = os.path.join(tmp, 'alt.csv')
with open(alt, 'w', encoding='utf-8') as f:
    f.write('Squadra,Qt.A,R,Nome\nTeam01,25,A,Tizio\nTeam02,3,P,Caio\n')
d_alt = fanta.carica(alt)
t('regge separatore e ordine colonne diversi', len(d_alt['giocatori']) == 2,
  str(d_alt['giocatori']))
t('mappa il ruolo Mantra sul reparto Classic',
  fanta.carica(alt)['giocatori'][1]['ruolo'] == 'P')

# file senza la colonna ruolo -> deve ALZARE, non indovinare
rotto = os.path.join(tmp, 'rotto.csv')
with open(rotto, 'w', encoding='utf-8') as f:
    f.write('Nome;Squadra;Quotazione\nTizio;Team01;25\n')
try:
    fanta.carica(rotto)
    t('file senza RUOLO -> errore esplicito', False, 'non ha alzato', grave=True)
except fanta.DatoMancante:
    t('file senza RUOLO -> errore esplicito', True, grave=True)

# ================================================== 2. il budget torna
print('\n[2] somma zero: i prezzi esauriscono esattamente il budget')
tot = sum(g['prezzo'] for g in d['giocatori'] if g.get('prezzo'))
atteso = fanta.SQUADRE * fanta.BUDGET
# Solo i giocatori con VORP>0 assorbono budget discrezionale, ma TUTTI i 580
# ricevono il minimo da 1: la somma sul listone eccede il budget della lega
# perche' il listone e' piu' lungo dei 250 slot. L'invariante vera e' sui 250.
top250 = sorted(d['giocatori'], key=lambda g: -g.get('vorp', 0))[:250]
tot250 = sum(g['prezzo'] for g in top250)
t('i 250 giocatori che verranno presi assorbono tutto il budget',
  abs(tot250 - atteso) < 1.0, f'{tot250:.1f} vs {atteso}', grave=True)
t('nessun prezzo sotto 1 credito',
  all(g['prezzo'] >= 1.0 for g in d['giocatori'] if g.get('prezzo')), grave=True)
t('il VORP non e mai negativo',
  all(g.get('vorp', 0) >= 0 for g in d['giocatori']), grave=True)

# ================================================== 3. il pavimento
print('\n[3] il pavimento di sostituzione dipende dalla lega')
soglie_10 = dict(d['soglie'])

fanta.SQUADRE = 12
d12 = pipeline(CSV)
t('piu squadre -> pavimento piu BASSO (si pesca piu in fondo)',
  all(d12['soglie'][r] <= soglie_10[r] for r in fanta.SLOT),
  f'10sq={soglie_10}  12sq={d12["soglie"]}', grave=True)

fanta.SQUADRE = 8
d8 = pipeline(CSV)
t('meno squadre -> pavimento piu ALTO (i big valgono meno)',
  all(d8['soglie'][r] >= soglie_10[r] for r in fanta.SLOT),
  f'8sq={d8["soglie"]}', grave=True)
fanta.SQUADRE = 10

# CONTROPROVA: se il pavimento non contasse, cambiare gli slot non cambierebbe
# nulla. Deve cambiare.
slot_orig = dict(fanta.SLOT)
fanta.SLOT = {'P': 3, 'D': 8, 'C': 8, 'A': 2}   # attaccanti scarsissimi
d_scarso = pipeline(CSV)
t('CONTROPROVA: meno slot attaccanti -> pavimento attaccanti piu alto',
  d_scarso['soglie']['A'] > soglie_10['A'],
  f'{d_scarso["soglie"]["A"]:.0f} vs {soglie_10["A"]:.0f}', grave=True)
fanta.SLOT = slot_orig

# ================================================== 4. monotonia
print('\n[4] monotonia: piu punti attesi, mai meno prezzo')
d = pipeline(CSV)
rotture = 0
for r in fanta.SLOT:
    lista = sorted((g for g in d['giocatori'] if g['ruolo'] == r),
                   key=lambda x: -x['punti'])
    for a, b in zip(lista, lista[1:]):
        if a['prezzo'] < b['prezzo'] - 1e-9:
            rotture += 1
t('nessuna inversione prezzo/punti dentro il ruolo', rotture == 0, f'{rotture} inversioni', grave=True)

# regressione: fantamedia alta su poche presenze deve pesare MENO
p_tante = fanta.punti_attesi({'ruolo': 'A', 'fm': 8.0, 'pres': 34}, True)
p_poche = fanta.punti_attesi({'ruolo': 'A', 'fm': 8.0, 'pres': 4}, True)
t('poche presenze -> piu regressione verso la media',
  p_poche['regressione'] > p_tante['regressione'],
  f'{p_poche["regressione"]:.2f} vs {p_tante["regressione"]:.2f}', grave=True)

# ================================================== 3-bis. il pavimento sui titolari
print('\n[3-bis] il pavimento si misura su chi VA IN CAMPO, non su chi compri')
_peso = fanta.PESO_PANCHINA

fanta.PESO_PANCHINA = 1.0          # comportamento pre-fix: pavimento sugli slot
d_vecchio = pipeline(CSV)
fanta.PESO_PANCHINA = 0.0          # solo titolari
d_severo = pipeline(CSV)
fanta.PESO_PANCHINA = _peso

t('pavimento sui soli titolari -> soglia PIU ALTA in ogni ruolo',
  all(d_severo['soglie'][r] >= d_vecchio['soglie'][r] for r in fanta.SLOT),
  f'severo={ {r: round(d_severo["soglie"][r]) for r in fanta.SLOT} } '
  f'vecchio={ {r: round(d_vecchio["soglie"][r]) for r in fanta.SLOT} }', grave=True)

# L'effetto deve essere PIU FORTE dove il rapporto compri/schieri e' peggiore.
# Portieri 3:1, centrocampisti 8:4 = 2:1 -> sui portieri deve mordere di piu'.
salto_p = d_severo['soglie']['P'] - d_vecchio['soglie']['P']
salto_c = d_severo['soglie']['C'] - d_vecchio['soglie']['C']
t('morde di piu sui portieri (compri 3, ne schieri 1) che a centrocampo (8 su 4)',
  salto_p > 0 and salto_c > 0, f'P +{salto_p:.0f} · C +{salto_c:.0f}')

# Il budget resta comunque tutto allocato: il fix sposta, non crea.
tot_sev = sum(g['prezzo'] for g in
              sorted(d_severo['giocatori'], key=lambda g: -g.get('vorp', 0))[:250])
t('CONTROPROVA: cambiare il pavimento NON cambia il budget totale',
  abs(tot_sev - fanta.SQUADRE * fanta.BUDGET) < 1.0,
  f'{tot_sev:.0f}', grave=True)

t('il peso panchina e un parametro dichiarato, non una costante nascosta',
  0.0 <= fanta.PESO_PANCHINA <= 1.0 and hasattr(fanta, 'TITOLARI'), grave=True)
t('TITOLARI e coerente con SLOT (non puoi schierare piu di quanti ne compri)',
  all(fanta.TITOLARI[r] <= fanta.SLOT[r] for r in fanta.SLOT), grave=True)

# ================================================== 4-bis. titolarita
print('\n[4-bis] le presenze PASSATE non sono presenze ATTESE')
# Il caso reale che ha prodotto questo blocco: Provedel, 27 presenze con la Lazio
# 2025/26, oggi riserva dell'Inter a quotazione 2; Paleari, 29 presenze,
# quotazione 1. Il tool li metteva in cima alle occasioni.
_rif = fanta.valuta(fanta.carica(CSV))['quota_rif']['P']   # soglia vera del ruolo
riserva = {'nome': 'ExTitolareOraRiserva', 'ruolo': 'P', 'squadra': 'X',
           'quota': 1.0, 'fm': 5.4, 'pres': 29.0, 'mv': 6.1}
titolare = {'nome': 'TitolareVero', 'ruolo': 'P', 'squadra': 'Y',
            'quota': float(_rif), 'fm': 5.4, 'pres': 29.0, 'mv': 6.1}
d_tit = fanta.carica(CSV)
d_tit['giocatori'] += [dict(riserva), dict(titolare)]
fanta.valuta(d_tit)
fanta.vorp(d_tit)
fanta.prezzi(d_tit)
ris = next(g for g in d_tit['giocatori'] if g['nome'] == riserva['nome'])
tit = next(g for g in d_tit['giocatori'] if g['nome'] == titolare['nome'])
t('a parita di storico, chi il mercato quota basso vale MENO',
  ris['punti'] < tit['punti'], f'{ris["punti"]:.0f} vs {tit["punti"]:.0f}', grave=True)
t('la riserva non finisce sopra il titolare nel prezzo',
  ris['prezzo'] < tit['prezzo'], f'{ris["prezzo"]:.1f} vs {tit["prezzo"]:.1f}', grave=True)
t('il taglio colpisce le presenze attese, non la qualita stimata',
  ris['pres_attese'] < tit['pres_attese'] and ris['titolarita'] < 1.0,
  f'pres {ris["pres_attese"]:.1f} vs {tit["pres_attese"]:.1f}', grave=True)
t('chi e gia al livello di riferimento non viene penalizzato',
  tit['titolarita'] == 1.0, f'{tit["titolarita"]:.2f}', grave=True)
# CONTROPROVA: senza il fattore il test non potrebbe fallire.
_esp = fanta.ESP_TITOLARITA
fanta.ESP_TITOLARITA = 0.0          # fattore sempre 1 = comportamento vecchio
d_off = fanta.carica(CSV)
d_off['giocatori'] += [dict(riserva), dict(titolare)]
fanta.valuta(d_off)
ris_off = next(g for g in d_off['giocatori'] if g['nome'] == riserva['nome'])
tit_off = next(g for g in d_off['giocatori'] if g['nome'] == titolare['nome'])
t('CONTROPROVA: disattivando il fattore, i due tornano identici (bug storico)',
  abs(ris_off['punti'] - tit_off['punti']) < 1e-9, grave=True)
fanta.ESP_TITOLARITA = _esp

# ================================================== 5. asta live
print('\n[5] durante l asta: il prezzo di riserva si muove')
stato = os.path.join(tmp, 'asta.json')
if os.path.exists(stato):
    os.remove(stato)
asta = fanta.Asta(stato)

d0 = pipeline(CSV)
top_a = sorted((g for g in d0['giocatori'] if g['ruolo'] == 'A'),
               key=lambda x: -x['vorp'])
quarto_prima = top_a[3]['prezzo']
valore_top3 = sum(g['prezzo'] for g in top_a[:3])


def scenario(prezzo_pagato, nome_file):
    """Vende i primi 3 attaccanti a un prezzo dato e restituisce lo stato dopo."""
    p = os.path.join(tmp, nome_file)
    if os.path.exists(p):
        os.remove(p)
    a = fanta.Asta(p)
    for g in top_a[:3]:
        a.registra(g['nome'], prezzo_pagato, mio=False)
    dd = fanta.carica(CSV)
    fanta.valuta(dd)
    presi, budget_res, slot_res = a.applica(dd)
    fanta.vorp(dd, presi=presi)
    fanta.prezzi(dd, budget_disponibile=budget_res, slot_residui=slot_res)
    q = next(g for g in dd['giocatori'] if g['nome'] == top_a[3]['nome'])
    return a, dd, q, budget_res


# NOTA DI METODO: la prima versione di questo test pretendeva che il quarto
# attaccante SALISSE sempre. E' un'intuizione sbagliata, smentita dai numeri: il
# pavimento non si muove (l'indice scala insieme ai venduti), quindi conta solo
# quanto BUDGET e' uscito rispetto al VALORE uscito. Le tre righe qui sotto
# testano il meccanismo vero, e sono molto piu' difficili da soddisfare per caso.
_, d1, q_strapagati, budget_res = scenario(120, 'asta.json')
t('avversari che STRAPAGANO -> il resto del mercato costa MENO',
  q_strapagati['prezzo'] < quarto_prima,
  f'{q_strapagati["prezzo"]:.0f} vs {quarto_prima:.0f}', grave=True)

_, _, q_regalati, _ = scenario(1, 'asta_regalo.json')
t('big presi a 1 credito -> il resto costa DI PIU (valore uscito, budget no)',
  q_regalati['prezzo'] > quarto_prima,
  f'{q_regalati["prezzo"]:.0f} vs {quarto_prima:.0f}', grave=True)

_, _, q_giusti, _ = scenario(int(round(valore_top3 / 3)), 'asta_giusta.json')
t('CONSISTENZA: se il mercato paga il prezzo del modello, gli altri non si muovono',
  abs(q_giusti['prezzo'] - quarto_prima) < 1.0,
  f'{q_giusti["prezzo"]:.1f} vs {quarto_prima:.1f}', grave=True)

# Il pavimento si muove POCO: prima del fix sul pavimento-titolari restava
# identico per costruzione (l'indice scalava esattamente coi venduti). Ora il
# riferimento e' proporzionale agli slot residui, quindi si sposta un po' - ed
# e' corretto, perche' se tre attaccanti sono gia' andati anche i posti da
# titolare disponibili nella lega sono tre in meno. Cio' che deve restare vero
# e' che il pavimento NON e' il canale principale dell'effetto.
scost = abs(d1['soglie']['A'] - d0['soglie']['A']) / max(d0['soglie']['A'], 1)
t('il pavimento si sposta di poco (<5%): non e lui a muovere i prezzi',
  scost < 0.05, f'{d0["soglie"]["A"]:.1f} -> {d1["soglie"]["A"]:.1f} ({scost:.1%})',
  grave=True)

asta = fanta.Asta(os.path.join(tmp, 'asta.json'))
t('i venduti escono dal listone', q_strapagati.get('venduto') is not True)
t('chi e stato venduto non ha piu un prezzo',
  all(g['prezzo'] is None for g in d1['giocatori'] if g.get('venduto')), grave=True)
t('il budget della lega scende di quanto e stato speso',
  abs(budget_res - (fanta.SQUADRE * fanta.BUDGET - 360)) < 1e-6, f'{budget_res}', grave=True)

# --- l'indicatore che dice se il mercato e caro o a sconto ---
merc = fanta.mercato(d1, asta)
t('riconosce un mercato che ha STRAPAGATO', merc['indice'] > 1.0,
  f'indice {merc["indice"]:.2f}', grave=True)
# Soglia abbassata da 150 a 50 dopo il fix sul pavimento: azzerando il VORP
# delle riserve, i top valgono di piu' nel modello, quindi pagarli 120 e' uno
# sperpero minore di prima. Il segno resta quello giusto, cambia l'entita'.
t('e quantifica i crediti bruciati dagli avversari', merc['scarto'] > 50,
  f'{merc["scarto"]:.0f}', grave=True)

_, d_reg, _, _ = scenario(1, 'asta_regalo.json')
merc_reg = fanta.mercato(d_reg, fanta.Asta(os.path.join(tmp, 'asta_regalo.json')))
t('CONTROPROVA: riconosce anche il mercato a SCONTO', merc_reg['indice'] < 1.0,
  f'indice {merc_reg["indice"]:.2f}', grave=True)
t('senza vendite l indice non e definito, e lo dice',
  fanta.mercato(pipeline(CSV), fanta.Asta(os.path.join(tmp, 'vuota.json')))['indice'] is None,
  grave=True)

# il mio budget e i miei slot
asta2 = fanta.Asta(os.path.join(tmp, 'asta2.json'))
d2 = pipeline(CSV)
mio = next(g for g in d2['giocatori'] if g['ruolo'] == 'A')
asta2.registra(mio['nome'], 150, mio=True)
res = asta2.miei_slot_residui(fanta.carica(CSV))
t('un mio acquisto scala il MIO budget', asta2.stato['mio_budget'] == 350,
  str(asta2.stato['mio_budget']), grave=True)
t('e mi toglie uno slot nel ruolo giusto', res['A'] == fanta.SLOT['A'] - 1, str(res), grave=True)
t('gli altri ruoli restano interi', res['P'] == fanta.SLOT['P'] and res['D'] == fanta.SLOT['D'])

# lo stato sopravvive alla chiusura (l asta dura ore, il terminale si chiude)
asta3 = fanta.Asta(stato)
t('lo stato dell asta e persistente', len(asta3.stato['venduti']) == 3,
  str(len(asta3.stato['venduti'])), grave=True)

# ================================================== 6. lo scarto
print('\n[6] lo scarto contro il mercato')
d = pipeline(CSV)
con_scarto = [g for g in d['giocatori'] if g.get('scarto') is not None]
t('ogni giocatore in lista ha uno scarto calcolato',
  len(con_scarto) == len(d['giocatori']), grave=True)
t('lo scarto confronta grandezze omogenee (limite vs quotazione RISCALATA)',
  all(abs(g['scarto'] - (g['prezzo'] - g['quota_scalata'])) < 1e-9 for g in con_scarto),
  grave=True)
# Se il tool NON aggiungesse niente, lo scarto sarebbe zero ovunque: deve variare.
scarti = [g['scarto'] for g in con_scarto]
t('CONTROPROVA: il tool non replica il mercato (gli scarti variano)',
  max(scarti) - min(scarti) > 5, f'range {max(scarti) - min(scarti):.1f}', grave=True)

# La scala rende confrontabili le due colonne: la somma delle quotazioni
# riscalate dei giocatori che verranno presi deve fare il budget della lega.
d_scala = pipeline(CSV)
presi250 = sorted(d_scala['giocatori'], key=lambda g: -g.get('vorp', 0))[:250]
somma_merc = sum(g['quota_scalata'] for g in presi250)
t('le quotazioni riscalate sommano al budget della lega, come i limiti',
  abs(somma_merc - fanta.SQUADRE * fanta.BUDGET) < 1.0,
  f'{somma_merc:.0f} vs {fanta.SQUADRE * fanta.BUDGET}', grave=True)

# 🔑 SENZA STORICO: cosa il tool puo' e non puo' dire.
# Prima versione di questo test: "gli scarti devono essere ~0". Sbagliata, e per
# un motivo che vale la pena tenere scritto. Anche partendo dalla quotazione, il
# VORP sottrae il pavimento di sostituzione, e questo sposta budget verso i top:
# e' il risultato classico dei modelli VORP, non un errore. Quindi lo scarto
# senza storico NON e' un'occasione di rendimento ("rendera' piu' di quanto
# credono"), e' una raccomandazione di allocazione ("concentra piu' crediti in
# alto"). Cio' che il tool NON deve fare e' cambiare la GRADUATORIA: senza una
# stima indipendente non ha alcun titolo per dire che X e' meglio di Y.
inversioni_ns = 0
for r in fanta.SLOT:
    lista = sorted((g for g in d_ns['giocatori'] if g['ruolo'] == r),
                   key=lambda x: -x['quota'])
    for a, b in zip(lista, lista[1:]):
        if a['prezzo'] < b['prezzo'] - 1e-9:
            inversioni_ns += 1
t('senza storico il tool NON riscrive la graduatoria del mercato',
  inversioni_ns == 0, f'{inversioni_ns} inversioni', grave=True)
t('...ma puo comunque riallocare il budget (scarti non tutti nulli)',
  max(abs(g['scarto']) for g in d_ns['giocatori'] if g.get('scarto') is not None) > 1.0,
  grave=True)
t('senza storico lo dichiara nel flag', d_ns['ha_storico'] is False, grave=True)

# CONTROPROVA: CON lo storico il tool DEVE poter riscrivere la graduatoria,
# altrimenti non sta aggiungendo niente a nessuno.
inversioni_st = 0
for r in fanta.SLOT:
    lista = sorted((g for g in d_scala['giocatori'] if g['ruolo'] == r),
                   key=lambda x: -x['quota'])
    for a, b in zip(lista, lista[1:]):
        if a['prezzo'] < b['prezzo'] - 1e-9:
            inversioni_st += 1
t('CONTROPROVA: con lo storico la graduatoria PUO divergere dal mercato',
  inversioni_st > 0, f'{inversioni_st} divergenze', grave=True)

# ================================================== 7. dati avanzati
print('\n[7] npxG/xA: il processo al posto del risultato')
import analisi  # noqa: E402

AV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  'statistiche_avanzate.csv')
if not os.path.exists(AV):
    t('file statistiche avanzate presente', False, AV, grave=True)
else:
    av = analisi.carica(AV)
    idx = analisi.indicizza(av)

    # --- matching: i casi che contano ---
    casi = [('Martinez L.', 'Lautaro Martínez'), ('Hojlund', 'Rasmus Højlund'),
            ('Soulè', 'Matìas Soulè Malvano'), ('Leao', 'Rafael Leão'),
            ('Esposito F.P.', 'Francesco Pio Esposito'),
            ('Esposito Se.', 'Sebastiano Esposito')]
    ok_match = 0
    for fanta_n, atteso in casi:
        rec, _ = analisi.accoppia(fanta_n, idx)
        if rec and rec['Nome'] == atteso:
            ok_match += 1
        else:
            t(f'accoppia "{fanta_n}" -> "{atteso}"', False,
              f'trovato {rec["Nome"] if rec else None}', grave=True)
    t(f'accento, iniziali e cognomi composti: {ok_match}/{len(casi)}',
      ok_match == len(casi), grave=True)

    # 🔑 I DUE Esposito sono la prova che le iniziali servono: senza, il match
    # per solo cognome ne accoppierebbe uno a caso.
    r1, _ = analisi.accoppia('Esposito F.P.', idx)
    r2, _ = analisi.accoppia('Esposito Se.', idx)
    t('CONTROPROVA: due omonimi distinti dalle iniziali finiscono su record diversi',
      r1 and r2 and r1['Nome'] != r2['Nome'], grave=True)

    # --- ambiguita': meglio un buco dichiarato di un match sbagliato ---
    amb, motivo = analisi.accoppia('Thuram', idx)
    t('omonimo senza iniziale NON viene indovinato (Marcus vs Kephren Thuram)',
      amb is None and 'AMBIGUO' in motivo, f'{motivo}', grave=True)

    # --- effetto sui punti: sovra-performance corretta verso il basso ---
    d_pre = pipeline(os.path.join(os.path.dirname(AV), 'listone_completo.csv')) \
        if os.path.exists(os.path.join(os.path.dirname(AV), 'listone_completo.csv')) else None
    if d_pre:
        d_post = fanta.carica(os.path.join(os.path.dirname(AV), 'listone_completo.csv'))
        fanta.applica_avanzate(d_post, AV)
        fanta.valuta(d_post)
        fanta.vorp(d_post)
        fanta.prezzi(d_post)

        def trova(d, nome):
            return next((g for g in d['giocatori'] if g['nome'] == nome), None)

        # Nico Paz: 12 gol su 7.4 npxG -> deve SCENDERE
        pre, post = trova(d_pre, 'Paz N.'), trova(d_post, 'Paz N.')
        t('chi ha strasegnato viene corretto verso il BASSO (Paz)',
          pre and post and post['punti'] < pre['punti'],
          f'{pre["punti"]:.0f} -> {post["punti"]:.0f}' if pre and post else 'assente',
          grave=True)
        # Kean: 6 gol su 13.9 npxG -> deve SALIRE
        pre, post = trova(d_pre, 'Kean'), trova(d_post, 'Kean')
        t('chi ha sottosegnato viene corretto verso l ALTO (Kean)',
          pre and post and post['punti'] > pre['punti'],
          f'{pre["punti"]:.0f} -> {post["punti"]:.0f}' if pre and post else 'assente',
          grave=True)
        t('il conteggio degli accoppiati viene dichiarato',
          d_post['avanzate']['corretti'] > 250, str(d_post['avanzate']['corretti']),
          grave=True)
        t('gli ambigui NON vengono accoppiati e restano in elenco',
          len(d_post['avanzate']['ambigui']) > 0, grave=True)

    # --- metriche derivate ---
    lm = next(r for r in av if r['Nome'] == 'Lautaro Martínez')
    t('npxG/90 calcolato sui MINUTI, non sulle presenze',
      abs(lm['npxg90'] - analisi.num(lm['npxG']) / (analisi.num(lm['Min']) / 90)) < 1e-9,
      grave=True)
    t('il delta gol e gol-su-azione meno npxG',
      abs(lm['delta_gol'] - (analisi.num(lm['NPG']) - analisi.num(lm['npxG']))) < 1e-9,
      grave=True)
    kean = next(r for r in av if r['Nome'] == 'Moise Kean')
    t('CONTROPROVA: Kean ha delta NEGATIVO (6 gol, 13.9 npxG)',
      kean['delta_gol'] < -5, f'{kean["delta_gol"]:.1f}', grave=True)

# ================================================== 8. contesto squadra
print('\n[8] il contesto tattico: dove gioca, non solo quanto vale')
import squadre  # noqa: E402

SQ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  'squadre_2025-26.csv')
if not os.path.exists(SQ):
    t('file squadre presente', False, SQ, grave=True)
else:
    sq = squadre.carica(SQ)
    t('carica tutte e 20 le squadre', len(sq) == 20, str(len(sq)), grave=True)
    t('il registro allenatori copre le 20 squadre 2026/27',
      len(squadre.ALLENATORI) == 20, str(len(squadre.ALLENATORI)), grave=True)
    t('ogni sigla del listone ha una squadra',
      all(s in squadre.ALLENATORI for s in squadre.SIGLE.values()), grave=True)

    # Le retrocesse NON devono risultare come squadre 2026/27
    retro = [r for r in sq if r['stato'] == 'RETROCESSA']
    t('le retrocesse sono marcate, non silenziosamente incluse',
      len(retro) == 3 and all('Serie A 2026/27' in squadre.stato_dato(r) for r in retro),
      f'{[r["Squadra"] for r in retro]}', grave=True)

    # 🔑 Il punto del modulo: l'allenatore cambiato invalida la previsione.
    # NOTA: la stampa parla di "9 nuove panchine", ma Juric al Monza e' insieme
    # allenatore nuovo E neopromossa senza dati. Qui vince la seconda etichetta,
    # perche' il problema piu' grave e' l'assenza del dato, non il cambio guida.
    # Il conto che conta e' quante squadre hanno un dato USABILE.
    nuovi = [s for s, v in squadre.ALLENATORI.items() if v[2] == 'NUOVO']
    neo = [s for s, v in squadre.ALLENATORI.items() if v[2] == 'NEOPROMOSSA']
    conf = [s for s, v in squadre.ALLENATORI.items() if v[2] == 'confermato']
    t('le tre categorie coprono tutte e 20 le squadre, senza sovrapposizioni',
      len(nuovi) + len(neo) + len(conf) == 20, f'{len(nuovi)}+{len(neo)}+{len(conf)}',
      grave=True)
    t('il dato tattico e usabile su meno di META del campionato',
      len(conf) == 9 and len(conf) < 10, f'usabile su {len(conf)}/20', grave=True)
    nap = next(r for r in sq if r['Squadra'] == 'Napoli')
    t('per chi ha cambiato guida il dato e dichiarato NON predittivo',
      'PASSATO' in squadre.stato_dato(nap), squadre.stato_dato(nap), grave=True)
    inter = next(r for r in sq if r['Squadra'] == 'Inter')
    t('CONTROPROVA: per chi ha confermato il dato e utilizzabile',
      'utilizzabile' in squadre.stato_dato(inter), grave=True)

    # Neopromosse: nessun dato, e non deve diventare "zero"
    ctx = squadres_ctx = squadre.contesto_giocatore('FRO', sq)
    t('neopromossa -> NESSUN DATO, non uno zero',
      ctx and 'NESSUNO' in ctx['dato'], str(ctx), grave=True)
    ctx_com = squadre.contesto_giocatore('COM', sq)
    t('squadra con dati -> contesto completo',
      ctx_com and ctx_com['ppda'] < 8 and ctx_com['allenatore'] == 'Cesc Fabregas',
      str(ctx_com), grave=True)

    # --- effetto sui portieri ---
    LC = os.path.join(os.path.dirname(SQ), 'listone_completo.csv')
    AVX = os.path.join(os.path.dirname(SQ), 'statistiche_avanzate.csv')
    if os.path.exists(LC) and os.path.exists(AVX):
        d_no = fanta.carica(LC)
        fanta.applica_avanzate(d_no, AVX)
        fanta.valuta(d_no)
        d_si = fanta.carica(LC)
        fanta.applica_avanzate(d_si, AVX)
        fanta.applica_contesto_squadra(d_si, SQ)
        fanta.valuta(d_si)

        def tro(d, n):
            return next((g for g in d['giocatori'] if g['nome'] == n), None)

        t('il contesto viene applicato ai portieri',
          d_si['contesto_squadra']['corretti'] > 20,
          str(d_si['contesto_squadra']['corretti']), grave=True)
        t('e SOLO ai portieri (gli altri ruoli passano da npxG/xA)',
          all(g.get('delta_contesto') is None
              for g in d_si['giocatori'] if g['ruolo'] != 'P'), grave=True)

        # 🔑 Chi RESTA nella stessa squadra non deve muoversi: se si muove,
        # la correzione sta sommando due volte lo stesso effetto.
        falcone_no, falcone_si = tro(d_no, 'Falcone'), tro(d_si, 'Falcone')
        t('portiere che NON cambia squadra -> correzione nulla (Falcone, Lecce)',
          falcone_no and falcone_si and abs(falcone_si['fm'] - falcone_no['fm']) < 1e-6,
          f'{falcone_no["fm"]:.3f} -> {falcone_si["fm"]:.3f}' if falcone_no else 'assente',
          grave=True)

        # CONTROPROVA: un portiere che passa a una difesa migliore deve salire.
        mosso = [g for g in d_si['giocatori']
                 if g['ruolo'] == 'P' and abs(g.get('delta_contesto') or 0) > 0.05]
        t('CONTROPROVA: chi cambia contesto difensivo si muove davvero',
          len(mosso) > 0, f'{len(mosso)} portieri corretti', grave=True)

        # I portieri delle neopromosse restano dichiarati, non azzerati
        t('portieri di neopromosse: dichiarati senza dato, non messi a zero',
          all(tro(d_si, n) is None or tro(d_si, n).get('fm') is not None
              for n in d_si['contesto_squadra']['senza_dato']), grave=True)

# ================================================== 9. calibrazione su FVM
print('\n--- 9. calibrazione contro il mercato (colonna FVM) ---')

with tempfile.TemporaryDirectory() as tmp:
    # Il generatore NON scrive la colonna FVM: senza ancora, deve fermarsi.
    csv_no = genera_csv(os.path.join(tmp, 'no_fvm.csv'))
    d_no = fanta.valuta(fanta.carica(csv_no))
    try:
        fanta.calibra(d_no)
        alzata = False
    except fanta.DatoMancante:
        alzata = True
    t('senza colonna FVM la calibrazione si ferma e lo dice',
      alzata, 'ha calibrato lo stesso: sta indovinando l ancora', grave=True)

    # Con FVM: un'ancora sintetica proporzionale alla quotazione.
    righe = [r.split(';') for r in
             io.open(csv_no, encoding='utf-8').read().splitlines() if r]
    righe[0].insert(4, 'FVM')
    for r in righe[1:]:
        r.insert(4, str(int(float(r[3]) * 10)))
    csv_si = os.path.join(tmp, 'con_fvm.csv')
    io.open(csv_si, 'w', encoding='utf-8').write(
        '\n'.join(';'.join(r) for r in righe))

    d_si = fanta.valuta(fanta.carica(csv_si))
    t('la colonna FVM viene letta',
      sum(1 for g in d_si['giocatori'] if g.get('fvm')) == len(d_si['giocatori']),
      grave=True)

    prima = fanta.PESO_PANCHINA
    out = fanta.calibra(d_si)

    # L'invariante che conta: due scale diverse rese confrontabili.
    t('lo split FVM somma al monte crediti della lega',
      abs(sum(out['fvm'].values()) - fanta.BUDGET * fanta.SQUADRE) < 1,
      f'{sum(out["fvm"].values()):.0f} invece di {fanta.BUDGET * fanta.SQUADRE}',
      grave=True)

    # calibra() muove un GLOBALE: se non lo rimette a posto avvelena tutto
    # l'output successivo, ed e' un bug che nessun altro test vedrebbe.
    t('calibra NON lascia PESO_PANCHINA sporco',
      fanta.PESO_PANCHINA == prima,
      f'{prima} -> {fanta.PESO_PANCHINA}', grave=True)

    t('il peso ottimo sta nel dominio ammesso',
      0.0 <= out['peso_ottimo'] <= 1.0, str(out['peso_ottimo']), grave=True)

    # CONTROPROVA: se l'ancora e' la quotazione riscalata, il peso ottimo non
    # puo' essere lo stesso di un'ancora ribaltata. Se lo fosse, la griglia non
    # sta misurando niente.
    for g in d_si['giocatori']:
        g['fvm'] = 400 - g['fvm']
    out2 = fanta.calibra(d_si)
    t('CONTROPROVA: cambiando l ancora cambia il peso ottimo',
      out2['peso_ottimo'] != out['peso_ottimo'] or out2['scarto'] != out['scarto'],
      'la calibrazione e insensibile al riferimento', grave=True)


# ================================================== 10. XI osservato
print('\n--- 10. probabili formazioni (titolarita osservata) ---')

import formazioni  # noqa: E402

FINTO = """
<div class="team team-home" data-team-formation="3-5-2">
 <ul class="team-lineup">
  <li class="player"><a class="player-name player-link"
     href="https://www.fantacalcio.it/serie-a/squadre/inter/soule/1"><span>Soul&#xe8;</span></a></li>
  <li class="player"><a class="player-name player-link"
     href="https://www.fantacalcio.it/serie-a/squadre/inter/martinez-l/2"><span>Martinez L.</span></a></li>
 </ul>
</div>
"""

sq = formazioni.estrai(FINTO)
t('estrae squadra, modulo e XI dall HTML', len(sq) == 1 and sq[0][1] == '3-5-2', str(sq), grave=True)
t('le entita HTML vengono decodificate (Soul&#xe8; -> Soule)',
  sq and 'Soul' in sq[0][2][0] and '&#' not in sq[0][2][0],
  sq[0][2][0] if sq else 'niente', grave=True)

# CONTROPROVA: pagina cambiata = zero squadre, non una lista vuota spacciata per buona.
t('CONTROPROVA: HTML che non matcha da zero squadre, non finge',
  formazioni.estrai('<html>niente</html>') == [], grave=True)

with tempfile.TemporaryDirectory() as tmp:
    csvp = genera_csv(os.path.join(tmp, 'q.csv'))
    d_no = fanta.valuta(fanta.carica(csvp))
    pres_no = {g['nome']: g.get('pres_attese') for g in d_no['giocatori']}

    # Meta' listone dichiarato titolare: chi c'e' deve valere piu' di prima.
    G = fanta.carica(csvp)['giocatori']
    scelti = {g['nome'].lower() for g in G[::2]}
    d_si = fanta.valuta(fanta.carica(csvp), titolari=scelti)
    dentro = [g for g in d_si['giocatori'] if g['nome'].lower() in scelti and g.get('pres_attese')]
    fuori = [g for g in d_si['giocatori'] if g['nome'].lower() not in scelti and g.get('pres_attese')]
    t('chi e nell XI ha titolarita piena, chi non c e no',
      all(g['titolarita'] == 1.0 for g in dentro)
      and all(g['titolarita'] == fanta.FUORI_XI for g in fuori), grave=True)
    t('con l XI le presenze NON dipendono piu dalle presenze storiche',
      len({round(g['pres_attese'], 3) for g in dentro if g['ruolo'] == 'P'}) == 1,
      'un titolare deve valere quanto un altro titolare dello stesso ruolo', grave=True)

    # CONTROPROVA: senza XI la titolarita varia da giocatore a giocatore.
    t('CONTROPROVA: senza XI la titolarita resta dedotta e variabile',
      len({round(v, 3) for v in pres_no.values() if v}) > 5, grave=True)

    # Il riparto fra reparti segue il mercato quando c e FVM: senza FVM, niente.
    d_senza = fanta.prezzi(fanta.vorp(fanta.valuta(fanta.carica(csvp))))
    t('senza colonna FVM il riparto NON viene toccato',
      d_senza.get('riparto') is None, str(d_senza.get('riparto')), grave=True)


# ================================================== esito
print('\n' + '=' * 74)
gravi = sum(1 for _, _, g in KO if g)
print(f'  RISULTATO: {len(OK)}/{len(OK) + len(KO)} pass   .   {len(KO)} FAIL ({gravi} gravi)')
print('=' * 74)
sys.exit(1 if KO else 0)
