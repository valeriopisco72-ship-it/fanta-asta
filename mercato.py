# -*- coding: utf-8 -*-
"""mercato - scambi e svincolati, misurati su quello che cambiano nella TUA formazione.

## L'errore che fanno tutti

Uno scambio si valuta sommando i valori: "do Tizio (fantamedia 6,5) e prendo
Caio (7), ci guadagno". E' il VORP dell'asta dimenticato a settembre. Caio vale
per te quanto cambia la formazione che schieri ogni domenica:

- se Caio finisce in panchina dietro a tre titolari migliori, vale ~0;
- se Tizio era il tuo unico portiere affidabile, perderlo costa molto piu'
  della sua fantamedia, perche' al suo posto gioca il secondo portiere.

Questo modulo stampa ENTRAMBI i numeri: la somma grezza e l'effetto sulla
formazione, giornata per giornata col calendario vero. La differenza fra i due
e' il motivo per cui esiste.

## Svincolati

Per ogni giocatore libero: quanto guadagna la tua formazione se lo prendi e
tagli il peggiore del suo ruolo che ti conviene tagliare. Si propone solo chi
guadagna davvero. Per restare veloce si provano solo i liberi che battono
almeno il tuo peggiore del ruolo (in mu x p) e i due tagli piu' probabili per
ruolo: e' un filtro, dichiarato, non un'esplorazione completa.

Uso: via socio.py (`python socio.py scambio ...`, `python socio.py svincolati`).
"""
import csv
import os

import fanta
import nomi
import schiera

COL_FANTA = ['fantasquadra', 'squadrafanta', 'fanta', 'proprietario', 'allenatore',
             'team', 'fantateam', 'squadra']
COL_NOME = ['nome', 'giocatore', 'calciatore']


def carica_rose(path='rose.csv'):
    """{fantasquadra: [chiavi giocatore]} da un CSV FantaSquadra;Nome[;Ruolo;Prezzo]."""
    if not path or not os.path.exists(path):
        return {}
    import voti
    righe = voti._righe(path)
    norm = [fanta._norm(c) for c in righe[0]]
    cf = next((norm.index(c) for c in COL_FANTA if c in norm), None)
    cn = next((norm.index(c) for c in COL_NOME if c in norm), None)
    if cf is None or cn is None:
        raise fanta.DatoMancante(f'{path}: servono le colonne FantaSquadra e Nome')
    out = {}
    for r in righe[1:]:
        if len(r) > max(cf, cn) and r[cf].strip() and r[cn].strip():
            out.setdefault(r[cf].strip(), []).append(nomi.giocatore(r[cn]))
    return out


def salva_rose(rose, nomi_leggibili, path='rose.csv'):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['FantaSquadra', 'Nome'])
        for sq, L in rose.items():
            for k in L:
                w.writerow([sq, nomi_leggibili.get(k, k)])


def _rosa(chiavi, E):
    return [E[k] for k in chiavi if k in E]


def valore(chiavi, Es, R):
    """Fantapunti attesi della formazione migliore, sommati sulle giornate."""
    tot = 0.0
    for E in Es:
        f = schiera.migliore_semplice(_rosa(chiavi, E), R)
        tot += schiera.valore_atteso(f) if f else 0.0
    return tot


def chiave(x, universo):
    """Il nome come l'hai scritto se e' gia' una chiave, altrimenti normalizzato."""
    return x if x in universo else nomi.giocatore(x)


def scambio(mia, dai, ricevi, Es, R):
    dai = [chiave(x, mia) for x in dai]
    ricevi = [chiave(x, Es[0]) for x in ricevi]
    manca = [x for x in dai if x not in mia]
    ignoti = [x for x in ricevi if x not in Es[0]]
    if manca or ignoti:
        return {'errore': (f'non in rosa: {", ".join(manca)}' if manca else '')
                + (f' sconosciuti: {", ".join(ignoti)}' if ignoti else '')}
    dopo = [k for k in mia if k not in dai] + ricevi
    prima_v, dopo_v = valore(mia, Es, R), valore(dopo, Es, R)
    grezzo = sum(E[k]['mu'] * E[k]['p'] for E in Es for k in ricevi if k in E) - \
        sum(E[k]['mu'] * E[k]['p'] for E in Es for k in dai if k in E)
    return {'prima': prima_v, 'dopo': dopo_v, 'delta': dopo_v - prima_v,
            'delta_grezzo': grezzo, 'giornate': len(Es)}


def svincolati(mia, occupati, Es, R, ruolo=None, top=10, per_ruolo=25):
    E0 = Es[0]
    base = valore(mia, Es, R)
    mie = _rosa(mia, E0)
    out = []
    for r in 'PDCA':
        if ruolo and r != ruolo:
            continue
        miei_r = sorted((g for g in mie if g['ruolo'] == r), key=lambda g: g['mu'] * g['p'])
        if not miei_r:
            continue
        soglia = miei_r[0]['mu'] * miei_r[0]['p']
        liberi = sorted((g for k, g in E0.items() if not k.startswith('_') and k not in occupati
                         and g['ruolo'] == r and g['p'] > 0 and g['mu'] * g['p'] > soglia),
                        key=lambda g: -g['mu'] * g['p'])[:per_ruolo]
        for lib in liberi:
            migliore = None
            for tagliato in miei_r[:2]:
                nuova = [k for k in mia if k != tagliato['k']] + [lib['k']]
                gain = valore(nuova, Es, R) - base
                if migliore is None or gain > migliore[0]:
                    migliore = (gain, tagliato['k'])
            if migliore and migliore[0] > 0.05:
                out.append({'k': lib['k'], 'nome': lib['nome'], 'ruolo': r,
                            'squadra': lib.get('squadra', ''), 'guadagno': migliore[0],
                            'taglia': migliore[1], 'mu': lib['mu'], 'p': lib['p']})
    return sorted(out, key=lambda x: -x['guadagno'])[:top]
