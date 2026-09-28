# -*- coding: utf-8 -*-
"""piano_asta - la rosa da costruire, e il prezzo massimo vero di ogni giocatore.

Due numeri per ogni giocatore, e un piano:

- **forchetta di mercato** (da `mercato_asta`): quanto lo paghera' la tua lega;
- **tetto**: il prezzo oltre il quale la rosa migliore la fai SENZA di lui. Non
  e' "quanto vale in assoluto": e' il prezzo di indifferenza fra la miglior
  rosa che lo contiene e la miglior rosa che non lo contiene, con lo stesso
  budget e gli stessi vincoli. Tiene conto delle alternative e dei reparti gia'
  coperti;
- **piano**: reparto per reparto nell'ordine di chiamata, i bersagli con
  forchetta, tetto e due alternative, e il budget da non superare.

## Il valore

Il valore di una rosa e' quello del socio: fantapunti attesi a giornata della
formazione migliore con la panchina che entra davvero (`schiera`). La versione
esatta costa 0,84 ms; l'ottimizzatore e il tetto ne chiedono centinaia di
migliaia, quindi usano `valore_rapido`: la stessa matematica per reparto
(Poisson-binomiale sui giocatori ordinati per fantavoto atteso) con la panchina
non limitata. Con panchina lunga coincidono (un test lo impone); con panchina
corta la rapida sopravvaluta un po' le rose profonde. I report usano l'esatta.

Spec: docs/superpowers/specs/2026-09-28-piano-asta-design.md (par. 4-8)
"""
import random

import nomi
import proiezioni
import regole
import schiera


def valori(listone, R, titolari=None):
    """Stime dei giocatori del listone (senza '_ruoli'), per il piano d'asta."""
    E = proiezioni.stima(S=None, listone=listone, titolari=titolari, R=R, prossima=False)
    return proiezioni.giocatori(E)


def valore_rosa(chiavi, E, R, giornate=1):
    """Fantapunti attesi della formazione migliore (esatto), per le giornate."""
    f = schiera.migliore_semplice([E[k] for k in chiavi if k in E], R)
    return schiera.valore_atteso(f) * giornate if f else 0.0


def _per_ruolo(chiavi, E):
    out = {r: [] for r in regole.RUOLI}
    for k in chiavi:
        if k in E:
            out[E[k]['ruolo']].append(E[k])
    for r in out:
        out[r].sort(key=lambda g: g['mu'], reverse=True)
    return out


def _v_ruolo(lista, n, cache=None):
    """Valore esatto del reparto con n titolari (panchina = tutto il resto)."""
    if cache is None:
        return schiera.valore_ruolo(lista, n)
    chiave = (tuple(g['k'] for g in lista), n)
    if chiave not in cache:
        cache[chiave] = schiera.valore_ruolo(lista, n)
    return cache[chiave]


def valore_rapido(chiavi, E, R, cache=None):
    """Valore di rosa per l'ottimizzatore: max sui moduli della somma per reparto."""
    per = _per_ruolo(chiavi, E)
    migliore = 0.0
    for m in R['moduli']:
        n = regole.modulo(m)
        if any(len(per[r]) < n[r] for r in regole.RUOLI):
            continue
        migliore = max(migliore, sum(_v_ruolo(per[r], n[r], cache) for r in regole.RUOLI))
    return migliore


# ------------------------------------------------------------------ OTTIMIZZATORE

CANDIDATI_RUOLO = 40      # i migliori per mu*p di ogni reparto...
ECONOMICI_RUOLO = 10      # ...piu' i piu' economici, per poter sempre chiudere la rosa
COPPIE_UP, COPPIE_DOWN = 60, 200


def rispetta(rosa, prezzi, E, vincoli):
    """Vincoli dello studio d'asta: crediti totali sui portieri, quanti nella fascia media."""
    if sum(prezzi[k] for k in rosa if E[k]['ruolo'] == 'P') > vincoli.get('portieri_max', float('inf')):
        return False
    lo, hi = vincoli.get('fascia_media', (25, 49))
    ok = vincoli.get('scouting_ok', set())
    medi = sum(1 for k in rosa if lo <= prezzi[k] <= hi and k not in ok)
    return medi <= vincoli.get('fascia_media_max', float('inf'))


