# -*- coding: utf-8 -*-
"""nomi - una chiave sola per giocatori e squadre, qualunque file li scriva.

Il listone scrive 'MIL', le probabili formazioni 'Milan', Understat 'AC Milan',
il calendario magari 'A.C. Milan'. Se ogni modulo normalizza a modo suo, i
join falliscono in silenzio e il Milan gioca contro nessuno. Qui si decide una
volta.

Le squadre sconosciute (le finte dei test, le neopromosse di domani) tengono il
nome normalizzato intero: troncarle alle prime tre lettere farebbe di 'Team01'
e 'Team02' la stessa squadra.
"""
from analisi import norm

# sigla -> parola che identifica il club nel nome esteso
CLUB = {
    'ATA': 'atalanta', 'BOL': 'bologna', 'CAG': 'cagliari', 'COM': 'como',
    'CRE': 'cremonese', 'EMP': 'empoli', 'FIO': 'fiorentina', 'FRO': 'frosinone',
    'GEN': 'genoa', 'INT': 'inter', 'JUV': 'juventus', 'LAZ': 'lazio',
    'LEC': 'lecce', 'MIL': 'milan', 'MON': 'monza', 'NAP': 'napoli',
    'PAR': 'parma', 'PIS': 'pisa', 'ROM': 'roma', 'SAL': 'salernitana',
    'SAM': 'sampdoria', 'SAS': 'sassuolo', 'SPE': 'spezia', 'TOR': 'torino',
    'UDI': 'udinese', 'VEN': 'venezia', 'VER': 'verona', 'PAL': 'palermo',
    'BAR': 'bari', 'CES': 'cesena', 'SPA': 'spal', 'BRE': 'brescia',
}
ALIAS = {'internazionale': 'INT', 'hellas': 'VER', 'juve': 'JUV'}


def squadra(s):
    """'AC Milan' / 'Milan' / 'MIL' -> 'MIL'. Sconosciuta -> nome normalizzato."""
    n = norm(s)
    if n.upper() in CLUB:
        return n.upper()
    parole = n.split()
    for sigla, parola in CLUB.items():
        if parola in parole:
            return sigla
    for a, sigla in ALIAS.items():
        if a in parole:
            return sigla
    return n


def cerca(nome, chiavi):
    """Chiavi che contengono tutte le parole di `nome`, in qualunque ordine:
    'N. Gonzalez' trova 'gonzalez n'. Serve per i nomi scritti a mano (capitano,
    scambi); chi chiama decide cosa fare se i risultati sono zero o piu' d'uno."""
    k = giocatore(nome)
    if k in chiavi:
        return [k]
    parole = set(k.split())
    return [c for c in chiavi if parole and parole <= set(c.split())]


def giocatore(s):
    """'Soulé M.' -> 'soule m'. I file di Fantacalcio.it usano tutti lo stesso
    formato 'Cognome I.', quindi il join e' esatto dopo aver tolto accenti e
    punteggiatura; non si fa fuzzy matching (un accoppiamento sbagliato in
    silenzio e' peggio di un buco dichiarato)."""
    return norm(s)
