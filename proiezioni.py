# -*- coding: utf-8 -*-
"""proiezioni - quanto fara' un giocatore la prossima giornata, e con che incertezza.

Tre numeri per giocatore, ognuno con la sua fonte dichiarata:

- **mu**: fantavoto atteso SE gioca. Media bayesiana fra un prior (la stagione
  scorsa dal listone, o la quotazione per chi arriva dall'estero, o la media di
  ruolo) e i fantavoti di questa stagione. Il peso del prior vale K_PRIOR
  partite: dopo 3 giornate comanda ancora il passato, dopo 15 il presente.
- **sd**: quanto ballano i suoi fantavoti. Serve negli scontri diretti, dove
  la varianza e' una scelta (v. schiera.py).
- **p**: probabilita' che scenda in campo con voto. Dalle probabili
  formazioni se ci sono, altrimenti da quante partite della sua squadra ha
  giocato quest'anno. Squalificato = 0, e si dice perche'.

## Le stime, dichiarate

    K_PRIOR = 6       partite di prior: 1 partita da 12 non batte 10 da 7.5
    P_XI    = 0.90    chi e' nelle probabili gioca ~9 volte su 10 [STIMA]
    P_FUORI = 0.15    chi non c'e' entra ~1,5 volte su 10 con voto [STIMA]

Le ultime due sono il punto piu' debole: le probabili sbagliano, e di quanto
non l'ho misurato. Si misura a fine girone confrontando titolari.csv del
giovedi' con i voti della domenica - ed e' il primo lavoro da fare.

## Cosa NON fa

Non modella gli infortuni oltre alle probabili, non sa chi batte i rigori, non
distingue un 7 in casa col Monza da un 7 a San Siro: la correzione di
calendario e' in per_giornata(), ed e' volutamente piccola (tocca solo i
bonus, non il voto base).
"""
import bisect
import copy
import math

import nomi
import regole

K_PRIOR = 6.0
K_SD = 4.0
P_XI = 0.90
P_FUORI = 0.15
P_IGNOTO = 0.5
# [STIMA] I fantavoti si tagliano a media di ruolo +- CODA deviazioni prima di
# farne la media. Il fantavoto ha code grasse: una doppietta e' un salto di +6,
# non rumore gaussiano, e con la media semplice una sola partita da 12 pesava
# piu' di dieci partite da 7,5 (trovato dal test, non ipotizzato). La doppietta
# resta informazione - alza la stima - ma non la trascina.
CODA = 2.0
REGRESSIONE = 0.35       # come fanta.py: verso la media di ruolo

# [STIMA] valori di ripiego quando non c'e' nessun dato del ruolo
FM_RUOLO = {'P': 5.2, 'D': 6.0, 'C': 6.3, 'A': 6.7}
MV_RUOLO = {'P': 6.1, 'D': 5.95, 'C': 6.0, 'A': 6.05}
SD_RUOLO = {'P': 1.4, 'D': 1.3, 'C': 1.5, 'A': 2.1}
SD_V_RUOLO = 0.6
SD_MIN = 0.5
SD_V_MIN = 0.3


def giocatori(E):
    """Le stime senza le chiavi di servizio ('_ruoli')."""
    return {k: v for k, v in E.items() if not k.startswith('_')}


def _media(v):
    return sum(v) / len(v) if v else None


def _var(v):
    if len(v) < 2:
        return None
    m = _media(v)
    return sum((x - m) ** 2 for x in v) / (len(v) - 1)