def _pool(E, prezzi, slot, fissati, esclusi):
    pool = {}
    for r in regole.RUOLI:
        tutti = [k for k in E if E[k]['ruolo'] == r and k not in esclusi and k in prezzi]
        forti = sorted(tutti, key=lambda k: (-E[k]['mu'] * E[k]['p'], k))[:CANDIDATI_RUOLO]
        economici = sorted(tutti, key=lambda k: (prezzi[k], -E[k]['mu'] * E[k]['p'], k))[:ECONOMICI_RUOLO]
        pool[r] = sorted(set(forti) | set(economici) | {k for k in fissati if E[k]['ruolo'] == r})
    return pool


def _costruisci(ordine, E, prezzi, slot, vincoli, fissati, budget):
    """Riempie gli slot nell'ordine dato, senza mai rendere impossibile chiudere la rosa."""
    rosa = list(fissati)
    manca = {r: slot[r] - sum(1 for k in rosa if E[k]['ruolo'] == r) for r in regole.RUOLI}
    economici = {r: sorted(prezzi[k] for k in ordine if E[k]['ruolo'] == r and k not in rosa)
                 for r in regole.RUOLI}
    for k in ordine:
        r = E[k]['ruolo']
        if k in rosa or manca[r] <= 0:
            continue
        manca[r] -= 1
        riserva = sum(sum(economici[x][:manca[x]]) for x in regole.RUOLI)
        prova = rosa + [k]
        if sum(prezzi[x] for x in prova) + riserva <= budget and rispetta(prova, prezzi, E, vincoli):
            rosa = prova
        else:
            manca[r] += 1
    if any(v != 0 for v in manca.values()) or sum(prezzi[k] for k in rosa) > budget:
        return None             # anche i fissati da soli possono sforare il budget
    return rosa


def ottimizza(E, prezzi, R, budget, slot, vincoli, fissati=(), esclusi=(), seme=1, partenze=5,
              iniziali=()):
    """La rosa slot[r] per reparto con il valore rapido massimo, entro budget e vincoli.

    Ricerca locale da piu' partenze: scambi 1-per-1 nello stesso reparto e, quando
    non ce ne sono piu', coppie "rinforzo + risparmio" (il budget morde sempre:
    per migliorare un reparto bisogna liberare crediti in un altro)."""
    fissati, esclusi = list(dict.fromkeys(fissati)), set(esclusi)
    for r in regole.RUOLI:
        if sum(1 for k in fissati if E[k]['ruolo'] == r) > slot[r]:
            raise ValueError(f'reparto {r}: piu fissati che slot')
    pool = _pool(E, prezzi, slot, fissati, esclusi)
    for r in regole.RUOLI:
        if len(pool[r]) < slot[r]:
            raise ValueError(f'reparto {r}: servono {slot[r]} giocatori, disponibili {len(pool[r])}')
    cache = {}

    def val(rosa):
        return valore_rapido(rosa, E, R, cache)

    def costo(rosa):
        return sum(prezzi[k] for k in rosa)

    tutti = sorted(k for r in regole.RUOLI for k in pool[r])
    ordini = [sorted(tutti, key=lambda k: (prezzi[k], k)),
              sorted(tutti, key=lambda k: (-E[k]['mu'] * E[k]['p'], k))]
    rng = random.Random(seme)
    for _ in range(max(0, partenze - 2)):
        o = list(tutti)
        rng.shuffle(o)
        ordini.append(o)
    partenze_rose = []
    for ini in iniziali:        # partenze calde: una rosa gia' buona, riparata se serve
        ini = _ripara(ini, pool, E, prezzi, slot, vincoli, fissati, esclusi, budget)
        if ini is not None:
            partenze_rose.append(ini)
    if not partenze_rose:
        partenze_rose = [_costruisci(o, E, prezzi, slot, vincoli, fissati, budget) for o in ordini]
    migliore = None
    for rosa in partenze_rose:
        if rosa is None:
            continue
        rosa = sorted(_migliora(rosa, pool, E, prezzi, vincoli, budget, fissati, val, costo))
        if migliore is None or val(rosa) > val(migliore) + 1e-12:
            migliore = rosa
    if migliore is None:
        raise ValueError(f'budget {budget} insufficiente per riempire la rosa con questi vincoli')
    rosa = migliore
    return {'rosa': rosa, 'costo': costo(rosa), 'valore': val(rosa), 'valore_esatto': valore_rosa(rosa, E, R)}


