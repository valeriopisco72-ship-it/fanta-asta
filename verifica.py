# -*- coding: utf-8 -*-
"""verifica - il socio ci azzecca? Backtest sulle giornate gia' giocate.

Per ogni giornata G si rifanno le stime usando SOLO i voti delle giornate prima
di G (e i risultati del calendario prima di G), poi si confrontano con i
fantavoti veri di G. Nessuna informazione dal futuro: e' l'unico modo onesto di
sapere se le proiezioni valgono qualcosa o se sono rumore ben impaginato.

Due confronti, contro due baseline ingenue:

1. **Errore sul singolo giocatore** (MAE fra fantavoto previsto e vero, solo
   per chi ha giocato):
   - socio: proiezioni.py con shrinkage e calendario
   - "fantamedia finora": la media dei fantavoti di quest'anno, senza prior
   - "listone": la fantamedia dell'anno scorso
2. **Punti veri della formazione** della tua rosa, giornata per giornata:
   - socio: la formazione che avrebbe consigliato (valore atteso, senza MC)
   - ingenua: i migliori per fantamedia finora, modulo 3-4-3, panchina per
     fantamedia. E' quello che fa chi schiera "a sensazione ma coi numeri".

Le probabili formazioni NON entrano nel backtest (quelle vecchie non le
abbiamo): il socio viene misurato con un braccio legato, e va detto.

Uso:  python socio.py verifica    (oppure  python verifica.py --lega lega.json)
"""
import argparse
import math

import calendario
import proiezioni
import regole
import schiera
import voti


def punti_reali(form, reali, R):
    """Fantapunti veri di una formazione, panchina e modificatore compresi."""
    def ha_voto(k):
        return k in reali and reali[k]['voto'] is not None
    finali, usati, cambi = [], set(), 0
    for g in form['titolari']:
        if ha_voto(g['k']):
            finali.append(g)
        elif cambi < R['max_sostituzioni']:
            sub = next((b for b in form['panchina'] if b['ruolo'] == g['ruolo']
                        and b['k'] not in usati and ha_voto(b['k'])), None)
            if sub:
                usati.add(sub['k'])
                cambi += 1
                finali.append(sub)
    tot = sum(reali[g['k']]['fv'] for g in finali)
    return tot + schiera.bonus_squadra(finali, {g['k']: reali[g['k']]['voto'] for g in finali}, R)


def _ingenua(rosa, S, R):
    """3-4-3 coi migliori per fantamedia finora (chi non ha giocato va in fondo)."""
    def fm(g):
        s = S['giocatori'].get(g['k']) if S else None
        return sum(s['fv']) / s['presenze'] if s and s['presenze'] else -1.0
    finta = [dict(g, mu=fm(g), p=1.0) for g in rosa]
    f = schiera.formazione(finta, '3-4-3', R, 'mu')
    ok = {g['k']: g for g in rosa}
    return {'modulo': f['modulo'], 'titolari': [ok[g['k']] for g in f['titolari']],
            'panchina': [ok[g['k']] for g in f['panchina']]}


def stime_prima(records, listone, partite, R, G):
    """Le stime per la giornata G usando SOLO voti e risultati di prima di G."""
    S = voti.stagione([r for r in records if r['giornata'] < G])
    E = proiezioni.stima(S=S, listone=listone, R=R, prossima=True)
    if partite:
        P_ = [dict(p, giocata=p['giocata'] and p['giornata'] < G) for p in partite]
        E = proiezioni.per_giornata(E, P_, calendario.forze(P_), G, R)
    return S, E


def backtest(records, listone, partite, R, mia=None, prima=3):
    """Metriche per giornata. `prima` = da che giornata iniziare (servono dati prima)."""
    giornate = sorted({r['giornata'] for r in records})
    righe = []
    for G in giornate:
        if G < prima:
            continue
        if not any(r['giornata'] < G for r in records):
            continue
        S, E = stime_prima(records, listone, partite, R, G)
        reali = {}
        for r in records:
            if r['giornata'] == G:
                reali[voti.nomi.giocatore(r['nome'])] = r
        err = {'socio': [], 'finora': [], 'listone': []}
        L = {voti.nomi.giocatore(x['nome']): x for x in (listone or [])}
        for k, r in reali.items():
            if r['fv'] is None or k not in E:
                continue
            err['socio'].append(abs(E[k]['mu'] - r['fv']))
            s = S['giocatori'].get(k)
            rif = E['_ruoli'][E[k]['ruolo']]['mu']
            err['finora'].append(abs((sum(s['fv']) / s['presenze'] if s and s['presenze'] else rif) - r['fv']))
            fm = L.get(k, {}).get('fm')
            err['listone'].append(abs((fm if fm is not None else rif) - r['fv']))
        riga = {'giornata': G, 'n': len(err['socio']),
                **{f'mae_{k}': (sum(v) / len(v) if v else math.nan) for k, v in err.items()}}
        if mia:
            rosa = [E[k] for k in mia if k in E]
            f_socio = schiera.migliore_semplice(rosa, R)
            riga['punti_socio'] = punti_reali(f_socio, reali, R)
            riga['punti_ingenua'] = punti_reali(_ingenua(rosa, S, R), reali, R)
        righe.append(riga)
    return righe


