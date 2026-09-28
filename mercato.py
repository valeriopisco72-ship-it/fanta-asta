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
import regole
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


# ------------------------------------------------------------------ TABELLA DELL'APP

COL_TAB = {
    'fantasquadra': ['fantasquadra', 'squadrafanta', 'fanta', 'proprietario', 'fantateam'],
    'nome': COL_NOME,
    'ruolo': ['ruolo', 'r'],
    'squadra': ['squadra', 'sq', 'club'],
    'mv': ['mv', 'mediavoto'],
    'fm': ['fm', 'fantamedia'],
    'fvm': ['fvmp', 'fvm', 'fantavalore'],
    'costo': ['costo', 'prezzo', 'crediti'],
    'pv': ['pv', 'presenze', 'partite'],
}


def carica_tabella(path):
    """Righe della tabella rose dell'app: fantasquadra, nome, ruolo, squadra, MV,
    FM, FVMp, costo, Pv (se c'e'). MV e FM a zero = nessun voto (None)."""
    import voti
    righe = voti._righe(path)
    norm = [fanta._norm(c) for c in righe[0]]
    col = {k: next((norm.index(c) for c in cand if c in norm), None) for k, cand in COL_TAB.items()}
    if col['nome'] is None or col['ruolo'] is None:
        raise fanta.DatoMancante(f'{path}: servono almeno Nome e Ruolo')
    out = []
    for r in righe[1:]:
        def get(k):
            i = col[k]
            return r[i].strip() if i is not None and i < len(r) else ''
        if not get('nome'):
            continue
        rec = {'fantasquadra': get('fantasquadra'), 'nome': get('nome'),
               'ruolo': get('ruolo').upper(), 'squadra': get('squadra')}
        for k in ('mv', 'fm', 'fvm', 'costo', 'pv'):
            rec[k] = fanta._num(get(k))
        if not rec['mv']:
            rec['mv'] = rec['fm'] = None
        out.append(rec)
    return out


# ------------------------------------------------------------------ PROPOSTE

def proposte(mia, rose, Es, R, top=10, min_lui=0.1, deboli=2, intoccabili=()):
    """Scambi che migliorano la TUA formazione e anche la sua: gli unici che
    hanno una possibilita' di essere accettati.

    Il vantaggio reciproco non viene dagli 1-per-1 a pari ruolo (li' quello che
    guadagni tu lo perde lui, a meno di differenze di panchina), ma dallo
    scambio di ECCEDENZE fra reparti: il tuo centrocampista forte che sta in
    panchina per il suo difensore forte che sta in panchina, ciascuno con uno
    scarto dell'altro reparto per tenere la rosa a 3/8/8/6. Si provano gli
    1-per-1 e questi 2-per-2. Filtro dichiarato, per restare sotto il minuto: i
    "forti" di un reparto sono quelli che possono partire titolari in almeno un
    modulo PIU' UNO - l'eccedenza piu' preziosa e' proprio il primo fuori, e un
    filtro sui soli titolari (trovato dal test) la escludeva; i "deboli" sono
    gli ultimi `deboli` del reparto.
    """
    E0 = Es[0]
    forti = {r: max(regole.modulo(m)[r] for m in R['moduli']) + 1 for r in 'PDCA'}
    # `intoccabili` = chi non si offre mai: capitano e vice designati per la
    # stagione (il valore della formazione non vede il fattore capitano, quindi
    # senza questo il socio proponeva di cedere il capitano)
    intoccabili = set(intoccabili)
    mie = [k for k in rose[mia] if k in E0]
    base_me = valore(mie, Es, R)

    def val_g(k):
        return E0[k]['mu'] * E0[k]['p']

    def per_ruolo(chiavi, r):
        return sorted((k for k in chiavi if E0[k]['ruolo'] == r), key=val_g, reverse=True)

    out, visti = [], set()
    for nome, sue in rose.items():
        if nome == mia:
            continue
        sue = [k for k in sue if k in E0]
        base_lui = None
        cand = []
        for r in 'PDCA':
            cand += [([a], [b]) for a in per_ruolo(mie, r) for b in per_ruolo(sue, r)]
        for ra in 'PDCA':
            for rb in 'PDCA':
                if ra == rb:
                    continue
                cand += [([x, y], [u, v])
                         for x in per_ruolo(mie, ra)[:forti[ra]] for y in per_ruolo(mie, rb)[-deboli:]
                         for u in per_ruolo(sue, ra)[-deboli:] for v in per_ruolo(sue, rb)[:forti[rb]]]
        for dai, ricevi in cand:
            if intoccabili & set(dai):
                continue
            firma = (nome, tuple(sorted(dai)), tuple(sorted(ricevi)))
            if firma in visti:
                continue
            visti.add(firma)
            per_me = valore([k for k in mie if k not in dai] + ricevi, Es, R) - base_me
            if per_me <= 0.05:
                continue
            if base_lui is None:
                base_lui = valore(sue, Es, R)
            per_lui = valore([k for k in sue if k not in ricevi] + dai, Es, R) - base_lui
            if per_lui >= min_lui:
                out.append({'avversario': nome, 'dai': dai, 'ricevi': ricevi,
                            'per_me': per_me, 'per_lui': per_lui})
    return sorted(out, key=lambda x: (-round(x['per_me'], 2), -x['per_lui']))[:top]
