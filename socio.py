# -*- coding: utf-8 -*-
"""socio - il tuo socio di fantacalcio: dall'asta all'ultima giornata.

L'asta e' una sera; il campionato sono 38 decisioni di formazione, un paio di
finestre di mercato e una decina di scambi proposti. Questo e' il comando che
le mette insieme, con un metro solo: **quanto cambia la TUA formazione**.

    python socio.py settimana                     # il briefing del giovedi'
    python socio.py settimana --avversario "FC Beta"
    python socio.py formazione                    # solo l'undici
    python socio.py rosa                          # stato dei tuoi giocatori
    python socio.py scambio --dai "Rossi A." --ricevi "Bianchi B.,Verdi C."
    python socio.py svincolati --ruolo C
    python socio.py portieri                      # quale schierare, e con chi fare coppia
    python socio.py verifica                      # le stime ci azzeccano? backtest sui tuoi voti
    python socio.py proposte                      # scambi che convengono a te E all'altro
    python socio.py lega                          # forza di tutte le squadre, P(vittoria) prossime
    python socio.py asta --mercato                # quanto paga davvero la tua lega, giocatore per giocatore
    python socio.py --lega altra/lega.json settimana

Tutto si configura in `lega.json` (v. regole.py per le regole, e la sezione
'file' per i percorsi). Ogni dato mancante viene detto in testa all'output, e
il tool gira comunque con quello che c'e': un listone e una rosa bastano, ogni
file in piu' (voti, calendario, probabili) rende le stime migliori.

Per provarlo senza dati veri:  python esempio.py --stagione
"""
import argparse
import datetime
import os
import sys

import calendario
import fanta
import formazioni
import mercato
import nomi
import proiezioni
import regole
import schiera
import scouting
import voti

FILE_DEFAULT = {'listone': 'listone_completo.csv', 'voti': 'voti', 'calendario': 'calendario.csv',
                'rose': 'rose.csv', 'titolari': 'titolari.csv', 'squadre': 'squadre_2025-26.csv',
                'tabella': 'statistiche_rose.csv', 'prezzi': 'prezzi_lega.csv', 'scouting': 'scouting'}
XI_VECCHIO = 3   # giorni: oltre, le probabili si dichiarano vecchie


