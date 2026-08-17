# -*- coding: utf-8 -*-
"""squadre - lettura tecnico-tattica dei club, e cosa se ne puo' dedurre.

I dati per giocatore dicono chi e' bravo. I dati per squadra dicono in che
CONTESTO gioca - e il contesto e' meta' del rendimento: lo stesso attaccante
in una squadra che arriva 11 volte a partita in zona pericolosa (Inter) e in
una che ci arriva 2,8 (Cremonese) non e' lo stesso attaccante.

## Le metriche tattiche, e cosa dicono davvero

- **npxG/partita**: quanto la squadra produce, al netto dei rigori. E' il tetto
  dei bonus disponibili per i suoi attaccanti.
- **npxGA/partita**: quanto concede. E' il dato che mancava per valutare
  PORTIERI e DIFENSORI: un portiere non e' bravo o scarso in astratto, subisce
  i tiri che la sua squadra concede.
- **PPDA** (passes allowed per defensive action): quanti passaggi concede
  l'avversario prima di un'azione difensiva. **PIU' BASSO = PRESSA DI PIU'.**
  E' la misura piu' diretta dell'identita' tattica di un allenatore.
- **PPDA subito**: quanto la squadra viene pressata. Alto = la lasciano
  giocare (di solito perche' e' forte, o perche' non fa paura in ripartenza).
- **deep**: passaggi completati entro ~20 metri dalla porta. Quante volte
  arrivi davvero li' davanti, non quanto giri palla.
- **punti - xPunti**: quanto la classifica si discosta dai meriti. Grande
  scarto positivo = ha raccolto piu' del prodotto (rientra); negativo = ha
  raccolto meno (rimbalza) - e spesso e' li' che si trovano i giocatori
  sottovalutati.

## 🔴 Il limite che governa tutto il modulo

I dati sono della stagione **2025/26**. Per la 2026/27 **nove squadre su venti
hanno cambiato allenatore** e tre sono neopromosse senza alcun dato di Serie A.
Un dato tattico legato a un allenatore che se n'e' andato descrive il passato,
non prevede il futuro - e questo modulo lo dichiara riga per riga invece di
lasciartelo dedurre. E' la stessa regola del resto del progetto: l'assenza di
continuita' non e' un dettaglio da nota a pie' di pagina.

Uso:
    python squadre.py                      # quadro tattico completo
    python squadre.py --continuita         # chi ha cambiato e chi no
    python squadre.py --portieri           # forza difensiva -> valore portieri
    python squadre.py --squadra Como
"""
import argparse
import csv
import os

# ---------------------------------------------------------------- REGISTRO
# [MANUALE - aggiornato al 10/08/2026, fonte: rassegna stampa Serie A]
# Come il registro dei nodi di rete in land-scout: compilato a mano e DATATO.
# Un allenatore esonerato a ottobre rende questa tabella sbagliata, e non c'e'
# modo di accorgersene da soli: va riverificata prima di usarla.
ALLENATORI = {
    'Atalanta':   ('Maurizio Sarri', '4-3-3', 'NUOVO'),
    'Bologna':    ('Domenico Tedesco', '4-2-3-1', 'NUOVO'),
    'Cagliari':   ('Fabio Pisacane', '3-5-2', 'confermato'),
    'Como':       ('Cesc Fabregas', '4-2-3-1', 'confermato'),
    'Fiorentina': ('Fabio Grosso', '4-3-3', 'NUOVO'),
    'Frosinone':  ('Massimiliano Alvini', '4-3-3', 'NEOPROMOSSA'),
    'Genoa':      ('Daniele De Rossi', '3-4-2-1', 'confermato'),
    'Inter':      ('Cristian Chivu', '3-5-2', 'confermato'),
    'Juventus':   ('Luciano Spalletti', '3-4-2-1', 'confermato'),
    'Lazio':      ('Gennaro Gattuso', '4-2-3-1', 'NUOVO'),
    'Lecce':      ('Eusebio Di Francesco', '4-3-3', 'confermato'),
    'AC Milan':   ('Ruben Amorim', '3-4-2-1', 'NUOVO'),
    'Monza':      ('Ivan Juric', '3-4-2-1', 'NEOPROMOSSA'),
    'Napoli':     ('Massimiliano Allegri', '4-3-3', 'NUOVO'),
    'Parma Calcio 1913': ('Carlos Cuesta', '3-5-2', 'confermato'),
    'Roma':       ('Gian Piero Gasperini', '3-4-2-1', 'confermato'),
    'Sassuolo':   ('Alberto Aquilani', '3-4-2-1', 'NUOVO'),
    'Torino':     ('Ignazio Abate', '3-5-2', 'NUOVO'),
    'Udinese':    ('Kosta Runjaic', '3-5-2', 'confermato'),
    'Venezia':    ('Giovanni Stroppa', '3-5-2', 'NEOPROMOSSA'),
}
DATA_REGISTRO = '10/08/2026'

