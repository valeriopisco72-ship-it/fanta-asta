# -*- coding: utf-8 -*-
"""regole - il regolamento della TUA lega, in un posto solo.

Ogni lega ha il suo: bonus gol diversi per ruolo, porta inviolata si' o no,
fasce gol a passo 6 o a tabella, modificatore di difesa acceso o spento. Un
tool che ne assume uno solo sbaglia in silenzio in tutte le altre leghe.
Qui ci sono i default piu' diffusi, e `lega.json` sovrascrive SOLO quello che
dichiara (fusione profonda: cambiare il gol del difensore non cancella quello
dell'attaccante).

Default e fonti [pub] (regolamento Classic di Fantacalcio.it e guide collegate,
verificati il 28/09/2026 via ricerca; le leghe private li cambiano spesso):

- gol +3, assist +1, rigore parato +3, rigore sbagliato -3, autogol -2,
  ammonizione -0.5, espulsione -1, gol subito dal portiere -1
- porta inviolata: 0 di default (molte leghe danno +1: si accende da lega.json)
- fasce gol: 66 = 1 gol, poi uno ogni 6 punti (72, 78, 84...). Molte leghe
  usano la tabella precaricata 66/72/77/81/85/89: si passa come lista.
- modificatore di difesa: media voto (SENZA bonus/malus) del portiere e dei 3
  migliori difensori, solo se i difensori schierati sono almeno 4.
  >= 6.00 -> +1, >= 6.50 -> +3, >= 7.00 -> +6.
- modificatore rendimento (spento di default): solo se tutti e 11 prendono
  voto, 8/9/10/11 sufficienze -> +0,5/+1/+2/+3.
- fattore capitano (spento di default): sul voto puro del capitano, o del
  vice se il capitano non scende in campo; da -1,5 (<=4,5) a +1,5 (>=7,5).
- squalifiche per somma di ammonizioni in Serie A [pub]: alla 5a, poi dopo
  altre 5, 4, 3, 2 e da li' ogni ammonizione (5, 10, 14, 17, 19, 20, 21...).

Uso da codice:
    R = regole.carica_lega('lega.json')      # None = solo default
    regole.fantavoto(riga, 'A', R)
    regole.gol(71.5, R)                      # -> 1
"""
import copy
import json
import os

DEFAULT = {
    # --- la lega ---
    'nome': 'la mia lega',
    'mia': None,                  # nome della TUA fantasquadra in rose.csv
    'formula': 'scontri',         # 'scontri' (fasce gol, 3-1-0) o 'punti' (somma)
    'squadre': 10,
    'budget': 500,
    'slot': {'P': 3, 'D': 8, 'C': 8, 'A': 6},
    # --- il punteggio ---
    'bonus': {
        'gol': {'P': 3.0, 'D': 3.0, 'C': 3.0, 'A': 3.0},
        'assist': 1.0,
        'rigore_parato': 3.0,
        'rigore_sbagliato': -3.0,
        # [dav] Nel file voti di Fantacalcio.it la colonna Gf dovrebbe gia'
        # comprendere i rigori segnati (Rf). Se nella tua lega il rigore vale
        # diverso dal gol, metti False e il bonus sotto.
        'gf_include_rigori': True,
        'rigore_segnato': 3.0,
        'autogol': -2.0,
        'ammonizione': -0.5,
        'espulsione': -1.0,
        'gol_subito': -1.0,       # solo portiere
        'porta_inviolata': 0.0,   # solo portiere, solo con voto e zero gol subiti
    },
    'soglie': {'prima': 66.0, 'passo': 6.0},   # oppure una lista [66, 72, 77, ...]
    'modificatore': {
        'attivo': True,
        'min_difensori': 4,
        # True: media di portiere + 3 migliori difensori. False: 4 migliori difensori.
        'portiere_incluso': True,
        'fasce': [[6.0, 1.0], [6.5, 3.0], [7.0, 6.0]],
    },
    # Modificatore rendimento: solo se TUTTI gli 11 prendono voto, bonus per
    # numero di sufficienze (voto puro >= 6). Spento di default.
    'rendimento': {
        'attivo': False,
        'fasce': [[8, 0.5], [9, 1.0], [10, 2.0], [11, 3.0]],
    },
    # Capitano: bonus/malus sul VOTO PURO del capitano (o del vice, se il
    # capitano non gioca). 'giocatore'/'vice' sono nomi come nel listone;
    # socio.py li risolve nelle chiavi 'k'/'kv' della rosa. Spento di default.
    'capitano': {
        'attivo': False,
        'giocatore': None,
        'vice': None,
        'fasce': [[0.0, -1.5], [5.0, -1.0], [5.5, -0.5], [6.0, 0.0],
                  [6.5, 0.5], [7.0, 1.0], [7.5, 1.5]],
    },
    # --- la formazione ---
    'moduli': ['3-4-3', '3-5-2', '4-3-3', '4-4-2', '4-5-1', '5-3-2', '5-4-1'],
    'panchina': 7,                # quanti in panchina
    'max_sostituzioni': 3,
}

RUOLI = ('P', 'D', 'C', 'A')

# Squalifica per somma di ammonizioni in Serie A [pub]: soglie esplicite fino
# a 19, poi una ad ogni cartellino.
SOGLIE_GIALLI = (5, 10, 14, 17, 19)


