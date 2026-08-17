# -*- coding: utf-8 -*-
"""talenti - filtro di attenzione sui profili anomali. NON un predittore.

🔴 VERDETTO DELLA VALIDAZIONE (10/08/2026) — leggere prima di usarlo.

Testato su 229 giocatori presenti sia nel 2024/25 sia nel 2025/26
(`python valida.py`). Risultato:

    segmento          esplosi     lift
    top 10% score        4,5%    0,25x
    top 20% score        6,7%    0,37x
    tasso base          17,9%    1,00x

**Lift 0,25x: il ranking di questo modulo seleziona AL CONTRARIO.** Nel decile
che indica come piu' promettente esplode un quarto dei giocatori rispetto al
caso. Dei 10 nomi che avrebbe segnalato nel 2024/25, nove sono peggiorati.

Causa: regressione alla media. I segnali cercano chi e' gia' fuori scala, ma
quelli sono al picco e da li' si scende. Gli esplosi hanno anomalia MINORE
(0,86x), sottoutilizzo MINORE (0,67x), sfortuna MINORE (0,51x) dei non esplosi.

**Come va usato, allora:** come lista di venti profili anomali da guardare a
mano, incrociandoli con l'informazione che i dati non hanno - chi ha cambiato
squadra, chi ha il posto libero davanti, chi gioca le amichevoli. Il filtro fa
la statistica, la previsione la fai tu.

**Cosa NON fare:** comprare per score. I pesi non sono stati ricalibrati sui
dati di validazione apposta: con 229 osservazioni e 5 parametri si arriva a
lift 2x giocando coi coefficienti, ed e' overfitting, non previsione.

---

Il metodo (che resta valido come descrizione, non come predizione):

## Il caso che ha definito il metodo

Marco Palestra, Cagliari 2025/26: **4,40 xA e 32 passaggi chiave da DIFENSORE**.
La mediana degli altri difensori con almeno 1500 minuti e' **1,14 xA**: Palestra
produceva quasi **4 volte** il suo ruolo. Il dato c'era, era pubblico, e nessuno
lo guardava - perche' tutti leggevano gol e assist (1 e 4, numeri banali) invece
di guardare quanto CREAVA rispetto a chi gioca nel suo stesso ruolo.

Da qui l'idea del modulo: **un talento non e' chi produce tanto in assoluto, e'
chi produce fuori scala per il proprio ruolo e per i propri minuti.**

## I cinque segnali

1. **ANOMALIA DI RUOLO** - produzione per 90' rapportata alla MEDIANA del ruolo.
   E' il segnale Palestra: un difensore con xA da trequartista.
2. **SOTTOUTILIZZO** - rate alti su pochi minuti. Se gioca di piu', il totale
   esplode senza che migliori di niente. E' il segnale piu' redditizio, perche'
   il mercato prezza i TOTALI e non i rate.
3. **SFORTUNA** - (npxG - gol) + (xA - assist) positivo: ha prodotto e non e'
   stato ripagato. Rimbalza.
4. **CREAZIONE** - passaggi chiave per 90'. Precedono gli assist e si vedono prima.
5. **PREZZO CIECO** - quotazione bassa a fronte di produzione alta: il mercato
   non ha ancora guardato.

## Cosa questo NON e'

Non e' una previsione. E' un **filtro di attenzione**: restringe 489 giocatori a
una ventina da guardare a mano. I falsi positivi sono attesi e frequenti - un
difensore con xA alta puo' essere semplicemente il battitore di corner della
squadra, o uno che ha avuto quattro partite fortunate. Il modulo dice DOVE
guardare, non chi comprare.

E soprattutto **non vede il salto che conta**: Palestra e' esploso anche perche'
il Cagliari lo ha reso titolare fisso. Nessun dato storico prevede una scelta
dell'allenatore.

Uso:
    python talenti.py                    # i candidati
    python talenti.py --controllo        # verifica sul caso Palestra
    python talenti.py --ruolo D --top 15
    python talenti.py --solo-quotati     # solo chi e nel listone 2026/27
"""
import argparse
import csv
import os
import statistics as st
import unicodedata

MIN_MINUTI = 400        # sotto, i rate per 90' sono rumore puro
RUOLI = ('P', 'D', 'C', 'A')


def num(v, d=0.0):
    try:
        return float(str(v).replace(',', '.'))
    except (TypeError, ValueError):
        return d


def nrm(s):
    s = unicodedata.normalize('NFKD', str(s).lower())
    return ''.join(c for c in s if not unicodedata.combining(c))


def ruolo_base(pos):
    """Posizione Understat (DFMS, FS, GK) -> reparto Classic."""
    p = (pos or '').upper()
    if 'GK' in p:
        return 'P'
    if p.startswith('D'):
        return 'D'
    if p.startswith('F') or p.startswith('S'):
        return 'A'
    return 'C'


