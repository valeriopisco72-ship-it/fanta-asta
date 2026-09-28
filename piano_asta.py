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