class Contesto:
    """Tutto quello che il socio sa, e la lista di cio' che NON sa."""

    def __init__(self, lega_path='lega.json', giornata=None):
        self.R = regole.carica_lega(lega_path)
        base = os.path.dirname(os.path.abspath(lega_path)) if lega_path and os.path.exists(lega_path) else '.'
        fl = dict(FILE_DEFAULT, **self.R.get('file', {}))
        self.file = {k: (v if os.path.isabs(v) else os.path.join(base, v)) for k, v in fl.items()}
        self.avvisi = []

        # listone (stagione scorsa + quotazioni)
        self.listone = []
        if os.path.exists(self.file['listone']):
            self.listone = fanta.carica(self.file['listone'])['giocatori']
        else:
            self.avvisi.append(f'listone assente ({self.file["listone"]}): niente prior dalla stagione scorsa')

        # voti della stagione in corso
        rec = voti.archivio(self.file['voti'], R=self.R)
        self.S = voti.stagione(rec) if rec else None
        # in mancanza dei voti di giornata: la tabella delle rose dell'app (MV, FM, FVMp)
        self.tabella = None
        if not self.S and os.path.exists(self.file['tabella']):
            self.tabella = mercato.carica_tabella(self.file['tabella'])
            if self.listone:
                self.avvisi.append('tabella dell app in uso: il listone non entra nelle stime')
        if not self.S and not self.tabella:
            self.avvisi.append('nessun voto di giornata: stime SOLO dal listone '
                               f'(metti i file in {self.file["voti"]}/)')

        # calendario e forza delle squadre
        self.partite = calendario.carica(self.file['calendario'])
        if self.partite:
            self.F = calendario.forze(self.partite, calendario.prior_da_squadre(self.file['squadre']))
        else:
            self.F = None
            self.avvisi.append('calendario assente: nessuna correzione per l avversario')

        # che giornata e'
        if giornata:
            self.g = giornata
        elif self.partite and calendario.prossima(self.partite):
            self.g = calendario.prossima(self.partite)
        elif self.S:
            self.g = self.S['giornate'][-1] + 1
        elif self.R.get('giornate_giocate'):
            self.g = int(self.R['giornate_giocate']) + 1
        else:
            self.g = 1

        # probabili formazioni: valgono solo per la PROSSIMA giornata
        reg = formazioni.carica(self.file['titolari'])
        self.titolari = None
        if reg:
            self.titolari = {nomi.giocatore(n) for n in reg['titolari']}
            if reg['giorni'] > XI_VECCHIO:
                self.avvisi.append(f'probabili formazioni di {reg["giorni"]} giorni fa: rilancia  '
                                   'python formazioni.py')
        else:
            self.avvisi.append('probabili formazioni assenti: la probabilita di giocare viene '
                               'dalle presenze (python formazioni.py per quelle vere)')

        # stime: la prossima giornata usa le probabili e le squalifiche; le
        # successive no (le probabili non valgono piu', la squalifica e' scontata)
        if self.tabella:
            gg = int(self.R.get('giornate_giocate') or max(self.g - 1, 1))
            self.E_ora = proiezioni.stima_app([dict(r) for r in self.tabella], gg, self.R, self.titolari)
            self.E_base = proiezioni.stima_app([dict(r) for r in self.tabella], gg, self.R, None)
            if not self.R.get('giornate_giocate'):
                self.avvisi.append(f'"giornate_giocate" non e in lega.json: assumo {gg}')
            senza_pv = [r for r in self.tabella if r.get('pv') is None]
            if senza_pv:
                mie_senza = sum(1 for r in senza_pv
                                if str(r.get('fantasquadra', '')).lower() == str(self.R.get('mia', '')).lower())
                self.avvisi.append(f'Pv mancante per {len(senza_pv)}/{len(self.tabella)} giocatori'
                                   + (f' (di cui {mie_senza} tuoi)' if mie_senza else ' (nessuno dei tuoi)')
                                   + ': presenze STIMATE dai decimali, giuste 16/17 sulle medie non tonde, '
                                   'a caso sulle tonde')
        else:
            self.E_ora = proiezioni.stima(S=self.S, listone=self.listone, titolari=self.titolari,
                                          R=self.R, prossima=True)
            self.E_base = proiezioni.stima(S=self.S, listone=self.listone, titolari=None,
                                           R=self.R, prossima=False)

        # scouting: schede qualitative in scouting/, correzione limitata e dichiarata
        self.schede, errori = scouting.carica(self.file['scouting'])
        self.avvisi += [f'scouting: {e}' for e in errori]
        if self.schede:
            oggi = datetime.date.today().isoformat()
            self.E_ora = scouting.applica(self.E_ora, self.schede, oggi, self.avvisi)
            self.E_base = scouting.applica(self.E_base, self.schede, oggi, [])

        # rose della lega
        self.rose = mercato.carica_rose(self.file['rose'])
        self.mia_nome = self.R.get('mia')
        self.mia = self._rosa_di(self.mia_nome) if self.mia_nome else None
        if self.rose and not self.mia:
            self.avvisi.append(f'la tua squadra ("mia" in lega.json) non e in {self.file["rose"]}: '
                               f'squadre trovate {", ".join(self.rose)}')
        if not self.rose:
            self.avvisi.append(f'rose assenti ({self.file["rose"]}): servono per formazione e mercato')
        cap = self.R.get('capitano') or {}
        if cap.get('attivo') and self.mia:
            for campo, dest in (('giocatore', 'k'), ('vice', 'kv')):
                if not cap.get(campo) or cap.get(dest):
                    continue
                trovati = nomi.cerca(cap[campo], self.mia)
                if len(trovati) == 1:
                    cap[dest] = trovati[0]
                else:
                    self.avvisi.append(
                        f'{"capitano" if dest == "k" else "vice"} "{cap[campo]}" '
                        + ('non e nella tua rosa' if not trovati else f'ambiguo: {", ".join(trovati)}')
                        + ': fattore capitano non applicato per lui')
        if self.mia:
            ignoti = [k for k in self.mia if k not in self.E_base]
            if ignoti:
                self.avvisi.append(f'{len(ignoti)} giocatori della tua rosa non sono in nessun file: '
                                   + ', '.join(ignoti[:5]))

    def _nome_rosa(self):
        return next((k for k in self.rose if k.strip().lower() == str(self.mia_nome).strip().lower()), None)

    def _rosa_di(self, nome):
        for k, v in self.rose.items():
            if k.strip().lower() == str(nome).strip().lower():
                return v
        return None

    def stime_giornata(self, g, ora=None):
        """Stime corrette per l'avversario della giornata g."""
        E = self.E_ora if (ora if ora is not None else g == self.g) else self.E_base
        if not self.partite:
            return E
        return proiezioni.per_giornata(E, self.partite, self.F, g, self.R)

    def rosa(self, chiavi, E):
        return [E[k] for k in chiavi if k in E]

    def avversario_di(self, g, forzato=None):
        if forzato:
            return forzato
        cal = self.R.get('calendario_lega') or {}
        return cal.get(str(g))