def _fondi(base, sopra):
    """Fusione profonda: `sopra` vince solo sulle chiavi che dichiara."""
    out = copy.deepcopy(base)
    for k, v in (sopra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _fondi(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def carica_lega(path='lega.json', extra=None):
    """Default <- lega.json (se c'e') <- extra (per i test e la riga di comando)."""
    R = copy.deepcopy(DEFAULT)
    if path and os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            R = _fondi(R, json.load(f))
    return _fondi(R, extra)


# ------------------------------------------------------------------ PUNTEGGIO

def _n(v):
    """Numero o 0: nei file voti le celle vuote significano zero eventi."""
    if v is None or v == '':
        return 0.0
    try:
        return float(str(v).replace(',', '.'))
    except ValueError:
        return 0.0


def fantavoto(r, ruolo, R):
    """Voto + bonus - malus. None se il giocatore e' senza voto.

    Senza voto non e' zero: in Classic entra la panchina. Confondere i due casi
    e' il modo piu' rapido di sbagliare una media.
    """
    if r.get('voto') is None:
        return None
    b = R['bonus']
    fv = float(r['voto'])
    fv += _n(r.get('gf')) * b['gol'][ruolo]
    if not b['gf_include_rigori']:
        fv += _n(r.get('rf')) * b['rigore_segnato']
    fv += _n(r.get('ass')) * b['assist']
    fv += _n(r.get('rp')) * b['rigore_parato']
    fv += _n(r.get('rs')) * b['rigore_sbagliato']
    fv += _n(r.get('au')) * b['autogol']
    fv += _n(r.get('amm')) * b['ammonizione']
    fv += _n(r.get('esp')) * b['espulsione']
    if ruolo == 'P':
        gs = _n(r.get('gs'))
        fv += gs * b['gol_subito']
        if gs == 0:
            fv += b['porta_inviolata']
    return fv


def bonus_netto(r, ruolo, R):
    """Solo la parte bonus/malus del fantavoto: e' quella che il calendario muove."""
    fv = fantavoto(r, ruolo, R)
    return None if fv is None else fv - float(r['voto'])


def gol(punti, R):
    """Fantapunti -> gol, con le fasce della lega."""
    s = R['soglie']
    if isinstance(s, (list, tuple)):
        s = sorted(s)
        n = sum(1 for x in s if punti >= x)
        # Oltre l'ultima soglia della tabella si prosegue col passo dell'ultima
        # fascia: fermarsi vorrebbe dire che 120 punti fanno quanto 89.
        if n == len(s) and len(s) >= 2:
            n += int((punti - s[-1]) // (s[-1] - s[-2]))
        return n
    if punti < s['prima']:
        return 0
    return 1 + int((punti - s['prima']) // s['passo'])


def modificatore(voto_portiere, voti_difensori, R):
    """Bonus di squadra dal modificatore di difesa.

    `voti_difensori` = voti PURI (senza bonus/malus) dei difensori schierati
    che hanno preso voto. Se sono meno del minimo, niente modificatore.
    """
    M = R['modificatore']
    if not M['attivo']:
        return 0.0
    voti = [v for v in voti_difensori if v is not None]
    if len(voti) < M['min_difensori']:
        return 0.0
    if M.get('portiere_incluso', True):
        if voto_portiere is None:
            return 0.0
        media = (voto_portiere + sum(sorted(voti, reverse=True)[:3])) / 4.0
    else:
        media = sum(sorted(voti, reverse=True)[:4]) / 4.0
    # arrotondato al centesimo: 6.4999999 per errore di virgola mobile non e' 6.49
    return _fascia(round(media, 2), M['fasce'], 0.0)


def _fascia(x, fasce, sotto):
    """Il bonus della fascia piu' alta con soglia <= x; `sotto` se nessuna."""
    esito = sotto
    for soglia, bonus in sorted(fasce):
        if x >= soglia:
            esito = bonus
    return esito


def rendimento(voti_undici, R):
    """Modificatore rendimento: None fra i voti (o meno di 11) = non scatta."""
    M = R.get('rendimento') or {}
    if not M.get('attivo') or len(voti_undici) < 11 or any(v is None for v in voti_undici):
        return 0.0
    return _fascia(sum(1 for v in voti_undici if v >= 6.0), M['fasce'], 0.0)


def capitano(voto, R):
    """Fattore capitano sul voto puro. Sotto la prima soglia vale la prima fascia."""
    M = R.get('capitano') or {}
    if not M.get('attivo') or voto is None:
        return 0.0
    fasce = sorted(M['fasce'])
    return _fascia(voto, fasce, fasce[0][1])


def esito_partita(gol_mio, gol_avv):
    """Punti in classifica: 3 vittoria, 1 pareggio, 0 sconfitta."""
    return 3 if gol_mio > gol_avv else (1 if gol_mio == gol_avv else 0)


# ------------------------------------------------------------------ FORMAZIONE

def modulo(m):
    """'3-4-3' -> {'P': 1, 'D': 3, 'C': 4, 'A': 3}."""
    d, c, a = (int(x) for x in m.split('-'))
    return {'P': 1, 'D': d, 'C': c, 'A': a}


# ------------------------------------------------------------------ CARTELLINI

def _soglie_gialli(fino_a):
    s = list(SOGLIE_GIALLI)
    while s[-1] < fino_a:
        s.append(s[-1] + 1)
    return s


def cartellini(n_gialli):
    """'' / 'diffidato' (al prossimo giallo salta) / 'squalificato' (appena scattata)."""
    n = int(n_gialli)
    s = _soglie_gialli(n + 1)
    if n in s:
        return 'squalificato'
    if n + 1 in s:
        return 'diffidato'
    return ''