def _migliora(rosa, pool, E, prezzi, vincoli, budget, fissati, val, costo):
    fissi = set(fissati)
    while True:
        cur, c0 = val(rosa), costo(rosa)
        fuori = [k for k in sorted(rosa) if k not in fissi]
        su, giu, fatto = [], [], False
        for out in fuori:
            r = E[out]['ruolo']
            for inn in pool[r]:
                if inn in rosa:
                    continue
                nuova = [x for x in rosa if x != out] + [inn]
                if not rispetta(nuova, prezzi, E, vincoli):
                    continue
                dv, dc = val(nuova) - cur, prezzi[inn] - prezzi[out]
                if c0 + dc <= budget and dv > 1e-12:
                    rosa, fatto = nuova, True
                    break
                if dv > 1e-12:
                    su.append((dv, dc, out, inn))
                elif dc < 0:
                    giu.append((dv / -dc, dv, dc, out, inn))
            if fatto:
                break
        if fatto:
            continue
        su = sorted(su, reverse=True)[:COPPIE_UP]
        giu = sorted(giu, reverse=True)[:COPPIE_DOWN]
        for _, dc1, o1, i1 in su:
            for _, _, dc2, o2, i2 in giu:
                if o2 == o1 or i2 == i1 or c0 + dc1 + dc2 > budget:
                    continue
                nuova = [x for x in rosa if x not in (o1, o2)] + [i1, i2]
                if rispetta(nuova, prezzi, E, vincoli) and val(nuova) > cur + 1e-12:
                    rosa, fatto = nuova, True
                    break
            if fatto:
                break
        if not fatto:
            return rosa


def _ripara(rosa, pool, E, prezzi, slot, vincoli, fissati, esclusi, budget):
    """Rende valida una rosa di partenza: via gli esclusi, dentro i fissati (al posto
    del peggiore del reparto), poi risparmi finche' budget e vincoli tornano."""
    fissi = set(fissati)
    rosa = [k for k in rosa if k not in esclusi and k in E]
    for f in fissati:
        if f in rosa:
            continue
        r = E[f]['ruolo']
        stesso = [k for k in rosa if E[k]['ruolo'] == r and k not in fissi]
        if len([k for k in rosa if E[k]['ruolo'] == r]) >= slot[r]:
            if not stesso:
                return None
            rosa.remove(min(stesso, key=lambda k: (E[k]['mu'] * E[k]['p'], k)))
        rosa.append(f)
    for r in regole.RUOLI:          # completa i reparti rimasti corti coi piu' economici
        while sum(1 for k in rosa if E[k]['ruolo'] == r) < slot[r]:
            liberi = [k for k in pool[r] if k not in rosa]
            if not liberi:
                return None
            rosa.append(min(liberi, key=lambda k: (prezzi[k], k)))
    for _ in range(len(rosa) * 3):
        if sum(prezzi[k] for k in rosa) <= budget and rispetta(rosa, prezzi, E, vincoli):
            return rosa
        mosse = []
        for out in rosa:
            if out in fissi:
                continue
            for inn in pool[E[out]['ruolo']]:
                if inn not in rosa and prezzi[inn] < prezzi[out]:
                    perso = E[out]['mu'] * E[out]['p'] - E[inn]['mu'] * E[inn]['p']
                    mosse.append((perso / (prezzi[out] - prezzi[inn]), out, inn))
        if not mosse:
            return None
        _, out, inn = min(mosse)
        rosa = [x for x in rosa if x != out] + [inn]
    return None


# ------------------------------------------------------------------ TETTO