# ------------------------------------------------------------------ STAMPA

def _gioc(g):
    campo = ''
    if g.get('avv'):
        campo = f'{"vs" if g["casa"] else "@"} {g["avv"][:8]}'
    note = g.get('stato', '')
    return (f'{g["nome"][:20]:<21}{g.get("squadra", "")[:8]:<9}{campo:<12}'
            f'{g["mu"]:>5.1f}{g["p"] * 100:>5.0f}%  {note}')


def intestazione(C, titolo):
    print('=' * 76)
    print(f'  {titolo} | {C.R["nome"]} | giornata {C.g} | '
          f'{"scontri diretti" if C.R["formula"] == "scontri" else "somma punti"}')
    print('=' * 76)
    fonti = []
    if C.S:
        fonti.append(f'voti giornate {C.S["giornate"][0]}-{C.S["giornate"][-1]}')
    if C.tabella:
        fonti.append(f'tabella rose dell app ({len(C.tabella)} giocatori)')
    if C.listone:
        fonti.append(f'listone ({len(C.listone)})')
    if C.F:
        fonti.append(f'calendario ({C.F["fonte"]})')
    if C.titolari is not None:
        fonti.append(f'probabili ({len(C.titolari)} titolari)')
    if C.schede:
        fonti.append(f'scouting ({len(C.schede)} schede)')
    print('  dati: ' + (' | '.join(fonti) if fonti else 'NESSUNO'))
    for a in C.avvisi:
        print(f'  !! {a}')


def allarmi(C, E):
    rosa = C.rosa(C.mia, E)
    sq = [g for g in rosa if g['stato'] == 'squalificato']
    di = [g for g in rosa if g['stato'] == 'diffidato']
    fuori = [g for g in rosa if g['stato'] != 'squalificato' and g['p'] < 0.5 and g['mu'] >= 6.0]
    if not (sq or di or fuori):
        return
    print('\n--- ALLARMI ---')
    for g in sq:
        print(f'  SQUALIFICATO  {g["nome"]}  (salta la giornata {C.g})')
    for g in di:
        print(f'  diffidato     {g["nome"]}  (al prossimo giallo salta)')
    for g in sorted(fuori, key=lambda x: -x['mu'])[:6]:
        print(f'  a rischio     {g["nome"]}  gioca con probabilita {g["p"] * 100:.0f}% '
              f'({g.get("fonte_p", "")})')


def stampa_formazione(C, ris):
    b = ris['migliore']
    print(f'\n--- FORMAZIONE CONSIGLIATA: {b["modulo"]}  (criterio: {b["criterio"]}) ---')
    print(f'  {"":<21}{"squadra":<9}{"partita":<12}{"fv":>5}{"gioca":>6}')
    for r in regole.RUOLI:
        for g in (x for x in b['titolari'] if x['ruolo'] == r):
            print(f'  {r} ' + _gioc(g))
    print('  panchina (in quest ordine):')
    for i, g in enumerate(b['panchina'], 1):
        print(f'  {i:>2}. {g["ruolo"]} ' + _gioc(g))
    print(f'\n  fantapunti attesi {b["media"]:.1f} (+- {b["sd"]:.1f}) | gol medi {b["gol_medi"]:.2f}')
    if 'p_v' in b:
        a = ris['avversario']
        print(f'  avversario: {a["media"]:.1f} (+- {a["sd"]:.1f})')
        print(f'  VITTORIA {b["p_v"] * 100:.0f}% | pareggio {b["p_n"] * 100:.0f}% | '
              f'sconfitta {b["p_s"] * 100:.0f}%  ->  {b["punti"]:.2f} punti attesi')
        base = next((c for c in ris['candidati'] if c['modulo'] == b['modulo'] and c['criterio'] == 'mu'),
                    None)
        favorito = b['media'] > a['media']
        print(f'  sei {"FAVORITO" if favorito else "SFAVORITO"}: '
              + ('la varianza ti e nemica, meglio chi garantisce il voto.' if favorito
                 else 'ti serve la coda alta, meglio chi puo fare il colpo.'))
        if base is not None and base is not b and b['punti'] - base['punti'] > 0.005:
            dm = b['media'] - base['media']
            print(f'  rispetto a schierare i migliori per fantavoto: {b["punti"] - base["punti"]:+.2f} '
                  f'punti in classifica attesi, {dm:+.1f} fantapunti di media'
                  + ('  <- rinunci a media per vincere piu spesso' if dm < 0 else ''))
    alt = [c for c in ris['candidati'] if c is not b][:3]
    if alt:
        print('  alternative valutate:')
        for c in alt:
            extra = f'  {c["punti"]:.2f} pt  V {c["p_v"] * 100:.0f}%' if 'p_v' in c else ''
            print(f'     {c["modulo"]:<6}{c["criterio"]:<14}{c["media"]:>6.1f}{extra}')


