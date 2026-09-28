# -*- coding: utf-8 -*-
"""mercato_asta - quanto paga DAVVERO la tua lega, giocatore per giocatore.

Il FVM di Fantacalcio.it e' il prezzo "giusto" nazionale. La tua lega non lo
rispetta: all'asta del 05/09/2026 (porcodidiosanto) i portieri si sono pagati
+46% sopra la proporzione del FVM, i difensori +25%, i centrocampisti -34%,
gli attaccanti -39% (mediane). Ipotesi: e' l'ordine di chiamata P -> D -> C -> A,
si strapaga con i crediti in tasca e si compra a sconto quando sono finiti.

Questo modulo stima, per ogni giocatore del listone:
- la forchetta 25-50-75% del prezzo che la lega paghera';
- la probabilita' che qualcuno lo compri;
- le "manie" della lega: dove strapaga e dove regala.

## Come

Per ogni cella (ruolo x fascia di FVM: <20, 20-49, 50-99, >=100) si provano due
modelli - lineare `pagato = k*FVM` e logaritmico `log pagato = a + b*log FVM` -
e si tiene quello con l'errore leave-one-out minore: il prezzo di ogni
giocatore si prevede SENZA usare il suo acquisto. Se nessuno dei due batte la
baseline (lineare su tutta la lega), si usa la baseline. Una cella con meno di
5 acquisti usa la baseline.

L'esplorazione del 28/09 ha mostrato perche' serve: il logaritmico vince sotto
FVM 50, perde di 30 crediti sopra FVM 100. Un modello solo avrebbe sbagliato
in una delle due zone.

Spec: docs/superpowers/specs/2026-09-28-piano-asta-design.md (par. 3)

Uso:
    python mercato_asta.py --prezzi prezzi_lega_2026-27.csv --listone listone_completo.csv
"""
import math
import statistics

import fanta
import nomi
import voti

FASCE = (0, 20, 50, 100)
MIN_CELLA = 5
ESCLUSI = []          # nomi scartati per FVM mancante o nullo, dall'ultima carica()


def _tabella(path, obbligatorie):
    righe = voti._righe(path)
    norm = [fanta._norm(c) for c in righe[0]]
    col = {}
    for campo, cand in obbligatorie.items():
        col[campo] = next((norm.index(c) for c in cand if c in norm), None)
    return righe[1:], col


def _get(r, i):
    return r[i].strip() if i is not None and i < len(r) else ''


def carica(prezzi_path, listone_path=None):
    """Prezzi pagati + listone -> una riga per giocatore; pagato None = non comprato."""
    del ESCLUSI[:]
    righe, c = _tabella(prezzi_path, {
        'fs': ['fantasquadra', 'squadrafanta', 'fanta'], 'nome': ['nome', 'giocatore'],
        'ruolo': ['ruolo', 'r'], 'pagato': ['pagato', 'prezzo', 'costo'], 'fvm': ['fvm']})
    if c['nome'] is None or c['pagato'] is None:
        raise fanta.DatoMancante(f'{prezzi_path}: servono le colonne Nome e Pagato')
    comprati = {}
    for r in righe:
        nome = _get(r, c['nome'])
        if not nome:
            continue
        comprati[nomi.giocatore(nome)] = {
            'nome': nome, 'ruolo': _get(r, c['ruolo']).upper(), 'pagato': fanta._num(_get(r, c['pagato'])),
            'fvm': fanta._num(_get(r, c['fvm'])), 'fantasquadra': _get(r, c['fs']) or None}

    out = []
    if listone_path:
        righe, c = _tabella(listone_path, {
            'nome': ['nome', 'giocatore'], 'ruolo': ['ruolo', 'r'], 'squadra': ['squadra', 'sq'],
            'quota': ['quotazione', 'qt', 'qta', 'quota'], 'fvm': ['fvm']})
        visti = set()
        for r in righe:
            nome = _get(r, c['nome'])
            if not nome:
                continue
            k = nomi.giocatore(nome)
            visti.add(k)
            comp = comprati.get(k, {})
            out.append({'k': k, 'nome': nome, 'ruolo': _get(r, c['ruolo']).upper(),
                        'squadra': _get(r, c['squadra']), 'fvm': fanta._num(_get(r, c['fvm'])),
                        'quota': fanta._num(_get(r, c['quota'])), 'pagato': comp.get('pagato'),
                        'fantasquadra': comp.get('fantasquadra')})
        mancano = [v['nome'] for k, v in comprati.items() if k not in visti]
        if mancano:
            raise fanta.DatoMancante(
                f'{len(mancano)} giocatori comprati non sono nel listone: {", ".join(mancano[:10])}')
    else:
        out = [{'k': k, 'nome': v['nome'], 'ruolo': v['ruolo'], 'squadra': '', 'fvm': v['fvm'],
                'quota': None, 'pagato': v['pagato'], 'fantasquadra': v['fantasquadra']}
               for k, v in comprati.items()]

    validi = []
    for a in out:
        if not a['fvm'] or a['fvm'] <= 0:
            ESCLUSI.append(a['nome'])
        else:
            validi.append(a)
    return validi


# ------------------------------------------------------------------ MODELLO

def fascia(fvm):
    """Indice della fascia di FVM: 0 (<20), 1 (20-49), 2 (50-99), 3 (>=100)."""
    return max(i for i, soglia in enumerate(FASCE) if fvm >= soglia)