def stampa(righe, R):
    if not righe:
        print('\n  servono almeno 3 giornate di voti per un backtest.')
        return
    print('\n=== VERIFICA: le stime contro le giornate vere (solo dati del passato) ===')
    con_rosa = 'punti_socio' in righe[0]
    print(f'  {"G":>3}{"gioc.":>7}{"MAE socio":>11}{"finora":>9}{"listone":>9}'
          + (f'{"formaz. socio":>15}{"ingenua":>9}' if con_rosa else ''))
    for r in righe:
        print(f'  {r["giornata"]:>3}{r["n"]:>7}{r["mae_socio"]:>11.2f}{r["mae_finora"]:>9.2f}'
              f'{r["mae_listone"]:>9.2f}'
              + (f'{r["punti_socio"]:>15.1f}{r["punti_ingenua"]:>9.1f}' if con_rosa else ''))
    m = {k: sum(r[k] for r in righe) / len(righe) for k in ('mae_socio', 'mae_finora', 'mae_listone')}
    print(f'  {"media":>10}{m["mae_socio"]:>11.2f}{m["mae_finora"]:>9.2f}{m["mae_listone"]:>9.2f}')
    if con_rosa:
        ds = sum(r['punti_socio'] - r['punti_ingenua'] for r in righe)
        print(f'\n  formazione del socio contro quella ingenua: {ds:+.1f} fantapunti in {len(righe)} giornate')
        if R['formula'] == 'scontri':
            dg = sum(regole.gol(r['punti_socio'], R) - regole.gol(r['punti_ingenua'], R) for r in righe)
            print(f'  in gol (fasce della lega): {dg:+d}')
    altro = min(('mae_finora', 'mae_listone'), key=m.get)
    scarto = m['mae_socio'] - m[altro]
    if scarto > 0.02:
        print(f'\n  Il socio NON batte "{altro[4:]}" su questi dati ({scarto:+.2f} di errore medio): '
              'fidati meno delle sue stime.')
    elif scarto > -0.02:
        print(f'\n  Il socio pareggia con "{altro[4:]}" ({scarto:+.2f}): il suo vantaggio, se c e, '
              'non e nelle stime singole.')
    else:
        print(f'\n  Il socio sbaglia meno di entrambe le baseline ({scarto:+.2f} sulla migliore).')
    print(f'  {len(righe)} giornate sono {"poco" if len(righe) < 10 else "un discreto"} campione.')


# ------------------------------------------------------------------ SCOUTING

def verifica_kpi(schede, records, stime_numeriche):
    """Lo scouting ci azzecca? Una riga per KPI.

    Per ogni giocatore schedato: la media di (fantavoto vero - stima numerica)
    SOLO nelle giornate dopo `giornata` della scheda (l'ultima giocata quando
    e' stata scritta: niente futuro). scarto = media dei giocatori con voto >= 1
    meno quella dei giocatori con voto <= -1; None se un gruppo e' vuoto.
    Schede senza `giornata` non entrano: il confine non si conosce."""
    import scouting
    residuo = {}
    for k, s in schede.items():
        g0 = s.get('giornata')
        if not isinstance(g0, int) or k not in stime_numeriche:
            continue
        fv = [r['fv'] for r in records if r['giornata'] > g0 and r.get('fv') is not None
              and voti.nomi.giocatore(r['nome']) == k]
        if fv:
            residuo[k] = sum(fv) / len(fv) - stime_numeriche[k]['mu']
    righe = []
    for kpi in scouting.KPI:
        alti, bassi = [], []
        for k, res in residuo.items():
            v = scouting._kpi_validi(schede[k]).get(kpi)
            if v and v['voto'] >= 1:
                alti.append(res)
            elif v and v['voto'] <= -1:
                bassi.append(res)
        scarto = sum(alti) / len(alti) - sum(bassi) / len(bassi) if alti and bassi else None
        righe.append({'kpi': kpi, 'n_alti': len(alti), 'n_bassi': len(bassi), 'scarto': scarto})
    return righe


def stampa_kpi(righe, n_schede, n_misurate):
    print(f'\n=== VERIFICA DELLO SCOUTING: {n_misurate} schede misurabili su {n_schede} ===')
    print('  scarto = (fantavoto - stima numerica) di chi ha voto alto meno chi ha voto basso,')
    print('  solo nelle giornate DOPO la scheda. Positivo = il KPI vede qualcosa che i numeri non vedono.\n')
    print(f'  {"KPI":<16}{"alti":>6}{"bassi":>7}{"scarto":>9}')
    for r in righe:
        sc = f'{r["scarto"]:>+9.2f}' if r['scarto'] is not None else '   nessun dato ancora'
        print(f'  {r["kpi"]:<16}{r["n_alti"]:>6}{r["n_bassi"]:>7}{sc}')
    misurati = [r for r in righe if r['scarto'] is not None]
    if misurati and sum(r['scarto'] for r in misurati) / len(misurati) <= 0:
        print('\n  LO SCOUTING NON BATTE I NUMERI su questi dati: i suoi pesi vanno abbassati.')
    elif misurati:
        print(f'\n  Casi pochi ({sum(r["n_alti"] + r["n_bassi"] for r in misurati)}): '
              'e un indizio, non una prova. Ricalibra i pesi solo a fine girone.')


def main():
    import socio
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--lega', default='lega.json')
    A = ap.parse_args()
    C = socio.Contesto(A.lega)
    stampa(backtest(voti.archivio(C.file['voti'], R=C.R), C.listone, C.partite, C.R, C.mia), C.R)


if __name__ == '__main__':
    main()