def portieri(C, n_giornate=5):
    if not C.partite:
        print('\n  (portieri: serve il calendario)')
        return
    E = C.stime_giornata(C.g)
    mie = [g for g in C.rosa(C.mia, E) if g['ruolo'] == 'P']
    if not mie:
        return
    print(f'\n--- PORTIERI: gol subiti attesi, prossime {n_giornate} giornate ---')
    gg = range(C.g, C.g + n_giornate)
    print('  ' + ' ' * 22 + ''.join(f'{"G" + str(g):>7}' for g in gg))
    for p in mie:
        vals = [calendario.gol_subiti_attesi(C.partite, C.F, p['squadra'], g) for g in gg]
        print(f'  {p["nome"][:20]:<22}' + ''.join(f'{v:>7.2f}' if v is not None else f'{"-":>7}'
                                                  for v in vals))
    sq = sorted({p['squadra'] for p in mie if p['squadra']})
    if len(sq) >= 2:
        gr = calendario.griglia(C.partite, C.F, sq, gg)
        c = gr[0]
        print(f'  coppia migliore della tua rosa: {c["coppia"][0]} + {c["coppia"][1]} '
              f'({c["gs_attesi"]:.2f} gol subiti attesi scegliendo ogni volta)')


# ------------------------------------------------------------------ COMANDI

def _serve_rosa(C):
    if not C.mia:
        raise SystemExit('\n[!] non trovo la tua rosa: metti "mia": "<nome squadra>" in lega.json '
                         'e le rose in rose.csv (FantaSquadra;Nome)\n')


def cmd_formazione(C, A, briefing=False):
    _serve_rosa(C)
    E = C.stime_giornata(C.g)
    rosa = C.rosa(C.mia, E)
    nome_avv = C.avversario_di(C.g, A.avversario)
    avv = None
    if nome_avv and C.R['formula'] == 'scontri':
        chiavi = C._rosa_di(nome_avv)
        if chiavi:
            avv = C.rosa(chiavi, E)
            print(f'\n  avversario della giornata {C.g}: {nome_avv}')
        else:
            print(f'\n  !! avversario "{nome_avv}" non trovato in rose.csv: ottimizzo la media')
    if briefing:
        allarmi(C, E)
    ris = schiera.consiglia(rosa, C.R, avversario=avv, n=A.sim)
    if ris.get('avviso'):
        print(f'  !! {ris["avviso"]}')
    stampa_formazione(C, ris)
    return ris


def cmd_settimana(C, A):
    intestazione(C, 'BRIEFING DELLA SETTIMANA')
    cmd_formazione(C, A, briefing=True)
    portieri(C)
    if C.rose:
        occupati = {k for v in C.rose.values() for k in v}
        Es = [C.stime_giornata(g) for g in range(C.g, C.g + A.giornate)]
        sv = mercato.svincolati(C.mia, occupati, Es, C.R, top=5)
        if sv:
            print(f'\n--- SVINCOLATI CHE MIGLIORANO LA TUA FORMAZIONE (prossime {A.giornate}) ---')
            for x in sv:
                print(f'  {x["ruolo"]} {x["nome"][:20]:<21}{x["squadra"][:8]:<9}'
                      f'+{x["guadagno"]:.1f} fantapunti   taglieresti {C.E_base[x["taglia"]]["nome"]}')
    print()