# Sigla del listone Fantacalcio -> nome Understat.
SIGLE = {'ATA': 'Atalanta', 'BOL': 'Bologna', 'CAG': 'Cagliari', 'COM': 'Como',
         'FIO': 'Fiorentina', 'GEN': 'Genoa', 'INT': 'Inter', 'JUV': 'Juventus',
         'LAZ': 'Lazio', 'LEC': 'Lecce', 'MIL': 'AC Milan', 'NAP': 'Napoli',
         'PAR': 'Parma Calcio 1913', 'ROM': 'Roma', 'SAS': 'Sassuolo',
         'TOR': 'Torino', 'UDI': 'Udinese',
         # Neopromosse: nessun dato Serie A 2025/26.
         'FRO': 'Frosinone', 'MON': 'Monza', 'VEN': 'Venezia'}

# Malus fantacalcio per gol subito dal portiere. Cambia da lega a lega.
MALUS_GOL_SUBITO = -1.0


def num(v, d=0.0):
    try:
        return float(str(v).replace(',', '.'))
    except (TypeError, ValueError):
        return d


def carica(path='squadre_2025-26.csv'):
    if not os.path.exists(path):
        raise SystemExit(f'[!] file squadre non trovato: {path}')
    with open(path, encoding='utf-8-sig', newline='') as f:
        dati = list(csv.DictReader(f, delimiter=';'))
    for r in dati:
        for k in ('npxG_p', 'npxGA_p', 'PPDA', 'PPDA_sub', 'Deep_p',
                  'Deep_sub_p', 'xPunti'):
            r[k] = num(r[k])
        for k in ('GolFatti', 'GolSubiti', 'CleanSheet', 'Punti', 'Partite'):
            r[k] = int(num(r[k]))
        r['scarto_punti'] = r['Punti'] - r['xPunti']
        all_ = ALLENATORI.get(r['Squadra'])
        r['allenatore'], r['modulo'], r['stato'] = all_ if all_ else ('?', '?', 'RETROCESSA')
    return dati


def stato_dato(r):
    """Quanto ci si puo' fidare del dato 2025/26 per prevedere il 2026/27."""
    if r['stato'] == 'RETROCESSA':
        return 'non in Serie A 2026/27'
    if r['stato'] == 'NEOPROMOSSA':
        return 'NESSUN DATO (neopromossa)'
    if r['stato'] == 'NUOVO':
        return 'PASSATO, non previsione (allenatore cambiato)'
    return 'utilizzabile (stessa guida tecnica)'


# ---------------------------------------------------------------- VISTE

def quadro(dati):
    v = [r for r in dati if r['stato'] != 'RETROCESSA']
    print('\n=== IDENTITA TATTICA (dati 2025/26) ===')
    print('    PPDA basso = pressa alto  |  Deep = arrivi in zona pericolosa per partita')
    print(f'    {"squadra":<20s}{"allenatore":<22s}{"mod":<9s}'
          f'{"npxG":>6s}{"npxGA":>7s}{"PPDA":>7s}{"Deep":>7s}{"CS":>4s}')
    for r in sorted(v, key=lambda x: -x['npxG_p']):
        marca = ' *' if r['stato'] == 'NUOVO' else ''
        print(f'    {r["Squadra"][:19]:<20s}{r["allenatore"][:21]:<22s}'
              f'{r["modulo"]:<9s}{r["npxG_p"]:>6.2f}{r["npxGA_p"]:>7.2f}'
              f'{r["PPDA"]:>7.2f}{r["Deep_p"]:>7.2f}{r["CleanSheet"]:>4d}{marca}')
    print('    * = allenatore cambiato: il dato descrive il passato, non prevede')

    manca = [s for s in SIGLE.values() if not any(r['Squadra'] == s for r in dati)]
    if manca:
        print(f'\n    SENZA DATI (neopromosse): {", ".join(manca)}')
        print('    Per queste il tool non ha NIENTE. Non e uno zero, e un buco.')