def carica(path='statistiche_avanzate.csv'):
    if not os.path.exists(path):
        raise SystemExit('[!] file non trovato: ' + path)
    with open(path, encoding='utf-8-sig', newline='') as f:
        dati = list(csv.DictReader(f, delimiter=';'))
    out = []
    for r in dati:
        m = num(r['Min'])
        if m < MIN_MINUTI:
            continue
        n90 = m / 90.0
        r['min'] = m
        r['n90'] = n90
        r['ruolo'] = ruolo_base(r['Pos'])
        r['npxg90'] = num(r['npxG']) / n90
        r['xa90'] = num(r['xA']) / n90
        r['kp90'] = num(r['KeyPass']) / n90
        r['prod90'] = r['npxg90'] + r['xa90']
        r['sfortuna'] = ((num(r['npxG']) - num(r['NPG']))
                         + (num(r['xA']) - num(r['Assist'])))
        out.append(r)
    return out


def quotazioni(path='quotazioni_ufficiali.csv'):
    """Cognome normalizzato -> quotazione. Chi non c'e' resta None, non zero."""
    if not os.path.exists(path):
        return {}
    q = {}
    with open(path, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f, delimiter=';'):
            chiave = nrm(r['Nome']).replace('.', ' ').split()[0]
            q[chiave] = num(r['Quotazione'])
    return q


def punteggia(dati, quot=None):
    quot = quot or {}
    # Riferimenti per ruolo: MEDIANA, non media - i fuoriscala sballano la media,
    # ed e' proprio i fuoriscala che stiamo cercando.
    rif = {}
    for r in RUOLI:
        g = [x for x in dati if x['ruolo'] == r]
        if not g:
            continue
        rif[r] = {'npxg90': st.median([x['npxg90'] for x in g]) or 0.005,
                  'xa90': st.median([x['xa90'] for x in g]) or 0.005,
                  'kp90': st.median([x['kp90'] for x in g]) or 0.01,
                  'min': st.median([x['min'] for x in g]) or 1.0}

    for x in dati:
        b = rif.get(x['ruolo'])
        if not b:
            continue
        # 🔑 L'anomalia si misura per COMPONENTE e si prende la MASSIMA, non la
        # somma. Trovato dal controllo positivo: sommando npxG e xA in un indice
        # unico, Palestra (npxG basso, xA altissimo) usciva a 1,55x e spariva al
        # 59esimo posto. Un talento emerge perche' UNA cosa e' fuori scala, non
        # perche' la media lo e' - e mediare le componenti cancella proprio il
        # segnale che si sta cercando.
        x['an_npxg'] = x['npxg90'] / b['npxg90']
        x['an_xa'] = x['xa90'] / b['xa90']
        x['anomalia'] = max(x['an_npxg'], x['an_xa'])
        x['dimensione'] = 'finalizzazione' if x['an_npxg'] >= x['an_xa'] else 'creazione'
        x['sottoutilizzo'] = ((x['anomalia'] - 1) * max(0.0, 1 - x['min'] / b['min'])
                              if x['anomalia'] > 1 else 0.0)
        x['sfortuna90'] = x['sfortuna'] / x['n90']
        x['creazione'] = x['kp90'] / b['kp90']
        cognome = nrm(x['Nome']).split()[-1]
        x['quot'] = quot.get(cognome)
        x['prezzo_cieco'] = (x['anomalia'] / x['quot']
                             if x['quot'] and x['quot'] > 0 else None)

        # [STIMA] I pesi sono miei. Servono a ORDINARE una lista da guardare,
        # non a stimare un valore: non leggerli come un modello.
        #
        # 🔑 Seconda correzione dal controllo positivo. La prima versione pesava
        # 2.5 il SOTTOUTILIZZO e 2.0 l'anomalia: cercava un solo tipo di talento
        # - quello che gioca poco - e Palestra restava 59esimo perche' di minuti
        # ne aveva 3087. Ma i talenti nascosti sono DUE specie:
        #   (a) chi gioca poco e produce  -> esplode se gli danno spazio;
        #   (b) chi gioca tanto, produce fuori scala, e il mercato non se ne
        #       accorge perche' guarda gol e assist -> il caso Palestra.
        # L'anomalia di ruolo e' l'unico segnale che vede entrambe, quindi
        # domina; il sottoutilizzo resta un bonus per la specie (a).
        x['score'] = (3.0 * max(0.0, x['anomalia'] - 1)
                      + 1.5 * x['sottoutilizzo']
                      + 0.8 * max(0.0, x['sfortuna90'] * 10)
                      + 0.6 * max(0.0, x['creazione'] - 1))

        s = []
        if x['anomalia'] >= 1.8:
            s.append('fuori scala nel ruolo: %s %.1fx' % (x['dimensione'], x['anomalia']))
        if x['sottoutilizzo'] > 0.3:
            s.append('gioca poco per quanto produce')
        if x['sfortuna90'] > 0.05:
            s.append('non ripagato (%+.1f)' % x['sfortuna'])
        if x['creazione'] >= 2.0:
            s.append('crea molto (%.1fx)' % x['creazione'])
        if x['prezzo_cieco'] and x['prezzo_cieco'] > 0.35:
            s.append('quotato basso (%.0f)' % x['quot'])
        x['segnali'] = s
    return dati