def cmd_rosa(C, A):
    _serve_rosa(C)
    intestazione(C, 'LA TUA ROSA')
    E = C.stime_giornata(C.g)
    print(f'\n  {"":<3}{"":<21}{"squadra":<9}{"partita":<12}{"fv":>5}{"gioca":>6}  '
          f'{"pres":>4}  fonte')
    for r in regole.RUOLI:
        for g in sorted((x for x in C.rosa(C.mia, E) if x['ruolo'] == r), key=lambda x: -x['mu']):
            print(f'  {r} ' + _gioc(g) + f'{g["n"]:>4}  {g["fonte"]}')
    print()


def cmd_scambio(C, A):
    _serve_rosa(C)
    intestazione(C, 'VALUTAZIONE SCAMBIO')
    dai = [x.strip() for x in A.dai.split(',') if x.strip()]
    ricevi = [x.strip() for x in A.ricevi.split(',') if x.strip()]
    Es = [C.stime_giornata(g) for g in range(C.g, C.g + A.giornate)]
    r = mercato.scambio(C.mia, dai, ricevi, Es, C.R)
    if 'errore' in r:
        raise SystemExit(f'\n[!] {r["errore"]}\n')
    print(f'\n  dai:    {", ".join(dai)}\n  ricevi: {", ".join(ricevi)}')
    print(f'\n  sulla carta (somma fantavoti attesi):   {r["delta_grezzo"]:+.1f} in {A.giornate} giornate')
    print(f'  nella TUA formazione migliore:          {r["delta"]:+.1f} in {A.giornate} giornate')
    verdetto = ('CONVIENE' if r['delta'] > 1 else 'NON conviene' if r['delta'] < -1
                else 'e quasi indifferente')
    print(f'\n  -> {verdetto}.')
    if (r['delta'] > 0) != (r['delta_grezzo'] > 0):
        print('     Attenzione: sulla carta dice il contrario. Conta quello che schieri, non la '
              'somma dei valori.')
    print()


def cmd_svincolati(C, A):
    _serve_rosa(C)
    intestazione(C, 'SVINCOLATI')
    occupati = {k for v in C.rose.values() for k in v}
    Es = [C.stime_giornata(g) for g in range(C.g, C.g + A.giornate)]
    sv = mercato.svincolati(C.mia, occupati, Es, C.R, ruolo=A.ruolo, top=A.top)
    if not sv:
        print('\n  nessun libero migliorerebbe la tua formazione. Tieniti la rosa.\n')
        return
    print(f'\n  guadagno = fantapunti in piu della tua formazione nelle prossime {A.giornate} giornate')
    for x in sv:
        print(f'  {x["ruolo"]} {x["nome"][:20]:<21}{x["squadra"][:8]:<9}+{x["guadagno"]:>5.1f}   '
              f'fv {x["mu"]:.1f} | gioca {x["p"] * 100:.0f}%   taglia {C.E_base[x["taglia"]]["nome"]}')
    print()


def cmd_portieri(C, A):
    _serve_rosa(C)
    intestazione(C, 'PORTIERI')
    portieri(C, A.giornate)
    if C.partite:
        occupati = {k for v in C.rose.values() for k in v}
        mie = {g['squadra'] for g in C.rosa(C.mia, C.E_base) if g['ruolo'] == 'P'}
        liberi = {g['squadra'] for k, g in proiezioni.giocatori(C.E_base).items()
                  if g['ruolo'] == 'P' and k not in occupati and g['p'] >= 0.5 and g['squadra']}
        if mie and liberi:
            gg = range(C.g, C.g + A.giornate)
            best = []
            for m in mie:
                for l in liberi - mie:
                    c = calendario.griglia(C.partite, C.F, [m, l], gg)[0]
                    best.append(c)
            print('\n  portieri LIBERI (titolari) che fanno la coppia migliore con i tuoi:')
            for c in sorted(best, key=lambda c: c['gs_attesi'])[:5]:
                print(f'     {c["coppia"][0]} + {c["coppia"][1]}   {c["gs_attesi"]:.2f} gol subiti attesi')
    print()