def continuita(dati):
    print(f'\n=== CONTINUITA TECNICA (registro manuale del {DATA_REGISTRO}) ===')
    gruppi = {'confermato': [], 'NUOVO': [], 'NEOPROMOSSA': []}
    for s, (a, m, st) in sorted(ALLENATORI.items()):
        gruppi.setdefault(st, []).append((s, a, m))
    print(f'\n  DATI UTILIZZABILI ({len(gruppi["confermato"])} squadre) '
          '- stessa guida tecnica, il 2025/26 dice qualcosa sul 2026/27')
    for s, a, m in gruppi['confermato']:
        r = next((x for x in dati if x['Squadra'] == s), None)
        extra = f'  npxG {r["npxG_p"]:.2f} · npxGA {r["npxGA_p"]:.2f} · PPDA {r["PPDA"]:.1f}' if r else ''
        print(f'    {s[:20]:<21s}{a[:22]:<23s}{m:<9s}{extra}')
    print(f'\n  DATI DA NON USARE COME PREVISIONE ({len(gruppi["NUOVO"])} squadre) '
          '- allenatore cambiato')
    for s, a, m in gruppi['NUOVO']:
        r = next((x for x in dati if x['Squadra'] == s), None)
        extra = f'  (era: npxG {r["npxG_p"]:.2f} · PPDA {r["PPDA"]:.1f})' if r else ''
        print(f'    {s[:20]:<21s}{a[:22]:<23s}{m:<9s}{extra}')
    print(f'\n  NESSUN DATO ({len(gruppi["NEOPROMOSSA"])} squadre) - neopromosse')
    for s, a, m in gruppi['NEOPROMOSSA']:
        print(f'    {s[:20]:<21s}{a[:22]:<23s}{m}')
    print(f'\n  In sintesi: su 20 squadre, il dato tattico e utilizzabile su '
          f'{len(gruppi["confermato"])}.')


def portieri(dati):
    """La forza difensiva della squadra vale piu' della bravura del portiere.

    Chiude il limite dichiarato del tool: i portieri venivano valutati sulla
    fantamedia storica, che pero' dipende quasi solo da quanti gol prende la
    squadra. Qui il dato diventa esplicito.
    """
    v = [r for r in dati if r['stato'] not in ('RETROCESSA', 'NEOPROMOSSA')]
    if not v:
        return
    peggiore = max(r['npxGA_p'] for r in v)
    print('\n=== FORZA DIFENSIVA -> VALORE DEL PORTIERE ===')
    print('    Un portiere non subisce i gol che merita: subisce quelli che la squadra concede.')
    print(f'    Il vantaggio e calcolato sul peggiore del campionato ({peggiore:.2f} npxGA/partita),')
    print(f'    con malus {MALUS_GOL_SUBITO:+.0f} per gol subito su 38 giornate.')
    print(f'\n    {"squadra":<20s}{"npxGA/p":>9s}{"CS 25/26":>10s}'
          f'{"punti fanta risparmiati":>26s}   guida tecnica')
    for r in sorted(v, key=lambda x: x['npxGA_p']):
        vantaggio = (peggiore - r['npxGA_p']) * abs(MALUS_GOL_SUBITO) * 38
        nota = '' if r['stato'] == 'confermato' else '  <- allenatore NUOVO'
        print(f'    {r["Squadra"][:19]:<20s}{r["npxGA_p"]:>9.2f}{r["CleanSheet"]:>10d}'
              f'{vantaggio:>26.0f}{nota}')
    print('\n    Lettura: fra il portiere della difesa migliore e quello della peggiore')
    print(f'    ballano ~{(peggiore - min(r["npxGA_p"] for r in v)) * 38:.0f} punti fanta in una stagione,')
    print('    a parita di bravura del portiere. E il motivo per cui i portieri')
    print('    si comprano guardando la SQUADRA, non il nome.')


