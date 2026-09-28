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