def tetto(k, E, prezzi, R, budget, slot, vincoli, fissati=(), esclusi=(), base=None, partenze=2):
    """Il prezzo massimo che conviene pagare `k`: il piu' alto p (intero) per cui la
    miglior rosa CON k pagato p vale strettamente piu' della miglior rosa SENZA k.
    A parita' di valore non serve: tetto 1. `base` = una rosa buona da cui partire."""
    esclusi = set(esclusi)
    ini = [base] if base else []
    try:
        v0 = ottimizza(E, prezzi, R, budget, slot, vincoli, fissati, esclusi | {k},
                       partenze=partenze, iniziali=ini)['valore']
    except ValueError:
        v0 = float('-inf')

    def conviene(p):
        pr = dict(prezzi)
        pr[k] = float(p)
        try:
            v = ottimizza(E, pr, R, budget, slot, vincoli, list(fissati) + [k], esclusi,
                          partenze=partenze, iniziali=ini)['valore']
        except ValueError:
            return False
        return v > v0 + 1e-9

    lo, hi = 1, int(budget - (sum(slot.values()) - 1))
    if hi < 1 or not conviene(1):
        return 1.0
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if conviene(mid):
            lo = mid
        else:
            hi = mid - 1
    return float(lo)


# ------------------------------------------------------------------ PIANO

MARGINE_REPARTO = 1.10
FUORI_PIANO_MOSTRATI = 5


def _etichetta(tetto_, forchetta):
    if tetto_ is None:
        return 'fuori piano'
    if tetto_ > forchetta[2]:
        return 'affare'
    if tetto_ < forchetta[0]:
        return 'lascia'
    return 'da giocare'


def piano(E, forchette, R, budget, slot, vincoli, ordine=('P', 'D', 'C', 'A'), candidati=40,
          fissati=(), esclusi=(), partenze=5):
    """Il piano d'asta: la rosa migliore ai prezzi previsti, e reparto per reparto
    i bersagli e i candidati con forchetta, tetto, etichetta e due alternative."""
    esclusi = set(esclusi)
    prezzi = {k: f[1] for k, f in forchette.items() if k in E}
    best = ottimizza(E, prezzi, R, budget, slot, vincoli, fissati, esclusi, partenze=partenze)
    rosa = best['rosa']

    def alternative(k):
        """Se lo perdi, vai su di loro: i 2 fuori rosa del suo ruolo piu' vicini a lui per valore."""
        r, v = E[k]['ruolo'], E[k]['mu'] * E[k]['p']
        liberi = [x for x in prezzi if E[x]['ruolo'] == r and x not in rosa and x not in esclusi and x != k]
        return sorted(liberi, key=lambda x: (abs(E[x]['mu'] * E[x]['p'] - v), prezzi[x], x))[:2]

    def riga(k, con_tetto):
        tuo = k in fissati
        tt = tetto(k, E, prezzi, R, budget, slot, vincoli, fissati, esclusi, base=rosa, partenze=1) \
            if con_tetto and not tuo else None
        return {'k': k, 'nome': E[k]['nome'], 'forchetta': forchette[k], 'tetto': tt,
                'etichetta': 'tuo' if tuo else _etichetta(tt, forchette[k]), 'alternative': alternative(k),
                'fonte': E[k].get('fonte', '')}

    reparti = {}
    for r in ordine:
        nel = sorted((k for k in rosa if E[k]['ruolo'] == r), key=lambda k: -prezzi[k])
        fuori = sorted((k for k in prezzi if E[k]['ruolo'] == r and k not in rosa and k not in esclusi),
                       key=lambda k: (-E[k]['mu'] * E[k]['p'], k))
        n_cand = max(0, candidati - len(nel))
        bersagli = [riga(k, True) for k in nel]
        altri = [riga(k, True) for k in fuori[:n_cand]] + \
                [riga(k, False) for k in fuori[n_cand:n_cand + FUORI_PIANO_MOSTRATI]]
        reparti[r] = {'budget': MARGINE_REPARTO * sum(forchette[k][1] for k in nel),
                      'bersagli': bersagli, 'altri': altri}
    struttura = {'top (50+)': sum(1 for k in rosa if prezzi[k] >= 50),
                 'medi (6-49)': sum(1 for k in rosa if 6 <= prezzi[k] < 50),
                 'da 1-5': sum(1 for k in rosa if prezzi[k] < 6)}
    return {'rosa': rosa, 'costo': best['costo'], 'valore': best['valore'],
            'valore_esatto': best['valore_esatto'], 'reparti': reparti, 'struttura': struttura}