def field_tilt(dati):
    """Dove avviene il possesso, non quanto ce n'e'.

    Il possesso totale e' quasi inutile: ce l'ha anche chi gira palla dietro.
    Il field tilt guarda solo la zona che conta: quota dei passaggi profondi
    (entro ~20 m dalla porta) prodotti sul totale prodotti+concessi.

    50% = equilibrio. Sopra = la partita si gioca nella meta' avversaria.

    E' una versione semplificata: il field tilt canonico usa i tocchi nel terzo
    offensivo, qui si usano i `deep` di Understat, che sono l'unica cosa
    disponibile. Misura la stessa idea con un proxy piu' grezzo, e va detto.
    """
    v = [r for r in dati if r['stato'] != 'RETROCESSA']
    print('\n=== FIELD TILT — dove si gioca la partita ===')
    print('    quota dei passaggi profondi prodotti su (prodotti + concessi)')
    print('    50% = equilibrio · sopra = comandi il campo · [proxy sui `deep`, non sui tocchi]')
    print(f'    {"squadra":<20s}{"tilt":>8s}{"deep":>8s}{"subiti":>8s}{"PPDA":>7s}   guida tecnica')
    for r in sorted(v, key=lambda x: -(x['Deep_p'] / (x['Deep_p'] + x['Deep_sub_p']))):
        tilt = 100 * r['Deep_p'] / (r['Deep_p'] + r['Deep_sub_p'])
        nota = '' if r['stato'] == 'confermato' else f'  <- {r["stato"]}'
        print(f'    {r["Squadra"][:19]:<20s}{tilt:>7.1f}%{r["Deep_p"]:>8.2f}'
              f'{r["Deep_sub_p"]:>8.2f}{r["PPDA"]:>7.2f}{nota}')


def tenuta_difensiva(dati):
    """Quanto la squadra ha subito MENO (o piu') dei gol attesi.

    ⚠️ QUESTO NON E' PSxG, e la differenza conta.

    PSxG (post-shot xG) misura la difficolta' dei tiri EFFETTIVAMENTE SUBITI e
    isola cosi' il portiere dalla difesa davanti a lui. E' la metrica giusta per
    valutare un portiere, e **non e' piu' disponibile gratuitamente**: il
    20/01/2026 Opta ha revocato a FBref tutte le statistiche avanzate, PSxG
    compreso.

    Quello che si puo' fare con i dati Understat e' un proxy piu' grezzo:
    `npxGA totale - gol subiti`. Dice quanto la squadra ha concesso meno del
    previsto, ma **mescola tre cose che PSxG separa**: le parate del portiere,
    la capacita' della difesa di deviare e ostacolare, e la fortuna.

    Un valore alto NON dimostra che il portiere e' bravo. Suggerisce di
    guardare, e nient'altro. Chiamarlo "indice del portiere" sarebbe
    esattamente il tipo di scorciatoia che questo progetto evita.
    """
    v = [r for r in dati if r['stato'] != 'RETROCESSA']
    print('\n=== TENUTA DIFENSIVA vs ATTESA (proxy grezzo, NON PSxG) ===')
    print('    npxGA totale meno gol effettivamente subiti, su 38 giornate.')
    print('    positivo = ha subito MENO del previsto (parate, deviazioni, fortuna: indistinti)')
    print(f'    {"squadra":<20s}{"npxGA tot":>11s}{"subiti":>8s}{"scarto":>9s}   lettura')
    for r in sorted(v, key=lambda x: -(x['npxGA_p'] * x['Partite'] - x['GolSubiti'])):
        atteso = r['npxGA_p'] * r['Partite']
        scarto = atteso - r['GolSubiti']
        if scarto > 4:
            lettura = 'ha tenuto molto meglio dell atteso'
        elif scarto < -4:
            lettura = 'ha subito piu del previsto'
        else:
            lettura = 'in linea'
        print(f'    {r["Squadra"][:19]:<20s}{atteso:>11.1f}{r["GolSubiti"]:>8d}'
              f'{scarto:>+9.1f}   {lettura}')
    print('\n    ⚠️ Non attribuire questo scarto al portiere: senza PSxG non si puo')
    print('    distinguere una parata da un tiro deviato o da un palo. Serve solo')
    print('    a sapere DOVE guardare, non a concludere.')


