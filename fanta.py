# -*- coding: utf-8 -*-
"""fanta-asta - prezzi limite per l'asta, tarati sulla TUA lega.

Il ranking dei giocatori e' una commodity: le quotazioni ufficiali ce le hanno
tutti e i tuoi nove avversari leggono le stesse statistiche. Quello che decide
l'asta non e' il valore del giocatore, e' il SURPLUS: valore atteso meno prezzo
atteso. E il prezzo dipende dalla tua lega, non dalla media nazionale.

Tre idee, e nessuna e' mia: vengono dal fantasy football americano, dove il
problema dell'asta e' stato studiato per trent'anni.

1. VORP (value over replacement player)
   Un giocatore non vale i suoi fantapunti: vale QUANTO SUPERA il peggior
   titolare che prenderesti comunque nel suo ruolo. Con 10 squadre x 3 portieri,
   il 30esimo portiere e' il tuo pavimento: se un portiere fa 5 punti in piu' di
   lui, quei 5 punti sono tutto cio' che stai comprando davvero.
   Il pavimento cambia con la lega: e' il motivo per cui un tool generico
   sbaglia sistematicamente.

2. Somma zero
   10 squadre x 500 crediti = 5.000 crediti che verranno spesi TUTTI su 250
   giocatori. Il prezzo giusto non e' una proprieta' del giocatore: e' la quota
   di un budget fisso. Quindi la somma dei prezzi consigliati deve fare
   esattamente 5.000 - e qui la fa, per costruzione.

3. Prezzo di riserva dinamico
   A meta' asta i limiti vanno rifatti. Se i tre attaccanti in lista sono andati,
   il quarto vale di piu': non e' migliorato lui, e' peggiorata l'alternativa.
   E' quello che fa `--live`.

## La regola di casa

Se manca il dato, il tool lo dice e non inventa. In particolare: se il file di
quotazioni non ha statistiche storiche, il tool usa la quotazione ufficiale come
proxy del valore e AVVISA che in quel caso sta solo riordinando il consenso di
mercato, non battendolo. Un tool che tace la differenza fra "ho stimato" e "ho
copiato il mercato" e' peggio di nessun tool.

Uso:
    python fanta.py --quot quotazioni.xlsx                 # listone completo
    python fanta.py --quot quotazioni.xlsx --ruolo A       # solo attaccanti
    python fanta.py --quot quotazioni.xlsx --live asta.json  # durante l'asta
"""
import argparse
import csv
import json
import os
import re
import sys

# ------------------------------------------------------------------ CONFIG

# Rosa Classic standard. Cambiali se la tua lega e' diversa.
SLOT = {'P': 3, 'D': 8, 'C': 8, 'A': 6}
SQUADRE = 10
BUDGET = 500

# Quanti ne SCHIERI, non quanti ne compri. Modulo di riferimento 3-4-3.
# 🔑 E' la correzione piu' importante del tool, e nasce da un difetto che
# avevo dichiarato due volte senza chiuderlo: i portieri risultavano
# sistematicamente sopravvalutati.
#
# Il motivo era il pavimento di sostituzione. Con 3 portieri x 10 squadre il
# pavimento era il 30esimo portiere - cioe' un terzo portiere che non gioca
# mai e vale ~0 punti. Rispetto a quello, QUALUNQUE titolare ha un VORP
# enorme. Ma il terzo portiere non e' la tua alternativa reale: la tua
# alternativa reale e' l'ultimo portiere TITOLARE disponibile.
#
# Vale per tutti i ruoli (compri 8 difensori e ne schieri 3), ma sui portieri
# e' devastante perche' il rapporto e' 3:1.
TITOLARI = {'P': 1, 'D': 3, 'C': 4, 'A': 3}

# Quanto la panchina conta nel definire il pavimento. 0.0 = pavimento sui soli
# titolari (severo), 1.0 = comportamento vecchio, sugli slot totali.
# [STIMA] 0.35: una riserva ha valore (infortuni, turnover) ma molto minore.
PESO_PANCHINA = 0.35

# Presenze attese per stagione (38 giornate) quando il dato storico manca.
# [STIMA] ordine di grandezza, non promessa: serve solo a non trattare un
# titolare e una riserva come se giocassero uguale.
PRES_ATTESE = {'P': 34.0, 'D': 28.0, 'C': 27.0, 'A': 26.0}

# Quante presenze prendersi da chi NON e' nell'XI di riferimento. Non e' zero:
# la rosa ruota, e chi sta fuori a agosto gioca comunque una parte di stagione.
# [STIMA] 0.45, tarata a mano contro lo split FVM (v. --calibra).
FUORI_XI = 0.45

# Quanto la fantamedia storica va tirata verso la media del ruolo. Una stagione
# sola e' poco campione: chi ha fatto 7.5 di fantamedia in 12 partite quasi
# sicuramente non lo rifa'. [STIMA] 0.35 = regressione moderata.
REGRESSIONE = 0.35


class DatoMancante(Exception):
    """Il file non ha quello che serve. Meglio fermarsi che indovinare."""


# ------------------------------------------------------------------ INPUT

# I file in giro hanno nomi di colonna tutti diversi. Qui si dichiara cosa
# cerchiamo; se non lo troviamo lo diciamo, non lo riempiamo.
COLONNE = {
    'nome':   ['nome', 'giocatore', 'calciatore', 'player'],
    'ruolo':  ['ruolo', 'r', 'rm', 'role'],
    'squadra': ['squadra', 'team', 'club'],
    'quota':  ['quotazione', 'qt', 'qta', 'quota', 'qt.a', 'qtainiziale',
               'quotazioneiniziale', 'crediti'],
    'fm':     ['fantamedia', 'fm', 'mediafanta', 'fantamediavoto'],
    'mv':     ['mediavoto', 'mv', 'media'],
    'pres':   ['presenze', 'pg', 'partite', 'pv', 'presenzecampionato'],
    # FVM = stima del prezzo d'asta di Fantacalcio.it. Non serve al calcolo:
    # serve a CONTROLLARLO (vedi --calibra).
    'fvm':    ['fvm', 'fantavalore', 'fantavaloremercato', 'valoremercato'],
}

