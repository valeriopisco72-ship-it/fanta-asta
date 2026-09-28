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
    python socio.py --lega altra/lega.json settimana

Tutto si configura in `lega.json` (v. regole.py per le regole, e la sezione
'file' per i percorsi). Ogni dato mancante viene detto in testa all'output, e
il tool gira comunque con quello che c'e': un listone e una rosa bastano, ogni
file in piu' (voti, calendario, probabili) rende le stime migliori.

Per provarlo senza dati veri:  python esempio.py --stagione
"""
import argparse
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
import voti

FILE_DEFAULT = {'listone': 'listone_completo.csv', 'voti': 'voti', 'calendario': 'calendario.csv',
                'rose': 'rose.csv', 'titolari': 'titolari.csv', 'squadre': 'squadre_2025-26.csv'}
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
        if not self.S:
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
        self.E_ora = proiezioni.stima(S=self.S, listone=self.listone, titolari=self.titolari,
                                      R=self.R, prossima=True)
        self.E_base = proiezioni.stima(S=self.S, listone=self.listone, titolari=None,
                                       R=self.R, prossima=False)

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
    if C.listone:
        fonti.append(f'listone ({len(C.listone)})')
    if C.F:
        fonti.append(f'calendario ({C.F["fonte"]})')
    if C.titolari is not None:
        fonti.append(f'probabili ({len(C.titolari)} titolari)')
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


def cmd_verifica(C, A):
    import verifica
    intestazione(C, 'VERIFICA')
    rec = voti.archivio(C.file['voti'], R=C.R)
    verifica.stampa(verifica.backtest(rec, C.listone, C.partite, C.R, C.mia), C.R)
    print()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--lega', default='lega.json')
    ap.add_argument('--giornata', type=int, default=None)
    sub = ap.add_subparsers(dest='cmd')
    for nome in ('settimana', 'formazione', 'rosa', 'scambio', 'svincolati', 'portieri', 'verifica'):
        p = sub.add_parser(nome)
        p.add_argument('--avversario', default=None)
        p.add_argument('--sim', type=int, default=3000, help='simulazioni Monte Carlo')
        p.add_argument('--giornate', type=int, default=5, help='orizzonte per mercato e portieri')
        if nome == 'scambio':
            p.add_argument('--dai', required=True)
            p.add_argument('--ricevi', required=True)
        if nome == 'svincolati':
            p.add_argument('--ruolo', choices=list(regole.RUOLI), default=None)
            p.add_argument('--top', type=int, default=15)
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
     'verifica': cmd_verifica}[A.cmd](C, A)
    return 0


if __name__ == '__main__':
    sys.exit(main())