def sorprese(dati):
    v = [r for r in dati if r['stato'] != 'RETROCESSA']
    print('\n=== CLASSIFICA vs MERITI (punti - punti attesi) ===')
    print('    positivo = ha raccolto piu del prodotto (di solito rientra)')
    print('    negativo = ha raccolto meno (di solito rimbalza: e li che si trova valore a sconto)')
    print(f'    {"squadra":<20s}{"punti":>7s}{"attesi":>8s}{"scarto":>8s}   guida tecnica')
    for r in sorted(v, key=lambda x: -x['scarto_punti']):
        nota = '' if r['stato'] == 'confermato' else f'  <- {r["stato"]}'
        print(f'    {r["Squadra"][:19]:<20s}{r["Punti"]:>7d}{r["xPunti"]:>8.1f}'
              f'{r["scarto_punti"]:>+8.1f}{nota}')


def contesto_giocatore(sigla, dati):
    """Dato il codice squadra del listone, dice in che contesto gioca."""
    nome = SIGLE.get(sigla.upper())
    if not nome:
        return None
    r = next((x for x in dati if x['Squadra'] == nome), None)
    if r is None:
        return {'squadra': nome, 'dato': 'NESSUNO (neopromossa)',
                'allenatore': ALLENATORI.get(nome, ('?',))[0]}
    return {'squadra': nome, 'allenatore': r['allenatore'], 'modulo': r['modulo'],
            'npxG_p': r['npxG_p'], 'npxGA_p': r['npxGA_p'], 'ppda': r['PPDA'],
            'deep': r['Deep_p'], 'affidabilita': stato_dato(r)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', default='squadre_2025-26.csv')
    ap.add_argument('--squadra', default=None)
    ap.add_argument('--continuita', action='store_true')
    ap.add_argument('--portieri', action='store_true')
    ap.add_argument('--sorprese', action='store_true')
    ap.add_argument('--tilt', action='store_true', help='field tilt: dove si gioca')
    ap.add_argument('--tenuta', action='store_true',
                    help='tenuta difensiva vs attesa (proxy grezzo, NON PSxG)')
    A = ap.parse_args()

    dati = carica(A.file)
    print('=' * 82)
    print(f'  analisi tecnico-tattica · dati 2025/26 · registro allenatori {DATA_REGISTRO}')
    print('=' * 82)

    if A.squadra:
        r = next((x for x in dati if A.squadra.lower() in x['Squadra'].lower()), None)
        if not r:
            raise SystemExit(f'squadra "{A.squadra}" non trovata')
        print(f'\n  {r["Squadra"]} — {r["allenatore"]} ({r["modulo"]})')
        print(f'  affidabilita del dato: {stato_dato(r)}\n')
        print(f'  produzione attesa   npxG/partita   {r["npxG_p"]:.2f}')
        print(f'  concessione attesa  npxGA/partita  {r["npxGA_p"]:.2f}')
        print(f'  pressing            PPDA           {r["PPDA"]:.2f}  '
              f'({"alto" if r["PPDA"] < 11 else "medio" if r["PPDA"] < 14 else "basso"})')
        print(f'  subisce pressing    PPDA sub       {r["PPDA_sub"]:.2f}')
        print(f'  arrivi in area      deep/partita   {r["Deep_p"]:.2f}  '
              f'(subiti {r["Deep_sub_p"]:.2f})')
        print(f'  gol {r["GolFatti"]} fatti / {r["GolSubiti"]} subiti · '
              f'{r["CleanSheet"]} clean sheet')
        print(f'  punti {r["Punti"]} vs attesi {r["xPunti"]:.1f} '
              f'({r["scarto_punti"]:+.1f})')
        print()
        return

    if A.continuita:
        continuita(dati)
    elif A.portieri:
        portieri(dati)
    elif A.sorprese:
        sorprese(dati)
    elif A.tilt:
        field_tilt(dati)
    elif A.tenuta:
        tenuta_difensiva(dati)
    else:
        quadro(dati)
        continuita(dati)
        field_tilt(dati)
        portieri(dati)
        tenuta_difensiva(dati)
        sorprese(dati)
    print()


if __name__ == '__main__':
    main()