RUOLI_VALIDI = set(SLOT)
# I ruoli Mantra ricadono nel reparto Classic corrispondente.
MANTRA = {'POR': 'P', 'DC': 'D', 'DD': 'D', 'DS': 'D', 'B': 'D', 'E': 'D',
          'M': 'C', 'C': 'C', 'W': 'C', 'T': 'C', 'A': 'A', 'PC': 'A'}


def _norm(s):
    """'Qt. A' -> 'qta'. Toglie tutto cio' che varia fra un file e l'altro."""
    return re.sub(r'[^a-z0-9]', '', str(s).lower())


def _mappa_colonne(intestazione):
    """Dice quale colonna del file corrisponde a quale campo, o None."""
    norm = [_norm(h) for h in intestazione]
    out = {}
    for campo, candidati in COLONNE.items():
        trovato = None
        for cand in candidati:
            if cand in norm:
                trovato = norm.index(cand)
                break
        out[campo] = trovato
    return out


def _num(v):
    """Converte in float accettando la virgola decimale italiana. None se non e' un numero."""
    if v is None:
        return None
    s = str(v).strip().replace(',', '.')
    if not s or s in {'-', 'None', 'nan', 'N/D'}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _righe_da_file(path):
    """Restituisce (intestazione, righe). Gestisce csv e xlsx."""
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.csv', '.txt'):
        with open(path, encoding='utf-8-sig', newline='') as f:
            campione = f.read(4096)
            f.seek(0)
            try:
                dial = csv.Sniffer().sniff(campione, delimiters=';,\t')
            except csv.Error:
                dial = csv.excel
            righe = [r for r in csv.reader(f, dial) if any(c.strip() for c in r)]
        if not righe:
            raise DatoMancante(f'{path} e vuoto')
        return righe[0], righe[1:]

    if ext in ('.xlsx', '.xlsm'):
        try:
            import openpyxl
        except ImportError:
            raise DatoMancante(
                'per leggere un .xlsx serve openpyxl:  pip install openpyxl\n'
                "   (in alternativa apri il file in Excel e salvalo come CSV)")
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb[wb.sheetnames[0]]
        righe = [[c for c in r] for r in ws.iter_rows(values_only=True)]
        righe = [r for r in righe if any(c is not None and str(c).strip() for c in r)]
        # I listoni ufficiali hanno spesso 1-2 righe di titolo prima delle
        # intestazioni vere: la riga buona e' la prima che contiene 'ruolo'.
        for i, r in enumerate(righe[:10]):
            if any(_norm(c) in COLONNE['ruolo'] for c in r if c is not None):
                return righe[i], righe[i + 1:]
        return righe[0], righe[1:]

    raise DatoMancante(f'formato non gestito: {ext} (usa .csv o .xlsx)')


def carica(path):
    """File di quotazioni -> lista di giocatori. Dichiara cosa ha trovato."""
    intest, righe = _righe_da_file(path)
    col = _mappa_colonne(intest)

    if col['nome'] is None or col['ruolo'] is None:
        raise DatoMancante(
            'nel file non trovo le colonne NOME e RUOLO.\n'
            f'   intestazioni lette: {[str(h) for h in intest][:12]}')
    if col['quota'] is None:
        raise DatoMancante('nel file non trovo la colonna QUOTAZIONE.')

    giocatori, scartate = [], 0
    for r in righe:
        def get(campo):
            i = col[campo]
            if i is None or i >= len(r):
                return None
            return r[i]

        nome = str(get('nome') or '').strip()
        ruolo_raw = str(get('ruolo') or '').strip().upper()
        ruolo = ruolo_raw if ruolo_raw in RUOLI_VALIDI else MANTRA.get(ruolo_raw)
        quota = _num(get('quota'))
        if not nome or ruolo is None or quota is None:
            scartate += 1
            continue

        giocatori.append({
            'nome': nome,
            'ruolo': ruolo,
            'squadra': str(get('squadra') or '').strip(),
            'quota': quota,
            'fm': _num(get('fm')),
            'mv': _num(get('mv')),
            'pres': _num(get('pres')),
            'fvm': _num(get('fvm')),
        })

    if not giocatori:
        raise DatoMancante('nessuna riga valida nel file.')

    con_storico = sum(1 for g in giocatori if g['fm'] is not None)
    return {
        'giocatori': giocatori,
        'scartate': scartate,
        'con_storico': con_storico,
        # Il flag che cambia il significato di tutto l'output.
        'ha_storico': con_storico >= 0.5 * len(giocatori),
        'colonne_trovate': {k: (v is not None) for k, v in col.items()},
    }


# ------------------------------------------------------------------ VALORE

# Quanto le presenze passate vanno tagliate per chi oggi non e' piu' titolare.
# [STIMA] esponente scelto da me, non da una fonte: 0.5 e' una via di mezzo fra
# ignorare del tutto la quotazione (1.0) e fidarsene ciecamente (lineare).
# E' il parametro piu' arbitrario del tool ed e' per questo che sta qui in cima,
# con scritto sopra che e' arbitrario.
ESP_TITOLARITA = 0.5


def fattore_titolarita(g, quota_rif):
    """Il mercato sa CHI GIOCA, lo storico sa QUANTO VALE. Questa funzione usa
    il primo per correggere il secondo, e solo per quello.

    Nasce da un errore vero, visto sui dati reali: Provedel ha 27 presenze con
    la Lazio 2025/26 e oggi e' la riserva dell'Inter a quotazione 2; Paleari ne
    ha 29 ed e' quotato 1. Usando le presenze storiche come presenze attese, il
    tool li metteva in cima alle occasioni e consigliava di scartare i titolari
    che hanno preso il loro posto. Le presenze passate non sono presenze attese
    quando il ruolo in squadra e' cambiato - e l'unico segnale disponibile su
    chi gioca OGGI e' la quotazione, perche' il mercato quello lo sa.

    Non tocca la qualita' stimata del giocatore: solo quante partite ci si
    aspetta che giochi.
    """
    if not quota_rif or quota_rif <= 0 or not g.get('quota'):
        return 1.0
    return min(1.0, (g['quota'] / quota_rif) ** ESP_TITOLARITA)