def _ruoli(S, listone):
    """Media e dispersione di riferimento per ruolo, dal dato migliore disponibile."""
    out = {}
    for r in regole.RUOLI:
        fv, vv, var_fv, var_v = [], [], [], []
        if S:
            for g in S['giocatori'].values():
                if g['ruolo'] != r:
                    continue
                fv += g['fv']
                vv += g['voti']
                if g['presenze'] >= 3:
                    var_fv.append(_var(g['fv']))
                    var_v.append(_var(g['voti']))
        if listone and not fv:
            L = [x for x in listone if x['ruolo'] == r and x.get('fm') is not None
                 and (x.get('pres') or 0) >= 10]
            fv = [x['fm'] for x in L]
            vv = [x['mv'] for x in L if x.get('mv') is not None]
        sd = math.sqrt(_media(var_fv)) if len(var_fv) >= 5 else SD_RUOLO[r]
        sd_v = math.sqrt(_media(var_v)) if len(var_v) >= 5 else SD_V_RUOLO
        out[r] = {'mu': _media(fv) if fv else FM_RUOLO[r],
                  'mv': _media(vv) if vv else MV_RUOLO[r],
                  'sd': max(sd, 0.8), 'sd_v': max(sd_v, SD_V_MIN)}
    return out


def _prior(x, ruoli, per_ruolo_q):
    """(mu, mv, fonte) dal listone per un giocatore."""
    r = x['ruolo']
    rif = ruoli[r]
    if x.get('fm') is not None:
        w = min(1.0, (x.get('pres') or 0) / 25.0)
        reg = REGRESSIONE + (1 - REGRESSIONE) * (1 - w)
        mv = x.get('mv') if x.get('mv') is not None else rif['mv']
        return ((1 - reg) * x['fm'] + reg * rif['mu'],
                (1 - reg) * mv + reg * rif['mv'], 'listone')
    q = per_ruolo_q.get(r)
    if q and x.get('quota'):
        quote, fms = q
        # percentile della quotazione nel ruolo -> fantamedia allo stesso
        # percentile fra chi lo storico ce l'ha. Poi regressione forte (0.5):
        # la quotazione e' consenso di mercato, non una misura.
        pc = bisect.bisect_left(quote, x['quota']) / max(1, len(quote) - 1)
        fm = fms[min(int(pc * (len(fms) - 1)), len(fms) - 1)]
        return 0.5 * fm + 0.5 * rif['mu'], rif['mv'], 'quotazione'
    return rif['mu'], rif['mv'], 'media di ruolo'