# ------------------------------------------------------------------ LIVE

def _chiave(nome, E):
    """Il nome come scritto nello stato dell'asta -> chiave delle stime, o None."""
    if nome in E:
        return nome
    k = nomi.giocatore(nome)
    if k in E:
        return k
    return next((x for x, g in E.items() if nomi.giocatore(g['nome']) == k), None)


def termometro(venduti, forchette, E):
    """Quanto la lega sta pagando rispetto al previsto: somma pagata / somma delle
    mediane previste dei venduti, tagliata fra 0,5 e 2. 1 senza vendite."""
    pagato = previsto = 0.0
    for v in venduti:
        k = _chiave(v['nome'], E)
        if k is not None and k in forchette:
            pagato += float(v['prezzo'])
            previsto += forchette[k][1]
    if not previsto:
        return 1.0
    return min(2.0, max(0.5, pagato / previsto))


def fattore_residuo(stato, forchette, E, R, slot=None):
    """Somma zero, come fanta.mercato(): i crediti ancora in circolo nella lega divisi
    per la spesa prevista sugli slot che restano (le mediane piu' alte fra i rimasti).
    Se gli avversari strapagano bruciano crediti, e il resto costera' MENO; se
    comprano a sconto, di piu'. Fra 0,5 e 2."""
    slot = slot or R['slot']
    venduti = stato.get('venduti', [])
    fuori = {_chiave(v['nome'], E) for v in venduti}
    crediti = R['squadre'] * R['budget'] - sum(float(v['prezzo']) for v in venduti)
    slot_res = R['squadre'] * sum(slot.values()) - len(venduti)
    resto = sorted((f[1] for k, f in forchette.items() if k not in fuori), reverse=True)[:max(slot_res, 0)]
    if not resto or not sum(resto):
        return 1.0
    return min(2.0, max(0.5, crediti / sum(resto)))


def ricalcola(stato, E, forchette, R, vincoli, slot=None, **kw):
    """Il piano rifatto a meta' asta: i miei restano (al prezzo pagato), i venduti ad
    altri spariscono, i prezzi dei rimasti si scalano a somma zero (fattore_residuo).
    Il termometro si riporta come lettura, non entra nei prezzi."""
    slot = slot or R['slot']
    miei, altri, speso = [], set(), 0.0
    for v in stato.get('venduti', []):
        k = _chiave(v['nome'], E)
        if k is None:
            continue
        if v.get('mio'):
            miei.append(k)
            speso += float(v['prezzo'])
        else:
            altri.add(k)
    temp = termometro([v for v in stato.get('venduti', []) if not v.get('mio')], forchette, E)
    fatt = fattore_residuo(stato, forchette, E, R, slot)
    f2 = {k: tuple(x * fatt for x in f) for k, f in forchette.items() if k not in altri}
    for v in stato.get('venduti', []):
        k = _chiave(v['nome'], E)
        if k in miei:
            f2[k] = (float(v['prezzo']),) * 3
    budget = float(stato.get('mio_budget', R['budget'])) + speso
    P = piano(E, f2, R, budget, slot, vincoli, fissati=miei, esclusi=altri, **kw)
    P['termometro'], P['fattore'] = temp, fatt
    return P


# ------------------------------------------------------------------ RIGIOCO