def cmd_proposte(C, A):
    _serve_rosa(C)
    intestazione(C, 'SCAMBI CHE CONVENGONO A ENTRAMBI')
    Es = [C.stime_giornata(g) for g in range(C.g, C.g + A.giornate)]
    cap = C.R.get('capitano') or {}
    intocc = {cap.get('k'), cap.get('kv')} - {None} if cap.get('attivo') else set()
    L = mercato.proposte(C._nome_rosa(), C.rose, Es, C.R, top=A.top, intoccabili=intocc)
    if intocc:
        print('\n  capitano e vice esclusi dalle offerte (designati per tutta la stagione)')
    if not L:
        print('\n  nessuno scambio migliora la tua formazione E quella dell altro.\n')
        return
    print(f'\n  fantapunti in piu nelle prossime {A.giornate} giornate, per te e per lui '
          '(scambi solo a pari ruolo complessivo)')
    nome = lambda k: C.E_base[k]['nome'] if k in C.E_base else k
    for x in L:
        print(f'  {x["avversario"][:18]:<19} dai {" + ".join(nome(k) for k in x["dai"]):<30} '
              f'ricevi {" + ".join(nome(k) for k in x["ricevi"]):<30} '
              f'te {x["per_me"]:+.1f} | lui {x["per_lui"]:+.1f}')
    print('\n  Il "lui" e la stima del socio, non la sua: proponilo partendo da quello che ci guadagna.\n')


def cmd_lega(C, A):
    _serve_rosa(C)
    intestazione(C, 'LA LEGA: forza delle squadre e prossimi scontri')
    E = C.stime_giornata(C.g)
    forze = []
    for nome, chiavi in C.rose.items():
        rosa = C.rosa(chiavi, E)
        f = schiera.migliore_semplice(rosa, C.R)
        if f is None:
            continue
        tot = schiera.punteggi(f, schiera.estrazioni(rosa, A.sim, 11), C.R)
        m = sum(tot) / len(tot)
        forze.append((m, nome, sum(regole.gol(x, C.R) for x in tot) / len(tot)))
    print(f'\n  {"":<3}{"squadra":<22}{"fantapunti attesi":>18}{"gol attesi":>11}')
    for i, (m, nome, gm) in enumerate(sorted(forze, reverse=True), 1):
        io = '  <- tu' if nome == C._nome_rosa() else ''
        print(f'  {i:<3}{nome[:21]:<22}{m:>18.1f}{gm:>11.2f}{io}')
    cal = C.R.get('calendario_lega') or {}
    prossime = [(g, cal[str(g)]) for g in range(C.g, C.g + A.giornate) if str(g) in cal]
    if prossime:
        print('\n  prossimi scontri (stessa forza per tutte le giornate: senza calendario di Serie A')
        print('  non si corregge per le partite vere)')
        rosa = C.rosa(C.mia, E)
        tot_pt = 0.0
        for g, avv in prossime:
            chiavi = C._rosa_di(avv)
            if not chiavi:
                print(f'    G{g:<3}{avv:<22} rosa non trovata')
                continue
            r = schiera.consiglia(rosa, C.R, avversario=C.rosa(chiavi, E), n=A.sim, moduli_top=2)
            b = r['migliore']
            tot_pt += b['punti']
            print(f'    G{g:<3}{avv[:21]:<22} V {b["p_v"] * 100:>3.0f}%  N {b["p_n"] * 100:>3.0f}%  '
                  f'S {b["p_s"] * 100:>3.0f}%   {b["punti"]:.2f} punti attesi')
        print(f'    totale atteso: {tot_pt:.1f} punti in {len(prossime)} giornate')
    print()


def cmd_asta(C, A):
    import mercato_asta
    import piano_asta
    if not A.mercato:
        titolo = 'ASTA: rigioco del 05/09' if A.rigioca else \
            ('ASTA: piano live' if A.live else 'ASTA: piano d asta e prezzo massimo')
        intestazione(C, titolo)
        rc = piano_asta.esegui(C.R, C.file['listone'], C.file['prezzi'],
                               'rigioca' if A.rigioca else 'piano', A.candidati, A.live)
        if rc:
            raise SystemExit(rc)
        print()
        return
    if not os.path.exists(C.file['prezzi']):
        raise SystemExit(f'\n[!] prezzi d asta non trovati: {C.file["prezzi"]} '
                         '(FantaSquadra;Nome;Ruolo;Pagato;FVM, in lega.json -> file.prezzi)\n')
    listone = C.file['listone'] if os.path.exists(C.file['listone']) else None
    try:
        acquisti = mercato_asta.carica(C.file['prezzi'], listone)
    except fanta.DatoMancante as e:
        raise SystemExit(f'\n[!] {e}\n')
    intestazione(C, 'ASTA: prezzo di mercato della lega')
    if not listone:
        print('  !! senza listone: solo i comprati, niente probabilita di acquisto')
    print()
    mercato_asta.stampa(acquisti, mercato_asta.stima(acquisti), A.ruolo, A.top, con_listone=bool(listone))
    print()