def stima(S=None, listone=None, titolari=None, R=None, prossima=True):
    """{chiave_giocatore: {nome, ruolo, squadra, mu, sd, mv, sd_v, p, n, stato, fonte}}
    piu' '_ruoli' con i riferimenti per ruolo.

    `prossima=False` = stima per le giornate successive alla prossima: la
    squalifica resta scritta in `stato` ma non azzera la probabilita' di
    giocare (si sconta in una giornata sola)."""
    R = R or regole.carica_lega(None)
    listone = listone or []
    ruoli = _ruoli(S, listone)
    ultima = S['giornate'][-1] if S and S['giornate'] else None

    per_ruolo_q = {}
    for r in regole.RUOLI:
        con = [x for x in listone if x['ruolo'] == r and x.get('fm') is not None]
        if len(con) >= 5:
            per_ruolo_q[r] = (sorted(x['quota'] for x in listone if x['ruolo'] == r and x.get('quota')),
                              sorted(x['fm'] for x in con))

    L = {nomi.giocatore(x['nome']): x for x in listone}
    Sg = S['giocatori'] if S else {}
    out = {'_ruoli': ruoli}
    for k in set(L) | set(Sg):
        x, s = L.get(k), Sg.get(k)
        ruolo = (s or x)['ruolo']
        rif = ruoli[ruolo]
        if x:
            p_mu, p_mv, fonte = _prior(x, ruoli, per_ruolo_q)
        else:
            p_mu, p_mv, fonte = rif['mu'], rif['mv'], 'media di ruolo'
        n = s['presenze'] if s else 0
        fv = s['fv'] if s else []
        vv = s['voti'] if s else []
        # la dispersione usata per il taglio non scende mai sotto quella di
        # riferimento del ruolo: con pochi dati (o dati troppo regolari) il taglio
        # diventerebbe una ghigliottina anche per chi e' davvero forte
        ampiezza = CODA * max(rif['sd'], SD_RUOLO[ruolo])
        lo, hi = rif['mu'] - ampiezza, rif['mu'] + ampiezza
        mu = (K_PRIOR * p_mu + sum(min(max(v, lo), hi) for v in fv)) / (K_PRIOR + n)
        mv = (K_PRIOR * p_mv + sum(vv)) / (K_PRIOR + n)
        var = _var(fv) or 0.0
        var_v = _var(vv) or 0.0
        sd = math.sqrt((K_SD * rif['sd'] ** 2 + max(n - 1, 0) * var) / (K_SD + max(n - 1, 0)))
        sd_v = math.sqrt((K_SD * rif['sd_v'] ** 2 + max(n - 1, 0) * var_v) / (K_SD + max(n - 1, 0)))

        squadra = (s['squadra'] if s and s['squadra'] else nomi.squadra(x['squadra']) if x else '')
        if titolari is not None:
            p = P_XI if k in titolari else P_FUORI
            fonte_p = 'probabili'
        elif s and S['partite_squadra'].get(squadra):
            p = (n + 1.0) / (S['partite_squadra'][squadra] + 2.0)
            fonte_p = f'{n}/{S["partite_squadra"][squadra]} partite della squadra'
        elif x and x.get('pres'):
            p = min(0.9, max(0.1, x['pres'] / 38.0))
            fonte_p = 'presenze della stagione scorsa'
        else:
            p, fonte_p = P_IGNOTO, 'nessun dato'

        stato = ''
        if s and ultima is not None:
            if s['espulso_in'] == ultima:
                stato = 'squalificato'
            else:
                c = regole.cartellini(s['gialli'])
                if c == 'squalificato' and s['giallo_in'] == ultima:
                    stato = 'squalificato'
                elif c == 'diffidato':
                    stato = 'diffidato'
        if stato == 'squalificato' and prossima:
            p, fonte_p = 0.0, 'squalificato'

        out[k] = {'k': k, 'nome': (s or x)['nome'], 'ruolo': ruolo, 'squadra': squadra,
                  'mu': mu, 'mv': mv, 'sd': max(sd, SD_MIN), 'sd_v': max(sd_v, SD_V_MIN),
                  'p': p, 'n': n, 'stato': stato,
                  'fonte': ('stagione + ' + fonte) if n else fonte, 'fonte_p': fonte_p}
    return out


def per_giornata(E, partite, F, giornata, R):
    """Copia delle stime con mu corretto per l'avversario di quella giornata.

    Il mu del giocatore contiene gia' la forza MEDIA della sua squadra (ci ha
    giocato tutte le partite). Quindi la correzione e' relativa alla partita
    tipica della sua squadra, non alla media del campionato - altrimenti
    l'attaccante dell'Inter verrebbe premiato due volte per essere dell'Inter.

    - D/C/A: si scalano solo i BONUS attesi (mu - mv) col rapporto fra i gol
      attesi di questa partita e quelli di una partita tipica.
    - P: gol subiti attesi della partita contro quelli tipici, per il malus
      della lega; piu' la porta inviolata, se la lega la premia.
    """
    import calendario
    out = copy.deepcopy(E)
    malus = abs(R['bonus']['gol_subito'])
    inviolata = R['bonus']['porta_inviolata']
    for k, g in giocatori(out).items():
        m = calendario.partita(partite, g['squadra'], giornata) if g['squadra'] else None
        if m is None:
            g['avv'], g['casa'] = None, None
            continue
        avv, casa = m
        me = F['squadre'].get(g['squadra'], {'att': 1.0, 'dif': 1.0})
        g['avv'], g['casa'] = avv, casa
        if g['ruolo'] == 'P':
            xs = calendario.xg(avv, g['squadra'], not casa, F)
            tipico = F['media'] * me['dif']
            g['mu'] += (tipico - xs) * malus + inviolata * (math.exp(-xs) - math.exp(-tipico))
            g['xg_subiti'] = xs
        else:
            xf = calendario.xg(g['squadra'], avv, casa, F)
            tipico = F['media'] * me['att']
            g['mu'] += max(g['mu'] - g['mv'], 0.0) * (xf / tipico - 1.0)
            g['xg_fatti'] = xf
    return out