def rigioca(acquisti, E_agosto, forchette, R, vincoli, ordine=('P', 'D', 'C', 'A'), slot=None, partenze=2):
    """L'asta del 05/09 rigiocata col piano, usando SOLO dati di agosto.

    Reparto per reparto nell'ordine di chiamata, il bersaglio piu' caro del piano:
    se nessuno lo ha comprato si prende a 1; se il tetto >= pagato + 1 si prende a
    pagato + 1; altrimenti e' perso e il piano si rifa' senza di lui. Ottimista per
    costruzione: gli altri avrebbero reagito ai rilanci, e qui non reagiscono."""
    slot = slot or R['slot']
    E = E_agosto
    pagato = {a['k']: a['pagato'] for a in acquisti}
    prezzi_base = {k: f[1] for k, f in forchette.items() if k in E}
    miei, persi, log = {}, set(), []
    for r in ordine:
        while True:
            prezzi = dict(prezzi_base, **miei)
            try:
                best = ottimizza(E, prezzi, R, R['budget'], slot, vincoli, list(miei), persi,
                                 partenze=partenze)
            except ValueError as e:
                log.append(f'stop: {e}')
                break
            bersagli = sorted((k for k in best['rosa'] if E[k]['ruolo'] == r and k not in miei),
                              key=lambda k: (-prezzi[k], k))
            if not bersagli:
                break
            k = bersagli[0]
            pg = pagato.get(k)
            if pg is None:
                miei[k] = 1.0
                log.append(f'libero {E[k]["nome"]} 1')
                continue
            tt = tetto(k, E, prezzi, R, R['budget'], slot, vincoli, list(miei), persi,
                       base=best['rosa'], partenze=1)
            if tt >= pg + 1:
                miei[k] = pg + 1.0
                log.append(f'preso {E[k]["nome"]} {pg + 1:.0f}')
            else:
                persi.add(k)
                log.append(f'perso {E[k]["nome"]} (pagato {pg:.0f}, tetto {tt:.0f})')
    return {'rosa': sorted(miei), 'speso': sum(miei.values()), 'prezzi': miei, 'log': log}


# ------------------------------------------------------------------ CLI

def prepara(listone_path, prezzi_path, R):
    """Dai file alle stime: (E, forchette, acquisti). Solleva fanta.DatoMancante."""
    import fanta
    import mercato_asta
    acquisti = mercato_asta.carica(prezzi_path, listone_path)
    M = mercato_asta.stima(acquisti)
    E = valori(fanta.carica(listone_path)['giocatori'], R)
    forchette = {a['k']: mercato_asta.prevedi(M, a['ruolo'], a['fvm']) for a in acquisti if a['k'] in E}
    return E, forchette, acquisti


def vincoli_da(R):
    """La sezione 'asta' di lega.json -> vincoli dell'ottimizzatore."""
    a = R.get('asta') or {}
    v = {k: a[k] for k in ('portieri_max', 'fascia_media_max') if k in a}
    if 'fascia_media' in a:
        v['fascia_media'] = tuple(a['fascia_media'])
    return v


def _f(x):
    return f'{x:.0f}'


def stampa_piano(P, E, R):
    slot = R['slot']
    print(f'  rosa del piano: {len(P["rosa"])} giocatori, {P["costo"]:.0f} crediti ai prezzi previsti, '
          f'{P["valore_esatto"]:.1f} fantapunti attesi a giornata')
    print('  struttura: ' + ', '.join(f'{n} {k}' for k, n in P['struttura'].items()))
    print('  etichette: affare = tetto sopra la forchetta; da giocare = tetto dentro;\n'
          '             lascia = tetto sotto (la lega lo paghera\' piu\' di quanto ti serve)')
    for r, rep in P['reparti'].items():
        print(f'\n  === REPARTO {r} ({slot[r]} slot) - budget del reparto: {rep["budget"]:.0f} crediti ===')
        print(f'    {"":<2}{"giocatore":<22}{"sq":<5}{"forchetta":>13}{"tetto":>7}  {"":<12}alternative')
        for tipo, righe in (('>>', rep['bersagli']), ('  ', rep['altri'])):
            for g in righe:
                q = g['forchetta']
                tt = _f(g['tetto']) if g['tetto'] is not None else '-'
                alt = ', '.join(E[a]['nome'] for a in g['alternative'])
                print(f'    {tipo}{g["nome"][:21]:<22}{E[g["k"]]["squadra"][:4]:<5}'
                      f'{_f(q[0]):>5}-{_f(q[1]):>3}-{_f(q[2]):>3}{tt:>7}  {g["etichetta"]:<12}{alt}')
    print('\n  >> = nel piano. Il tetto e\' il prezzo oltre il quale la rosa migliore la fai senza di lui.')