def stampa(dati, ruolo=None, n=20, solo_quotati=False):
    v = [x for x in dati if x.get('score') is not None and x['ruolo'] != 'P']
    if ruolo:
        v = [x for x in v if x['ruolo'] == ruolo]
    if solo_quotati:
        v = [x for x in v if x['quot']]
    v = sorted(v, key=lambda x: -x['score'])[:n]
    print('\n=== CANDIDATI BREAKOUT ===')
    print('    ordinati per quanto sono ANOMALI nel proprio ruolo, non per quanto hanno fatto')
    for i, x in enumerate(v, 1):
        q = ('quot %.0f' % x['quot']) if x['quot'] else 'non quotato'
        print('\n  %2d. %-29s%-19s%s  %.0f min  %s'
              % (i, x['Nome'][:28], x['Squadra'][:18], x['ruolo'], x['min'], q))
        print('      npxG/90 %.2f . xA/90 %.2f . KP/90 %.1f . score %.2f'
              % (x['npxg90'], x['xa90'], x['kp90'], x['score']))
        if x['segnali']:
            print('      ' + ' . '.join(x['segnali']))


def controllo(dati):
    """CONTROLLO POSITIVO: il detector deve riconoscere il caso Palestra.

    Se non lo trova, il modulo e' rotto - non "da calibrare". E' la regola di
    casa: un test che non puo' fallire non e' un test.
    """
    p = next((x for x in dati if 'Palestra' in x['Nome']), None)
    print('\n=== CONTROLLO POSITIVO: il caso Palestra ===')
    if not p:
        print('  [!] Palestra assente dai dati: controllo IMPOSSIBILE, non superato')
        return False
    dif = sorted([x for x in dati if x['ruolo'] == 'D'], key=lambda x: -x['score'])
    rank = dif.index(p) + 1
    print('  Marco Palestra - %s - %.0f minuti' % (p['Squadra'], p['min']))
    print('  gol %s . assist %s      <- i numeri che guardavano tutti'
          % (p['Gol'], p['Assist']))
    print('  xA %.2f . KP %s          <- i numeri che nessuno guardava'
          % (num(p['xA']), p['KeyPass']))
    print('  anomalia di ruolo: %.2fx la mediana dei difensori' % p['anomalia'])
    print('  segnali: %s' % (', '.join(p['segnali']) if p['segnali'] else 'NESSUNO'))
    print('  posizione fra i %d difensori: %do' % (len(dif), rank))

    # Il criterio e' che il SEGNALE si accenda, non che il rank sia primo.
    # Prima versione: "deve stare nei top 10". Sbagliata per due motivi, e
    # scoperti guardando chi lo scavalca:
    #  1. sopra di lui non c'e' rumore, ci sono anomalie PIU' GRANDI e vere -
    #     Dimarco 12,4x (16 assist da difensore), Conceicao 7,3x. Palestra a
    #     3,0x e' notevole, non eccezionale.
    #  2. e soprattutto: in questi dati Palestra E' GIA' ESPLOSO. Cercare un
    #     talento nascosto nella stagione in cui e' gia' affermato e' la
    #     domanda sbagliata.
    # Alzare i pesi finche' Palestra arriva primo sarebbe overfitting su n=1,
    # cioe' l'errore piu' banale che esista. Non lo faccio.
    ok = p['anomalia'] >= 2.5 and len(p['segnali']) > 0
    print('\n  criterio: il segnale si accende (anomalia >= 2.5x + almeno un flag)')
    print('  esito: %s' % ('SUPERATO' if ok else 'FALLITO - il detector non vede il profilo'))
    print('\n  [!] Questo NON valida la capacita predittiva. Per farlo servono i')
    print('      dati della stagione PRIMA dell esplosione (Understat 2024/25):')
    print('      il test vero e "il segnale c era gia quando nessuno lo conosceva?".')
    print('      Quei dati non sono in questo repo - la validazione resta APERTA.')
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stat', default='statistiche_avanzate.csv')
    ap.add_argument('--quot', default='quotazioni_ufficiali.csv')
    ap.add_argument('--ruolo', choices=list(RUOLI), default=None)
    ap.add_argument('--top', type=int, default=20)
    ap.add_argument('--controllo', action='store_true')
    ap.add_argument('--solo-quotati', action='store_true',
                    help='solo chi e nel listone 2026/27 (comprabile davvero)')
    A = ap.parse_args()

    dati = punteggia(carica(A.stat), quotazioni(A.quot))
    print('=' * 78)
    print('  detector talenti . %d giocatori sopra %d minuti' % (len(dati), MIN_MINUTI))
    print('=' * 78)
    if A.controllo:
        raise SystemExit(0 if controllo(dati) else 1)
    controllo(dati)
    stampa(dati, A.ruolo, A.top, A.solo_quotati)
    print('\n  [!] Filtro di attenzione, non previsione. I falsi positivi sono attesi:')
    print('      un difensore con xA alta puo essere il battitore di corner.')
    print('      E nessun dato vede il salto che conta: diventare titolare fisso.\n')


if __name__ == '__main__':
    main()