def _fit(tipo, punti):
    """Parametri del modello sui punti [(fvm, pagato)], o None se non stimabile."""
    if not punti:
        return None
    if tipo in ('lineare', 'baseline'):
        s = sum(f for f, _ in punti)
        return (sum(p for _, p in punti) / s,) if s else None
    xs = [math.log(f) for f, _ in punti]
    ys = [math.log(max(p, 1.0)) for _, p in punti]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    return (my - b * mx, b)


def _prev(tipo, param, fvm):
    if tipo == 'log':
        a, b = param
        return math.exp(a + b * math.log(fvm))
    return param[0] * fvm


def _loo(tipo, punti, tutti=None):
    """Previsioni leave-one-out: per ogni punto, il modello stimato SENZA di lui.
    Per la baseline il modello si stima su `tutti` (la lega intera) meno lui."""
    out = []
    for i, (f, _) in enumerate(punti):
        if tipo == 'baseline':
            altri = [q for q in tutti if q is not punti[i]]
        else:
            altri = punti[:i] + punti[i + 1:]
        param = _fit(tipo, altri)
        out.append(_prev(tipo, param, f) if param else None)
    return out


def _mae(punti, prev):
    err = [abs(p - q) for (_, p), q in zip(punti, prev) if q is not None]
    return sum(err) / len(err) if err else float('inf')


def stima(acquisti):
    """Modello per cella (ruolo, fascia) scelto dall'errore leave-one-out."""
    comprati = [a for a in acquisti if a['pagato'] is not None]
    tutti = [(a['fvm'], a['pagato']) for a in comprati]
    base = _fit('baseline', tutti)
    base_k = base[0] if base else 1.0
    prev_base_tutti = _loo('baseline', tutti, tutti)
    M = {'_base': base_k,
         '_rapporti_base': [p / q for (_, p), q in zip(tutti, prev_base_tutti) if q]}
    celle = {}
    for a, pt in zip(comprati, tutti):
        celle.setdefault((a['ruolo'], fascia(a['fvm'])), []).append(pt)
    for cella, punti in celle.items():
        prev_b = _loo('baseline', punti, tutti)
        scelta = {'tipo': 'baseline', 'param': (base_k,), 'prev': prev_b,
                  'mae': _mae(punti, prev_b), 'mae_base': _mae(punti, prev_b), 'n': len(punti)}
        if len(punti) >= MIN_CELLA:
            for tipo in ('lineare', 'log'):
                prev = _loo(tipo, punti)
                mae = _mae(punti, prev)
                if mae < scelta['mae']:
                    scelta.update(tipo=tipo, param=_fit(tipo, punti), prev=prev, mae=mae)
        scelta['rapporti'] = [p / q for (_, p), q in zip(punti, scelta.pop('prev')) if q]
        M[cella] = scelta
    return M


def _quartili(v):
    v = sorted(v)
    if not v:
        return 1.0, 1.0, 1.0
    if len(v) < 4:
        m = statistics.median(v)
        return min(v), m, max(v)
    q = statistics.quantiles(v, n=4)
    return q[0], q[1], q[2]


def prevedi(M, ruolo, fvm):
    """(q25, q50, q75) del prezzo che la lega paghera', mai sotto 1 credito."""
    cella = M.get((ruolo, fascia(fvm)))
    if cella is None:
        previsto, rapporti = M['_base'] * fvm, M['_rapporti_base']
    else:
        previsto = _prev(cella['tipo'], cella['param'], fvm)
        rapporti = cella['rapporti'] or M['_rapporti_base']
    return tuple(max(1.0, previsto * r) for r in _quartili(rapporti))


def previsto_loo(acquisti, k):
    """Prezzo mediano previsto per `k` con un modello stimato SENZA di lui."""
    a = next(x for x in acquisti if x['k'] == k)
    return prevedi(stima([x for x in acquisti if x['k'] != k]), a['ruolo'], a['fvm'])[1]


# ------------------------------------------------------------------ ACQUISTO E MANIE

MIN_SQUADRA = 5


def p_acquisto(acquisti, ruolo, fvm):
    """Frequenza dei comprati nella cella (ruolo, fascia), con Laplace (c+1)/(n+2).
    Serve il listone: sui soli comprati varrebbe sempre ~1."""
    f = fascia(fvm)
    cella = [a for a in acquisti if a['ruolo'] == ruolo and fascia(a['fvm']) == f]
    c = sum(1 for a in cella if a['pagato'] is not None)
    return (c + 1.0) / (len(cella) + 2.0)


def manie(acquisti, M):
    """Dove la lega strapaga e dove regala, rispetto alla baseline k*FVM.
    scarto = mediana di pagato/(k*FVM) - 1 per ruolo, squadra (>= 5 acquisti) e fascia."""
    k = M['_base']
    gruppi = {}
    for a in acquisti:
        if a['pagato'] is None:
            continue
        r = a['pagato'] / (k * a['fvm']) - 1.0
        gruppi.setdefault(('ruolo', a['ruolo']), []).append(r)
        if a['squadra']:
            gruppi.setdefault(('squadra', a['squadra']), []).append(r)
        gruppi.setdefault(('fascia', f'{FASCE[fascia(a["fvm"])]}+'), []).append(r)
    out = []
    for (dim, val), v in gruppi.items():
        if dim == 'squadra' and len(v) < MIN_SQUADRA:
            continue
        out.append({'dimensione': dim, 'valore': val, 'n': len(v), 'scarto': statistics.median(v)})
    return sorted(out, key=lambda m: (m['dimensione'], -m['scarto']))