def stampa_rigioco(res, acquisti, E, R):
    print('  L\'asta del 05/09 rigiocata col piano, solo con dati di agosto. OTTIMISTA per costruzione:')
    print('  quando rilanci a pagato+1 gli altri non reagiscono.\n')
    for riga in res['log']:
        print('    ' + riga)
    rose = {}
    for a in acquisti:
        if a['pagato'] is not None:
            fs = a['fantasquadra'] or '?'
            rose.setdefault(fs, []).append(a)
    mia = str(R.get('mia', '')).lower()
    print('\n  === CONFRONTO (fantapunti attesi a giornata col modello di agosto) ===')
    righe = [('PIANO (rigioco)', valore_rosa(res['rosa'], E, R), res['speso'], len(res['rosa']))]
    for fs, lista in rose.items():
        chiavi = [a['k'] for a in lista]
        nome = fs + ('  <- tu, vera' if fs.lower() == mia else '')
        righe.append((nome, valore_rosa(chiavi, E, R), sum(a['pagato'] for a in lista), len(lista)))
    print(f'    {"":<3}{"rosa":<30}{"valore":>8}{"speso":>8}{"gioc.":>7}')
    for i, (nome, v, s, n) in enumerate(sorted(righe, key=lambda x: -x[1]), 1):
        print(f'    {i:<3}{nome[:29]:<30}{v:>8.1f}{s:>8.0f}{n:>7}')


def esegui(R, listone_path, prezzi_path, modo='piano', candidati=12, live=None, partenze=3):
    """Il comando: stampa piano, piano live o rigioco. Ritorna il codice di uscita."""
    import json
    import os

    import fanta
    for nome, f in (('listone', listone_path), ('prezzi d asta', prezzi_path)):
        if not f or not os.path.exists(f):
            print(f'[!] {nome} non trovato: {f} (in lega.json -> file.listone / file.prezzi)')
            return 1
    try:
        E, forchette, acquisti = prepara(listone_path, prezzi_path, R)
    except fanta.DatoMancante as e:
        print(f'[!] {e}')
        return 1
    vincoli = vincoli_da(R)
    ordine = tuple((R.get('asta') or {}).get('ordine', 'PDCA'))
    try:
        if modo == 'rigioca':
            stampa_rigioco(rigioca(acquisti, E, forchette, R, vincoli, ordine), acquisti, E, R)
        elif live:
            if not os.path.exists(live):
                print(f'[!] stato dell asta non trovato: {live}')
                return 1
            with open(live, encoding='utf-8') as fh:
                stato = json.load(fh)
            P = ricalcola(stato, E, forchette, R, vincoli, ordine=ordine, candidati=candidati,
                          partenze=partenze)
            print(f'  termometro: la lega paga {P["termometro"]:.2f}x il previsto; '
                  f'prezzi dei rimasti x{P["fattore"]:.2f} (somma zero)\n')
            stampa_piano(P, E, R)
        else:
            stampa_piano(piano(E, forchette, R, R['budget'], R['slot'], vincoli, ordine,
                               candidati=candidati, partenze=partenze), E, R)
    except ValueError as e:
        print(f'[!] piano impossibile: {e}')
        return 1
    return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--lega', default='lega.json')
    ap.add_argument('--listone', default=None)
    ap.add_argument('--prezzi', default=None)
    ap.add_argument('--candidati', type=int, default=12, help='giocatori con tetto per reparto')
    ap.add_argument('--live', default=None, help='stato dell asta in corso (json)')
    ap.add_argument('--rigioca', action='store_true', help='rigioca l asta coi prezzi veri')
    A = ap.parse_args(argv)
    R = regole.carica_lega(A.lega)
    fl = R.get('file', {})
    return esegui(R, A.listone or fl.get('listone'), A.prezzi or fl.get('prezzi'),
                  'rigioca' if A.rigioca else 'piano', A.candidati, A.live)


if __name__ == '__main__':
    raise SystemExit(main())