def punti_attesi(g, ha_storico):
    """Fantapunti stagionali attesi.

    Con lo storico: fantamedia regredita verso la media del ruolo, per presenze
    attese. Senza: si ripiega sulla quotazione ufficiale - che e' il consenso di
    mercato, non una stima indipendente. Chi chiama deve saperlo, ed e' per
    questo che `ha_storico` viaggia fino all'output.
    """
    if not ha_storico or g['fm'] is None:
        return None
    pres = g['pres'] if g['pres'] else PRES_ATTESE[g['ruolo']]
    # Poche presenze = campione piccolo = piu' regressione.
    peso_campione = min(1.0, (g['pres'] or 0) / 25.0) if g['pres'] else 0.4
    reg = REGRESSIONE + (1 - REGRESSIONE) * (1 - peso_campione)
    return {'fm_grezza': g['fm'], 'pres_attese': pres, 'regressione': reg}


def applica_avanzate(dati, path):
    """Sostituisce i bonus REALIZZATI con quelli ATTESI (npxG, xA).

    La fantamedia e' `voto + bonus - malus`. Il voto del giornalista e' rumoroso
    e non si modella; i BONUS invece si', e si modellano meglio con npxG e xA che
    coi gol e assist realizzati - perche' su 30 partite il gol e' un evento raro
    e la fortuna pesa quanto la bravura.

    Quindi: si toglie dalla fantamedia il contributo dei bonus veri e si rimette
    quello dei bonus attesi. Il voto base resta intatto: non abbiamo niente di
    meglio per stimarlo, e fingere il contrario sarebbe peggio.

    Chi non ha riscontro nei dati avanzati resta con la fantamedia grezza, e il
    conteggio di quanti sono viene dichiarato: e' l'unico modo di sapere quanto
    dell'output poggia sul modello e quanto sull'anno scorso.
    """
    try:
        import analisi
    except ImportError:
        return dati, {'errore': 'analisi.py non importabile'}

    av = analisi.carica(path)
    idx = analisi.indicizza(av)

    corretti, ambigui, mancanti = 0, [], []
    for g in dati['giocatori']:
        if g.get('fm') is None or not g.get('pres'):
            continue
        rec, motivo = analisi.accoppia(g['nome'], idx)
        if rec is None:
            (ambigui if 'AMBIGUO' in motivo else mancanti).append((g['nome'], motivo))
            continue
        pres = g['pres'] or 1
        # bonus per partita, realizzati e attesi
        b_veri = (analisi.num(rec['NPG']) * analisi.PUNTI_GOL +
                  analisi.num(rec['Assist']) * analisi.PUNTI_ASSIST) / pres
        b_attesi = (analisi.num(rec['npxG']) * analisi.PUNTI_GOL +
                    analisi.num(rec['xA']) * analisi.PUNTI_ASSIST) / pres
        g['fm_grezza'] = g['fm']
        g['fm'] = g['fm'] - b_veri + b_attesi
        g['delta_bonus'] = b_attesi - b_veri
        g['avanzate'] = rec
        corretti += 1

    dati['avanzate'] = {'corretti': corretti, 'ambigui': ambigui,
                        'mancanti': mancanti, 'totale_av': len(av)}
    return dati, dati['avanzate']


def applica_contesto_squadra(dati, path='squadre_2025-26.csv'):
    """Corregge i PORTIERI con la forza difensiva della squadra in cui giocano ORA.

    Chiude il difetto piu' grosso rimasto. Un portiere non subisce i gol che
    merita: subisce quelli che la sua difesa concede. La fantamedia storica di
    Falcone incorpora i gol del Lecce, che ne concede piu' di chiunque altro -
    e il tool lo metteva in cima alle occasioni perche' guardava le 38 presenze
    e ignorava il contesto. Fra la difesa migliore e la peggiore ballano ~28
    punti fanta a stagione, a parita' di bravura del portiere.

    Correzione: si sostituisce la concessione della squadra PASSATA con quella
    della squadra ATTUALE. Se il portiere resta dov'era, la correzione e' zero
    per costruzione.

    Non tocca gli altri ruoli: per loro il contesto conta ma passa da npxG e xA,
    che sono gia' misurati sul giocatore. Qui il dato mancava del tutto.
    """
    try:
        import squadre
    except ImportError:
        return dati, {'errore': 'squadre.py non importabile'}
    if not os.path.exists(path):
        return dati, {'errore': f'{path} non trovato'}

    sq = squadre.carica(path)
    per_nome = {r['Squadra']: r for r in sq}
    media = sum(r['npxGA_p'] for r in sq) / len(sq)

    corretti, senza_dato = 0, []
    for g in dati['giocatori']:
        if g['ruolo'] != 'P' or g.get('fm') is None:
            continue
        nome_att = squadre.SIGLE.get(g['squadra'].upper())
        att = per_nome.get(nome_att) if nome_att else None
        if att is None:
            # Neopromossa: nessun dato. Si dichiara, non si inventa.
            senza_dato.append(g['nome'])
            g['contesto'] = 'NESSUN DATO (neopromossa)'
            continue

        # Squadra della stagione scorsa, dai dati avanzati se accoppiati.
        rec = g.get('avanzate')
        pas = per_nome.get(rec['Squadra']) if rec else None
        npxga_pas = pas['npxGA_p'] if pas else media

        delta = (att['npxGA_p'] - npxga_pas) * squadre.MALUS_GOL_SUBITO
        g['fm'] = g['fm'] + delta
        g['delta_contesto'] = delta
        g['contesto'] = (f"{att['allenatore']} · npxGA {att['npxGA_p']:.2f}"
                         f"{' · allenatore NUOVO' if att['stato'] == 'NUOVO' else ''}")
        corretti += 1

    dati['contesto_squadra'] = {'corretti': corretti, 'senza_dato': senza_dato,
                                'media_npxGA': media}
    return dati, dati['contesto_squadra']


def _fm_media_ruolo(giocatori, ruolo, n_rilevanti):
    """Fantamedia di riferimento del ruolo: media dei giocatori che verranno
    davvero presi, non di tutto il listone (dove 400 riserve la schiacciano)."""
    v = sorted((g['fm'] for g in giocatori
                if g['ruolo'] == ruolo and g['fm'] is not None), reverse=True)
    v = v[:n_rilevanti] or v
    return sum(v) / len(v) if v else 0.0


