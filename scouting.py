# -*- coding: utf-8 -*-
"""scouting - schede qualitative con prova, fonte e data, e cosa ne fa il socio.

I numeri da soli non trovano i gioielli: la previsione dei breakout coi dati ha
lift 0,25x (`talenti.py`). Lo scouting aggiunge quello che i numeri non vedono -
chi gioca, dove, per chi, con quali compiti - con un patto: **ogni giudizio ha
una prova e una fonte**, sposta le stime di poco, e viene misurato contro quello
che succede dopo (`verifica.verifica_kpi`).

Una scheda e' un file JSON in `scouting/`:

    {"nome": "Varela G.", "squadra": "Monza", "ruolo": "A",
     "data": "2026-09-28", "giornata": 5, "autore": "claude",
     "kpi": {"spazio": {"voto": 2, "prova": "titolare nelle prime 5",
                        "fonte": "https://..."}},
     "note": "testo libero, non entra nei calcoli"}

Spec: docs/superpowers/specs/2026-09-28-scouting-qualitativo-design.md
"""
import datetime
import json
import os

import nomi

# peso iniziale (stima dichiarata: la verifica lo ricalibra), domanda
KPI = {
    'spazio': (1.0, 'giochera? (riserva chiusa .. titolare inamovibile)'),
    'ruolo_tattico': (0.8, 'quanto gioca vicino alla porta? (compiti difensivi .. libero di attaccare)'),
    'palle_inattive': (0.6, 'rigori, punizioni, corner (nessuna .. rigorista designato)'),
    'contesto': (0.6, 'la squadra gli fa fare bonus? (chiusa e sterile .. offensiva / gli da minuti)'),
    'allenatore': (0.5, 'fiducia del tecnico (fuori dai piani .. voluto da lui)'),
    'fisico': (0.5, 'infortuni, condizione (cronico / rotto .. integro e in forma)'),
    'traiettoria': (0.4, 'in crescita? (in calo .. eta e stagione in rampa)'),
    'carattere': (0.3, 'affidabilita e fame, SOLO su fatti (indisciplina documentata .. leader)'),
}
SCADENZA_GIORNI = 60
CAMPI = {'nome', 'squadra', 'ruolo', 'data', 'giornata', 'autore', 'kpi', 'note'}


def _data(s):
    try:
        return datetime.date.fromisoformat(str(s))
    except ValueError:
        return None


def _errori(scheda):
    """(errori che scartano la scheda, {kpi: errore} che scartano solo il KPI)."""
    if not isinstance(scheda, dict):
        return ['non e un oggetto JSON'], {}
    gravi, kpi_err = [], {}
    if not str(scheda.get('nome') or '').strip():
        gravi.append('manca il nome')
    if _data(scheda.get('data')) is None:
        gravi.append(f'data non ISO (AAAA-MM-GG): {scheda.get("data")!r}')
    g = scheda.get('giornata')
    if g is not None and (isinstance(g, bool) or not isinstance(g, int)):
        gravi.append(f'giornata non intera: {g!r}')
    ignoti = sorted(set(scheda) - CAMPI)
    if ignoti:
        gravi.append('campi sconosciuti: ' + ', '.join(ignoti))
    kpi = scheda.get('kpi') or {}
    if not isinstance(kpi, dict):
        return gravi + ['kpi non e un oggetto'], {}
    sconosciuti = sorted(set(kpi) - set(KPI))
    if sconosciuti:
        gravi.append('KPI sconosciuti: ' + ', '.join(sconosciuti))
    for k in set(kpi) & set(KPI):
        v = kpi[k] if isinstance(kpi[k], dict) else {}
        voto = v.get('voto')
        if isinstance(voto, bool) or not isinstance(voto, int) or not -2 <= voto <= 2:
            kpi_err[k] = f'{k}: voto {voto!r} non intero fra -2 e +2'
        elif not str(v.get('prova') or '').strip():
            kpi_err[k] = f'{k}: senza prova'
        elif not str(v.get('fonte') or '').strip():
            kpi_err[k] = f'{k}: senza fonte'
    return gravi, kpi_err


def valida(scheda):
    """Tutti gli errori della scheda, leggibili; lista vuota = valida."""
    gravi, kpi_err = _errori(scheda)
    return gravi + sorted(kpi_err.values())


def _kpi_validi(scheda):
    _, kpi_err = _errori(scheda)
    return {k: v for k, v in (scheda.get('kpi') or {}).items() if k in KPI and k not in kpi_err}


def indice(scheda, escludi=()):
    """(indice in [-1, 1], confidenza in [0, 1]) sui KPI validi.

    indice = somma peso*voto / (2 * somma di TUTTI i pesi): un KPI mancante vale 0.
    confidenza = somma dei pesi documentati / somma di tutti i pesi.
    `escludi` toglie dei KPI da numeratore e denominatore."""
    pesi = {k: p for k, (p, _) in KPI.items() if k not in escludi}
    tot = sum(pesi.values())
    validi = {k: v for k, v in _kpi_validi(scheda).items() if k in pesi}
    if not tot:
        return 0.0, 0.0
    idx = sum(pesi[k] * v['voto'] for k, v in validi.items()) / (2 * tot)
    conf = sum(pesi[k] for k in validi) / tot
    return idx, conf


def carica(cartella):
    """Le schede in `cartella` (*.json) -> ({chiave giocatore: scheda}, errori).

    Una scheda non valida e' scartata intera; un KPI non valido e' tolto e detto;
    due schede per lo stesso giocatore: vale la piu' recente, e lo si dice."""
    schede, errori, da_file = {}, [], {}
    if not cartella or not os.path.isdir(cartella):
        return {}, []
    for f in sorted(os.listdir(cartella)):
        if not f.lower().endswith('.json'):
            continue
        try:
            with open(os.path.join(cartella, f), encoding='utf-8') as fh:
                s = json.load(fh)
        except (OSError, ValueError) as e:
            errori.append(f'{f}: JSON non leggibile ({e.__class__.__name__}), scartata')
            continue
        gravi, kpi_err = _errori(s)
        if gravi:
            errori.append(f'{f}: scartata - ' + '; '.join(gravi))
            continue
        if kpi_err:
            errori.append(f'{f}: KPI tolti - ' + '; '.join(sorted(kpi_err.values())))
            s = dict(s, kpi={k: v for k, v in s['kpi'].items() if k not in kpi_err})
        k = nomi.giocatore(s['nome'])
        if k in schede:
            vecchia, nuova = (schede[k], s) if _data(schede[k]['data']) <= _data(s['data']) else (s, schede[k])
            f_nuova = f if nuova is s else da_file[k]
            errori.append(f'{s["nome"]}: due schede, vale la piu recente ({nuova["data"]}, {f_nuova}), '
                          f'ignorata quella del {vecchia["data"]}')
            s, f = nuova, f_nuova
        schede[k], da_file[k] = s, f
    return schede, errori