def _guadagni_liberi(C, occupati, top):
    """Liberi che migliorano la tua formazione, con il guadagno da qui alla 38a.
    I liberi si stimano dal listone (+ scouting); i rosati restano sulle stime di stagione."""
    oggi = datetime.date.today().isoformat()
    E_lis = scouting.applica(proiezioni.stima(S=None, listone=C.listone, titolari=None, R=C.R, prossima=False),
                             C.schede, oggi)
    E_mix = dict(E_lis, **proiezioni.giocatori(C.E_base))
    rimaste = max(1, 38 - C.g + 1)
    sv = mercato.svincolati(C.mia, occupati, [E_mix], C.R, top=top)
    return sv, {x['k']: x['guadagno'] * rimaste for x in sv}, rimaste


def cmd_scouting(C, A):
    if not C.listone:
        raise SystemExit(f'\n[!] listone assente ({C.file["listone"]}): serve per sapere chi e libero '
                         '(in lega.json -> file.listone)\n')
    occupati = {k for v in C.rose.values() for k in v}
    neo = C.R.get('neopromosse') or []
    if A.azione == 'candidati':
        intestazione(C, 'SCOUTING: chi schedare fra i liberi')
        if not neo:
            print('  !! "neopromosse" non e in lega.json: manca il segnale piu forte')
        guadagni = _guadagni_liberi(C, occupati, 15)[1] if C.mia else {}
        if not C.mia:
            print('  !! senza la tua rosa niente segnale "i numeri": solo segnali strutturali')
        cand = scouting.candidati(C.listone, occupati, neo, n=A.n, guadagni=guadagni)
        print(f'\n  {len(cand)} candidati (liberi = listone meno le {len(C.rose)} rose). Schedali con la skill '
              'scouting,\n  una scheda JSON per giocatore in scouting/.\n')
        print(f'  {"":<2}{"giocatore":<22}{"sq":<5}{"quota":>6}{"FVM":>5}  {"scheda":<11}segnali')
        for c in cand:
            sch = C.schede.get(c['k'])
            stato = f'{sch["data"]}' if sch else '-'
            q = c.get('quota')
            print(f'  {c["ruolo"]:<2}{c["nome"][:21]:<22}{str(c.get("squadra", ""))[:4]:<5}'
                  f'{(f"{q:.0f}" if q is not None else "-"):>6}{(c.get("fvm") or 0):>5.0f}  {stato:<11}'
                  + ('; '.join(c['segnali']) or '-'))
        print()
        return
    _serve_rosa(C)
    intestazione(C, 'SCOUTING: gioielli e prezzo massimo')
    sv, guadagni, rimaste = _guadagni_liberi(C, occupati, max(3 * A.slot, 15))
    gi = scouting.gioielli(sv, guadagni, A.budget, A.slot)
    if C.tabella:
        print('  !! i liberi sono stimati dal listone (stagione scorsa) + scouting; i tuoi dalla stagione in corso')
    if not gi:
        print('\n  nessun libero migliorerebbe la tua formazione. Tieniti i crediti.\n')
        return
    print(f'\n  guadagno = fantapunti in piu della tua formazione da qui alla 38a ({rimaste} giornate)')
    print(f'  prezzo max a somma zero su {A.budget:.0f} crediti e {A.slot} slot, poi tetti '
          f'{scouting.TETTO_GIOIELLO} (tutti) e {scouting.TETTO_PORTIERE} (portieri)\n')
    print(f'  {"":<2}{"giocatore":<22}{"sq":<5}{"guadagno":>9}  {"scheda":<24}{"prezzo max":>10}')
    for g in gi:
        sch = C.schede.get(g['k'])
        if sch:
            i, c = scouting.indice(sch)
            stato = f'indice {i:+.2f} conf {c:.0%}'
        else:
            stato = 'NON schedato'
        print(f'  {g["ruolo"]:<2}{g["nome"][:21]:<22}{str(g.get("squadra", ""))[:4]:<5}{g["guadagno"]:>+9.1f}  '
              f'{stato:<24}{g["prezzo_max"]:>10.0f}')
    tagliati = sum(g['tagliato'] for g in gi)
    print(f'\n  crediti tagliati dai tetti, da NON spendere: {tagliati:.0f}'
          if tagliati else '\n  nessun credito tagliato dai tetti')
    print()