def valuta(dati, titolari=None):
    """Assegna a ogni giocatore i punti attesi della stagione.

    `titolari` = insieme di nomi (minuscoli) nell'XI di riferimento di oggi.
    Quando c'e', SOSTITUISCE l'inferenza della titolarita': le presenze
    dell'anno scorso e la quotazione erano due proxy indiretti, l'XI e' il dato.
    E' la correzione del difetto n.1 - v. formazioni.py.
    """
    G, ha_storico = dati['giocatori'], dati['ha_storico']
    presi = {r: SLOT[r] * SQUADRE for r in SLOT}

    medie = {r: _fm_media_ruolo(G, r, presi[r]) for r in SLOT} if ha_storico else {}

    # Quotazione di riferimento del ruolo = mediana di quelli che verranno presi.
    # E' il metro per capire chi il mercato considera titolare.
    quota_rif = {}
    for r in SLOT:
        q = sorted((x['quota'] for x in G if x['ruolo'] == r), reverse=True)[:presi[r]]
        quota_rif[r] = q[len(q) // 2] if q else 0

    for g in G:
        p = punti_attesi(g, ha_storico)
        if p is None:
            # Nessuna stima indipendente: si usa il mercato e lo si dichiara.
            g['punti'] = g['quota']
            g['base'] = 'quotazione'
        else:
            fm = (1 - p['regressione']) * p['fm_grezza'] + p['regressione'] * medie[g['ruolo']]
            if titolari is None:
                g['titolarita'] = fattore_titolarita(g, quota_rif[g['ruolo']])
                g['pres_attese'] = p['pres_attese'] * g['titolarita']
            else:
                # Osservato batte inferito. La base e' uguale per tutti nel ruolo:
                # a distinguere e' l'XI di oggi, non quanto ha giocato l'anno
                # scorso - che era esattamente cio' che confondeva un portiere
                # promosso a titolare con uno retrocesso a riserva.
                g['titolarita'] = 1.0 if g['nome'].strip().lower() in titolari else FUORI_XI
                g['pres_attese'] = PRES_ATTESE[g['ruolo']] * g['titolarita']
            g['punti'] = fm * g['pres_attese']
            g['base'] = 'storico'
    dati['quota_rif'] = quota_rif
    return dati


# ------------------------------------------------------------------ VORP

def vorp(dati, presi=None):
    """Valore sopra il rimpiazzo, per ruolo.

    `presi` = {ruolo: quanti ne sono gia' stati comprati nella lega}. Serve al
    live: se sono gia' andati 40 attaccanti su 60, il pavimento si abbassa e i
    superstiti valgono di piu'.
    """
    G = dati['giocatori']
    presi = presi or {}
    fuori = {g['nome'] for g in G if g.get('venduto')}

    for r in SLOT:
        disponibili = sorted(
            (g for g in G if g['ruolo'] == r and g['nome'] not in fuori),
            key=lambda x: -x['punti'])
        # Quanti ne servono ancora alla lega in questo ruolo (acquisti).
        residui = max(0, SLOT[r] * SQUADRE - presi.get(r, 0))
        if not disponibili:
            continue
        # 🔑 Il pavimento NON e' l'ultimo che verra' comprato: e' l'ultimo che
        # verra' SCHIERATO. Chi compri e non metti mai in campo non e' la tua
        # alternativa - la tua alternativa e' il peggior titolare disponibile.
        # Fra i due estremi si interpola con PESO_PANCHINA.
        # ponytail: la soglia e' in PUNTI TOTALI, quindi include le presenze
        # dell'anno scorso del rimpiazzo - che per una riserva sono ~2 e non
        # dicono quanto vale. Testato il 17/08/2026 il pavimento in QUALITA'
        # (fm del rango x PRES_ATTESE): sistema i portieri (827 -> 358 contro
        # 297 di mercato) ma rompe gli attaccanti (1917 -> 1279 contro 2051),
        # perche' il budget e' a somma zero. Scartato: scarto totale 1126 ->
        # 1544. Si riapre solo con le presenze ATTESE 2026/27 (probabili
        # formazioni), non con un'altra taratura di PESO_PANCHINA.
        tit = TITOLARI.get(r, SLOT[r]) * SQUADRE
        rif = tit + PESO_PANCHINA * (SLOT[r] * SQUADRE - tit)
        # Durante l'asta il riferimento scala insieme ai giocatori gia' venduti,
        # nella stessa proporzione degli slot residui.
        if SLOT[r] * SQUADRE > 0:
            rif *= residui / float(SLOT[r] * SQUADRE)
        idx = min(int(round(rif)), len(disponibili)) - 1
        soglia = disponibili[idx]['punti'] if idx >= 0 else disponibili[-1]['punti']
        for g in disponibili:
            g['vorp'] = max(0.0, g['punti'] - soglia)
        for g in (x for x in G if x['ruolo'] == r and x['nome'] in fuori):
            g['vorp'] = 0.0
        dati.setdefault('soglie', {})[r] = soglia
        dati.setdefault('residui', {})[r] = residui
    return dati


def prezzi(dati, budget_disponibile=None, slot_residui=None):
    """VORP -> crediti. La somma dei prezzi esaurisce ESATTAMENTE il budget.

    Ogni giocatore costa almeno 1: quei crediti sono impegnati a prescindere.
    Il resto e' budget discrezionale, ripartito in proporzione al VORP.
    """
    G = dati['giocatori']
    fuori = {g['nome'] for g in G if g.get('venduto')}

    tot_slot = slot_residui if slot_residui is not None else sum(SLOT.values()) * SQUADRE
    tot_budget = budget_disponibile if budget_disponibile is not None else BUDGET * SQUADRE

    discrezionale = max(0.0, tot_budget - tot_slot)
    somma_vorp = sum(g.get('vorp', 0.0) for g in G if g['nome'] not in fuori)

    for g in G:
        if g['nome'] in fuori:
            g['prezzo'] = None
            continue
        if somma_vorp <= 0:
            g['prezzo'] = 1.0
            continue
        g['prezzo'] = 1.0 + discrezionale * (g.get('vorp', 0.0) / somma_vorp)

    # --- lo scarto va calcolato fra grandezze OMOGENEE ---
    # Trovato provando il tool sulle quotazioni ufficiali vere: la quotazione di
    # Fantacalcio.it vive su una scala sua (1-35) che NON somma al budget della
    # lega. Confrontarla col limite in crediti dava "+71 su Lautaro", che si
    # legge come un affare colossale ed e' solo un cambio di unita' di misura.
    # Le quotazioni si riportano quindi sulla stessa scala: quanto varrebbe
    # quella quotazione se il mercato spendesse esattamente i crediti della lega.
    disponibili = [g for g in G if g['nome'] not in fuori]
    da_prendere = sorted(disponibili, key=lambda x: -x.get('vorp', 0.0))[:int(tot_slot)]
    somma_quote = sum(g['quota'] for g in da_prendere)
    scala = (tot_budget / somma_quote) if somma_quote > 0 else 1.0

    for g in disponibili:
        g['quota_scalata'] = g['quota'] * scala
        g['scarto'] = g['prezzo'] - g['quota_scalata']

    # --- allocazione fra reparti: il modello non ha edge, il mercato si' ---
    # Misurato il 17/08/2026 con l'XI osservato collegato: l'accordo col mercato
    # GIOCATORE PER GIOCATORE sale in tutti e 4 i ruoli (Spearman medio 0,375 ->
    # 0,459), ma lo split di budget FRA reparti peggiora (scarto 1.126 -> 3.322,
    # portieri al 30% del monte). Ordinamento buono, livelli no.
    # Quindi: il modello decide CHI vale dentro il ruolo, la colonna FVM decide
    # QUANTO va a ogni ruolo. E' una rinuncia dichiarata, non un pareggio: sul
    # riparto fra reparti il tool ha sbagliato in ogni configurazione provata.
    quote = split_ruolo(
        {r: [g['fvm'] for g in G if g['ruolo'] == r and g.get('fvm') and g['nome'] not in fuori]
         for r in SLOT})
    if quote:
        massa = sum(g['prezzo'] for g in disponibili)
        for r in SLOT:
            nel_ruolo = [g for g in disponibili if g['ruolo'] == r]
            s_r = sum(g['prezzo'] for g in nel_ruolo)
            obiettivo = quote[r] / (BUDGET * SQUADRE) * massa
            # Si riscala solo la parte discrezionale: il credito di base resta.
            k = ((obiettivo - len(nel_ruolo)) / (s_r - len(nel_ruolo))
                 if s_r > len(nel_ruolo) and obiettivo > len(nel_ruolo) else 1.0)
            for g in nel_ruolo:
                g['prezzo'] = 1.0 + (g['prezzo'] - 1.0) * k
                g['scarto'] = g['prezzo'] - g['quota_scalata']
        dati['riparto'] = 'FVM'

    dati['discrezionale'] = discrezionale
    dati['scala_quotazioni'] = scala
    return dati


# ------------------------------------------------------------------ ASTA LIVE

def mercato(dati, asta):
    """Il mercato sta pagando SOPRA o SOTTO il valore? E' la lettura piu' utile
    che si possa avere in mano a meta' asta, e nessun listone statico te la da'.

    Il pavimento di sostituzione non si muove quando i giocatori vengono venduti
    (l'indice scala insieme ai venduti): quindi cio' che cambia i prezzi residui
    e' solo quanto BUDGET e' uscito rispetto a quanto VALORE e' uscito.

      indice > 1  gli avversari stanno strapagando -> restano meno crediti in
                  circolo -> tutto il resto costera' MENO: il tuo potere
                  d'acquisto e' cresciuto senza che tu abbia fatto niente.
      indice < 1  stanno comprando a sconto -> il mercato si sta portando via
                  valore a poco prezzo, e per te resta piu' concorrenza sui
                  crediti: alza i limiti o rimani senza.

    Restituisce indice=None se non c'e' ancora niente da misurare: un indice
    inventato su zero vendite sarebbe peggio di nessun indice.
    """
    venduti = asta.stato.get('venduti', [])
    if not venduti:
        return {'indice': None, 'motivo': 'nessuna vendita ancora registrata',
                'valore_uscito': 0.0, 'budget_uscito': 0.0, 'scarto': 0.0, 'n': 0}

    # Prezzi teorici del mercato PRIMA di qualunque vendita: e' il metro.
    base = {'giocatori': [dict(g) for g in dati['giocatori']]}
    for g in base['giocatori']:
        g.pop('venduto', None)
    vorp(base)
    prezzi(base)
    teorico = {g['nome'].lower(): (g['prezzo'] or 1.0) for g in base['giocatori']}

    valore_uscito = sum(teorico.get(v['nome'].lower(), 1.0) for v in venduti)
    budget_uscito = float(sum(v['prezzo'] for v in venduti))
    indice = budget_uscito / valore_uscito if valore_uscito > 0 else None
    return {'indice': indice,
            'valore_uscito': valore_uscito,
            'budget_uscito': budget_uscito,
            'scarto': budget_uscito - valore_uscito,
            'n': len(venduti),
            'motivo': None}


class Asta:
    """Stato dell'asta su file JSON. Lo aggiorni tu dopo ogni assegnazione.

    Non prova a indovinare niente dai silenzi: un'asta che il tool crede di
    conoscere e non conosce e' peggio di un foglio di carta.
    """

    def __init__(self, path):
        self.path = path
        self.stato = {'venduti': [], 'mio_budget': BUDGET, 'miei': []}
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                self.stato = json.load(f)

    def salva(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.stato, f, ensure_ascii=False, indent=1)

    def registra(self, nome, prezzo, mio=False):
        self.stato['venduti'].append({'nome': nome, 'prezzo': prezzo, 'mio': mio})
        if mio:
            self.stato['miei'].append({'nome': nome, 'prezzo': prezzo})
            self.stato['mio_budget'] -= prezzo
        self.salva()

    def applica(self, dati):
        """Marca i venduti e ricalcola il contesto residuo della lega."""
        venduti = {v['nome'].lower(): v for v in self.stato['venduti']}
        presi_ruolo = {r: 0 for r in SLOT}
        speso_lega = 0.0
        for g in dati['giocatori']:
            v = venduti.get(g['nome'].lower())
            if v:
                g['venduto'] = True
                g['prezzo_reale'] = v['prezzo']
                presi_ruolo[g['ruolo']] += 1
                speso_lega += v['prezzo']

        slot_residui = sum(SLOT.values()) * SQUADRE - len(self.stato['venduti'])
        budget_residuo = BUDGET * SQUADRE - speso_lega
        return presi_ruolo, budget_residuo, slot_residui

    def miei_slot_residui(self, dati):
        """Quanti giocatori mi mancano per ruolo: senza questo il budget
        residuo non dice niente."""
        miei = {m['nome'].lower() for m in self.stato['miei']}
        per_ruolo = {r: 0 for r in SLOT}
        for g in dati['giocatori']:
            if g['nome'].lower() in miei:
                per_ruolo[g['ruolo']] += 1
        return {r: SLOT[r] - per_ruolo[r] for r in SLOT}


# ------------------------------------------------------------------ OUTPUT

RUOLO_NOME = {'P': 'PORTIERI', 'D': 'DIFENSORI', 'C': 'CENTROCAMPISTI', 'A': 'ATTACCANTI'}


def stampa_listone(dati, ruolo=None, limite=25):
    G = [g for g in dati['giocatori'] if g.get('prezzo') is not None]
    ruoli = [ruolo] if ruolo else ['P', 'D', 'C', 'A']

    for r in ruoli:
        lista = sorted((g for g in G if g['ruolo'] == r),
                       key=lambda x: -x.get('vorp', 0))[:limite]
        if not lista:
            continue
        soglia = dati.get('soglie', {}).get(r)
        print(f'\n=== {RUOLO_NOME[r]} ===')
        if soglia is not None:
            print(f'    pavimento di sostituzione: {soglia:.0f} punti attesi '
                  f'({dati.get("residui", {}).get(r, 0)} slot ancora da riempire nella lega)')
        print(f'    {"giocatore":<22s}{"squadra":<12s}{"limite":>8s}{"mercato":>8s}{"scarto":>8s}')
        for g in lista:
            sc = g.get('scarto', 0.0)
            segno = '+' if sc > 0 else ''
            print(f'    {g["nome"][:21]:<22s}{g["squadra"][:11]:<12s}'
                  f'{g["prezzo"]:>8.0f}{g.get("quota_scalata", g["quota"]):>8.0f}'
                  f'{segno + format(sc, ".0f"):>8s}')


def stampa_occasioni(dati, n=15):
    """Dove il tuo prezzo limite supera di piu' la quotazione ufficiale: e' li'
    che il mercato sbaglia (o che sbagli tu - lo scarto va guardato, non subito)."""
    G = [g for g in dati['giocatori']
         if g.get('prezzo') is not None and g.get('vorp', 0) > 0]
    top = sorted(G, key=lambda x: -x.get('scarto', 0))[:n]
    print('\n=== DOVE VALE LA PENA ALZARE (limite molto sopra la quotazione) ===')
    for g in top:
        print(f'    {g["ruolo"]}  {g["nome"][:24]:<25s}{g["squadra"][:11]:<12s}'
              f'limite {g["prezzo"]:>4.0f}  mercato {g.get("quota_scalata", g["quota"]):>4.0f}  '
              f'scarto +{g.get("scarto", 0):.0f}')

    bassi = sorted((g for g in G if g.get('scarto', 0) < 0),
                   key=lambda x: x.get('scarto', 0))[:n]
    if bassi:
        print('\n=== DOVE LASCIAR PERDERE (il mercato chiede piu di quanto valga) ===')
        for g in bassi:
            print(f'    {g["ruolo"]}  {g["nome"][:24]:<25s}{g["squadra"][:11]:<12s}'
                  f'limite {g["prezzo"]:>4.0f}  mercato {g.get("quota_scalata", g["quota"]):>4.0f}  '
                  f'scarto {g.get("scarto", 0):.0f}')


def split_ruolo(valori, normalizza=True):
    """{ruolo: crediti} sui SOLI giocatori che la lega compra davvero.

    `valori` = {ruolo: [numeri]}. Si prendono i migliori SLOT[r]*SQUADRE per
    ruolo - 250 in una lega standard, non tutti i 503 del listone - perche' e'
    l'unico universo su cui due scale diverse sono confrontabili.
    """
    per_ruolo = {r: sum(sorted(valori.get(r, []), reverse=True)[:SLOT[r] * SQUADRE])
                 for r in SLOT}
    tot = sum(per_ruolo.values())
    if not tot:
        return None
    if not normalizza:
        return per_ruolo
    return {r: v / tot * BUDGET * SQUADRE for r, v in per_ruolo.items()}


def calibra(dati, pesi=(0.0, 0.35, 1.0)):
    """PESO_PANCHINA e' tarato o inventato? Il listone contiene gia' la risposta.

    La colonna FVM e' la stima del prezzo d'asta di Fantacalcio.it: consenso di
    mercato, **non prezzi pagati** - va letta per quello che e'. Ma e' l'unica
    ancora esterna disponibile, e trasforma PESO_PANCHINA da parametro libero
    (una mia stima che muove i prezzi del 55%) nell'incognita di un'equazione:
    quale valore riproduce lo split di budget che il mercato si aspetta.

    Non dice chi ha ragione. Dice QUANTO il modello si allontana dal consenso,
    che finora era un'impressione scritta nel README.
    """
    global PESO_PANCHINA
    G = dati['giocatori']
    rif = split_ruolo({r: [g['fvm'] for g in G if g['ruolo'] == r and g.get('fvm')]
                       for r in SLOT})
    if rif is None:
        raise DatoMancante(
            'per calibrare serve la colonna FVM nel file quotazioni.\n'
            "   Il listone ufficiale di fantacalcio.it ce l'ha; l'esempio no.")

    memoria = PESO_PANCHINA

    def modello(peso):
        global PESO_PANCHINA
        PESO_PANCHINA = peso
        prezzi(vorp(dati))
        return split_ruolo({r: [g['prezzo'] for g in G
                                if g['ruolo'] == r and g.get('prezzo')] for r in SLOT})

    try:
        colonne = [(f'{p:.2f}', modello(p)) for p in pesi]
        # scarto L1 dal mercato su una griglia fitta: 21 passaggi, costo nullo
        griglia = [(sum(abs(modello(i / 20.0)[r] - rif[r]) for r in SLOT), i / 20.0)
                   for i in range(21)]
    finally:
        PESO_PANCHINA = memoria
        prezzi(vorp(dati))

    scarto_min, peso_ott = min(griglia)
    print('\n=== CALIBRAZIONE DI --peso-panchina CONTRO IL MERCATO ===')
    print(f'    riferimento: colonna FVM (fantacalcio.it) sui {sum(SLOT.values()) * SQUADRE} '
          f'giocatori che la lega compra,')
    print(f'    riscalata su {BUDGET * SQUADRE} crediti. E consenso di mercato, NON prezzi pagati.')
    print(f'\n    {"ruolo":<8}{"FVM":>10}' + ''.join(f'{p:>10}' for p, _ in colonne))
    for r in ['P', 'D', 'C', 'A']:
        print(f'    {RUOLO_NOME[r][:7]:<8}{rif[r]:>10.0f}'
              + ''.join(f'{c[r]:>10.0f}' for _, c in colonne))
    print(f'    {"scarto":<8}{"-":>10}'
          + ''.join(f'{sum(abs(c[r] - rif[r]) for r in SLOT):>10.0f}' for _, c in colonne))
    print(f'\n    peso che minimizza lo scarto dal mercato: {peso_ott:.2f}  '
          f'(scarto residuo {scarto_min:.0f} crediti su {BUDGET * SQUADRE})')
    print(f'    in uso oggi: {memoria:.2f}')

    # Da dove viene lo scarto: il pavimento e' in PUNTI TOTALI (fm x presenze),
    # e le presenze di una riserva dell'anno scorso non dicono quanto vale, solo
    # che non ha giocato. Stampare le due componenti separate e' l'unica cosa che
    # ha impedito di correggere il parametro sbagliato per la terza volta.
    print(f'\n    composizione del pavimento (peso {memoria:.2f}) - il crollo e nelle PRESENZE:')
    print(f'    {"ruolo":<8}{"rango":>7}{"punti":>9}{"fm":>7}{"presenze":>10}')
    for r in ['P', 'D', 'C', 'A']:
        disp = sorted((g for g in dati['giocatori'] if g['ruolo'] == r),
                      key=lambda x: -x['punti'])
        tit = TITOLARI.get(r, SLOT[r]) * SQUADRE
        idx = min(int(round(tit + memoria * (SLOT[r] * SQUADRE - tit))), len(disp)) - 1
        g = disp[max(idx, 0)]
        pres = g.get('pres_attese') or 0
        print(f'    {RUOLO_NOME[r][:7]:<8}{idx + 1:>7}{g["punti"]:>9.0f}'
              f'{(g["punti"] / pres if pres else 0):>7.2f}{pres:>10.1f}')
    if abs(peso_ott - memoria) > 0.1:
        print('    -> il default NON riproduce lo split di mercato. Prima di fidarti di un\n'
              '       prezzo, gira il tool con entrambi i valori e guarda quanto si muove.')
    return {'fvm': rif, 'peso_ottimo': peso_ott, 'scarto': scarto_min}


def stampa_intestazione(dati):
    n = len(dati['giocatori'])
    print('=' * 74)
    print(f'  fanta-asta  |  {SQUADRE} squadre x {BUDGET} crediti = '
          f'{SQUADRE * BUDGET} sul mercato  |  {sum(SLOT.values())} slot a rosa')
    print('=' * 74)
    print(f'  giocatori letti: {n}   scartati: {dati["scartate"]}')
    if dati['ha_storico']:
        print(f'  base del valore: STORICO ({dati["con_storico"]}/{n} con fantamedia), '
              f'regressione verso la media di ruolo')
    else:
        print('  !! base del valore: QUOTAZIONE UFFICIALE (nessuno storico nel file)')
        print('     Senza statistiche il tool non ha una stima indipendente, quindi')
        print('     NON riscrive la graduatoria: l ordine dentro ogni ruolo resta')
        print('     quello del mercato. Lo "scarto" qui sotto NON e un occasione di')
        print('     rendimento ("rendera piu di quanto credono"), e una indicazione')
        print('     di ALLOCAZIONE ("concentra piu crediti in alto, perche i')
        print('     giocatori sopra il pavimento sono gli unici che compri davvero").')
        print('     Per le occasioni vere servono le colonne Fantamedia e Presenze.')


# ------------------------------------------------------------------ CLI

def main():
    global SQUADRE, BUDGET, SLOT, PESO_PANCHINA
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--quot', required=True, help='file quotazioni (.xlsx o .csv)')
    ap.add_argument('--squadre', type=int, default=10)
    ap.add_argument('--budget', type=int, default=500)
    ap.add_argument('--slot', default=None,
                    help='slot rosa, es. "3,8,8,6" per P,D,C,A')
    ap.add_argument('--peso-panchina', type=float, default=None,
                    help='0.0 = pavimento sui soli titolari (severo) · '
                         '1.0 = sugli slot totali (comportamento pre-fix). '
                         f'Default {PESO_PANCHINA}. Cambia molto i prezzi: provalo.')
    ap.add_argument('--titolari', default='titolari.csv',
                    help='XI di riferimento da formazioni.py (default: titolari.csv, '
                         'ignorato se non esiste)')
    ap.add_argument('--calibra', action='store_true',
                    help='confronta lo split di budget per ruolo con la colonna FVM '
                         'e cerca il --peso-panchina che riproduce il mercato')
    ap.add_argument('--ruolo', choices=list(SLOT), default=None)
    ap.add_argument('--top', type=int, default=25)
    ap.add_argument('--avanzate', nargs='?', const='statistiche_avanzate.csv',
                    default=None,
                    help='usa npxG/xA al posto di gol/assist realizzati '
                         '(default: statistiche_avanzate.csv)')
    ap.add_argument('--live', default=None, help='file JSON di stato asta')
    ap.add_argument('--compra', nargs=2, metavar=('NOME', 'PREZZO'),
                    help='registra un acquisto MIO (richiede --live)')
    ap.add_argument('--venduto', nargs=2, metavar=('NOME', 'PREZZO'),
                    help='registra un acquisto di un AVVERSARIO (richiede --live)')
    A = ap.parse_args()

    SQUADRE, BUDGET = A.squadre, A.budget
    if A.peso_panchina is not None:
        if not 0.0 <= A.peso_panchina <= 1.0:
            raise SystemExit('--peso-panchina deve stare fra 0.0 e 1.0')
        PESO_PANCHINA = A.peso_panchina
    if A.slot:
        v = [int(x) for x in A.slot.split(',')]
        if len(v) != 4:
            raise SystemExit('--slot vuole 4 numeri: P,D,C,A')
        SLOT = dict(zip(['P', 'D', 'C', 'A'], v))

    try:
        dati = carica(A.quot)
    except DatoMancante as e:
        raise SystemExit(f'\n[!] {e}\n')

    stampa_intestazione(dati)

    if A.avanzate:
        if not os.path.exists(A.avanzate):
            raise SystemExit(f'\n[!] file dati avanzati non trovato: {A.avanzate}\n')
        _, esito = applica_avanzate(dati, A.avanzate)
        if esito.get('errore'):
            print(f'  !! dati avanzati non applicati: {esito["errore"]}')
        else:
            tot = len(dati['giocatori'])
            print(f'  dati avanzati: npxG/xA applicati a {esito["corretti"]}/{tot} '
                  f'giocatori (fonte: {esito["totale_av"]} record)')
            if esito['ambigui']:
                print(f'     {len(esito["ambigui"])} NON accoppiati per ambiguita '
                      f'(omonimi): restano sulla fantamedia grezza, non indovinati')
                for n, m in esito['ambigui'][:5]:
                    print(f'       - {n}  [{m}]')

        _, ctx = applica_contesto_squadra(dati)
        if ctx.get('errore'):
            print(f'  !! contesto squadra non applicato: {ctx["errore"]}')
        else:
            print(f'  contesto squadra: forza difensiva applicata a '
                  f'{ctx["corretti"]} portieri')
            if ctx['senza_dato']:
                print(f'     {len(ctx["senza_dato"])} portieri di neopromosse '
                      f'senza dato difensivo: non corretti, dichiarati')

    import formazioni
    reg = formazioni.carica(A.titolari)
    titolari = None
    if reg:
        titolari = reg['titolari']
        noti = {g['nome'].strip().lower() for g in dati['giocatori']}
        persi = len(titolari - noti)
        eta = reg['giorni']
        print(f'  titolarita: OSSERVATA da {A.titolari} - {reg["n"]} titolari, '
              f'{reg["squadre"]}/20 squadre, {len(titolari & noti)} accoppiati'
              + (f', {persi} NON nel listone' if persi else ''))
        if eta > 3:
            print(f'  !! l XI ha {eta} giorni: le formazioni cambiano ogni giorno. '
                  f'Rilancia  python formazioni.py')
    else:
        print(f'  titolarita: DEDOTTA da presenze storiche e quotazione '
              f'({A.titolari} assente). E il difetto n.1 del tool:')
        print(f'     lancia  python formazioni.py  per sostituirla col dato osservato.')

    valuta(dati, titolari=titolari)

    if A.calibra:
        try:
            calibra(dati)
        except DatoMancante as e:
            raise SystemExit(f'\n[!] {e}\n')
        print()
        return

    if A.live:
        asta = Asta(A.live)
        if A.compra:
            asta.registra(A.compra[0], float(A.compra[1]), mio=True)
            print(f'\n  registrato MIO: {A.compra[0]} a {A.compra[1]}')
        if A.venduto:
            asta.registra(A.venduto[0], float(A.venduto[1]), mio=False)
            print(f'\n  registrato: {A.venduto[0]} a {A.venduto[1]} (avversario)')

        presi, budget_res, slot_res = asta.applica(dati)
        vorp(dati, presi=presi)
        prezzi(dati, budget_disponibile=budget_res, slot_residui=slot_res)

        miei_res = asta.miei_slot_residui(dati)
        mio_budget = asta.stato['mio_budget']
        da_riempire = sum(miei_res.values())
        print(f'\n  --- IL TUO STATO ---')
        print(f'  budget residuo: {mio_budget}   slot da riempire: {da_riempire}')
        if da_riempire:
            print(f'  se spendessi 1 per ogni slot restante, ti resterebbero '
                  f'{mio_budget - da_riempire} crediti da giocare')
        print('  mancano: ' + '  '.join(f'{r}:{n}' for r, n in miei_res.items() if n > 0))
        print(f'  lega: {len(asta.stato["venduti"])} giocatori venduti, '
              f'{budget_res:.0f} crediti ancora in circolo')

        m = mercato(dati, asta)
        if m['indice'] is None:
            print(f'  termometro del mercato: -- ({m["motivo"]})')
        else:
            if m['indice'] > 1.05:
                verso = ('CARO: gli avversari stanno strapagando. Hanno bruciato '
                         f'{m["scarto"]:.0f} crediti sopra il valore.\n'
                         '     -> il resto del listone costera MENO del previsto: '
                         'aspetta e prendi valore a sconto.')
            elif m['indice'] < 0.95:
                verso = ('A SCONTO: stanno comprando valore per poco.\n'
                         '     -> restera piu concorrenza sui crediti: alza i limiti '
                         'o rimani con la rosa peggiore.')
            else:
                verso = 'IN LINEA col modello: i tuoi limiti valgono cosi come sono.'
            print(f'  termometro del mercato: {m["indice"]:.2f}x  {verso}')
    else:
        vorp(dati)
        prezzi(dati)

    stampa_listone(dati, ruolo=A.ruolo, limite=A.top)
    if dati['ha_storico']:
        stampa_occasioni(dati)
    print()


if __name__ == '__main__':
    main()