def cmd_verifica(C, A):
    import verifica
    intestazione(C, 'VERIFICA')
    rec = voti.archivio(C.file['voti'], R=C.R)
    if not A.scouting:
        verifica.stampa(verifica.backtest(rec, C.listone, C.partite, C.R, C.mia), C.R)
        print()
        return
    if not C.schede:
        raise SystemExit(f'\n[!] nessuna scheda di scouting in {C.file["scouting"]}\n')
    # la stima numerica di ogni giocatore e' quella fatta coi voti fino alla giornata della sua scheda
    per_g, stime = {}, {}
    for k, s in C.schede.items():
        g0 = s.get('giornata')
        if isinstance(g0, int):
            if g0 not in per_g:
                per_g[g0] = verifica.stime_prima(rec, C.listone, C.partite, C.R, g0 + 1)[1]
            if k in per_g[g0]:
                stime[k] = per_g[g0][k]
    senza = sum(1 for s in C.schede.values() if not isinstance(s.get('giornata'), int))
    if senza:
        print(f'  !! {senza} schede senza "giornata": non si sa da dove misurarle, escluse')
    verifica.stampa_kpi(verifica.verifica_kpi(C.schede, rec, stime), len(C.schede), len(stime))
    print()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--lega', default='lega.json')
    ap.add_argument('--giornata', type=int, default=None)
    sub = ap.add_subparsers(dest='cmd')
    for nome in ('settimana', 'formazione', 'rosa', 'scambio', 'svincolati', 'portieri', 'verifica',
                 'proposte', 'lega', 'asta', 'scouting'):
        p = sub.add_parser(nome)
        p.add_argument('--avversario', default=None)
        p.add_argument('--sim', type=int, default=3000, help='simulazioni Monte Carlo')
        p.add_argument('--giornate', type=int, default=5, help='orizzonte per mercato e portieri')
        if nome == 'scambio':
            p.add_argument('--dai', required=True)
            p.add_argument('--ricevi', required=True)
        if nome in ('svincolati', 'asta'):
            p.add_argument('--ruolo', choices=list(regole.RUOLI), default=None)
        if nome in ('svincolati', 'proposte', 'asta'):
            p.add_argument('--top', type=int, default={'svincolati': 15, 'proposte': 10, 'asta': 25}[nome])
        if nome == 'asta':
            p.add_argument('--mercato', action='store_true', help='solo il prezzo di mercato della lega')
            p.add_argument('--candidati', type=int, default=12, help='giocatori con tetto per reparto')
            p.add_argument('--live', default=None, help='stato dell asta in corso (json)')
            p.add_argument('--rigioca', action='store_true', help='rigioca l asta del 05/09 col piano')
        if nome == 'verifica':
            p.add_argument('--scouting', action='store_true', help='misura i KPI delle schede di scouting')
        if nome == 'scouting':
            p.add_argument('azione', choices=['candidati', 'gioielli'])
            p.add_argument('--n', type=int, default=30, help='quanti candidati')
            p.add_argument('--budget', type=float, default=50, help='crediti per il mercato di gennaio')
            p.add_argument('--slot', type=int, default=3, help='slot da riempire a gennaio')
    A = ap.parse_args(argv)
    if not A.cmd:
        ap.print_help()
        return 0
    try:
        C = Contesto(A.lega, A.giornata)
    except fanta.DatoMancante as e:
        raise SystemExit(f'\n[!] {e}\n')
    {'settimana': cmd_settimana,
     'formazione': lambda C, A: (intestazione(C, 'FORMAZIONE'), cmd_formazione(C, A), print()),
     'rosa': cmd_rosa, 'scambio': cmd_scambio,
     'svincolati': cmd_svincolati, 'portieri': cmd_portieri,
     'verifica': cmd_verifica, 'proposte': cmd_proposte, 'lega': cmd_lega, 'asta': cmd_asta,
     'scouting': cmd_scouting}[A.cmd](C, A)
    return 0


if __name__ == '__main__':
    sys.exit(main())
