# Candidati allo scouting — settembre 2026

**28/09/2026**, dopo 5 giornate. Generata con `python socio.py scouting candidati` (rifalla
quando cambiano le rose). **Liberi** = listone di agosto meno le 10 rose di *porcodidiosanto*.

Come leggerla:

- **attaccante di neopromossa**: il segnale più forte misurato nella lega (fra i pagati ≤ 5
  crediti, 4 colpi da FM ≥ 7 su 10, contro 2 su 16 per gli altri attaccanti).
- **i numeri: +X**: fantapunti in più che la formazione di AL DOMORO farebbe da qui alla 38ª
  prendendolo al posto del peggiore del reparto (stima dalla stagione scorsa: i liberi non
  sono nella tabella dell'app). È dove i numeri dicono che serve rinforzarsi: **la difesa**.
- Leao, Lukaku, Romero D. liberi con FVM 37-75: da schedare per primi sullo `spazio` e sul
  `fisico` (perché nessuno li ha presi ad agosto?).

Prossimo passo: una scheda JSON per giocatore in `scouting/` seguendo la skill di progetto
`.claude/skills/scouting/SKILL.md`, poi `python socio.py scouting gioielli --budget B --slot S`
per il prezzo massimo di gennaio.

```
    giocatore             sq    quota  FVM  scheda     segnali
  A Ghedjemis             FRO       8   23  -          attaccante di neopromossa (4 colpi su 10 fra i pagati <= 5)
  A Rrahmani Al.          VEN       7   13  -          attaccante di neopromossa (4 colpi su 10 fra i pagati <= 5)
  A Birligea              FRO       5   11  -          attaccante di neopromossa (4 colpi su 10 fra i pagati <= 5); quotazione bassa (5)
  A Adorante              VEN       4    8  -          attaccante di neopromossa (4 colpi su 10 fra i pagati <= 5); quotazione bassa (4)
  A Petagna               MON       2    5  -          attaccante di neopromossa (4 colpi su 10 fra i pagati <= 5); quotazione bassa (2)
  A Robinson J.           MON       4    5  -          attaccante di neopromossa (4 colpi su 10 fra i pagati <= 5); quotazione bassa (4)
  A Lauberbach            VEN       1    1  -          attaccante di neopromossa (4 colpi su 10 fra i pagati <= 5); quotazione bassa (1)
  A Lisman                VEN       1    1  -          attaccante di neopromossa (4 colpi su 10 fra i pagati <= 5); quotazione bassa (1)
  C Cristante             ROM       9   29  -          i numeri: +10.3 alla tua formazione
  C Thuram K.             JUV       9   25  -          i numeri: +10.9 alla tua formazione
  C Konè I.               SAS       8   20  -          i numeri: +12.3 alla tua formazione
  D Romagnoli             LAZ       6   20  -          i numeri: +14.7 alla tua formazione
  D Circati               PAR       6   18  -          i numeri: +14.1 alla tua formazione
  D Djimsiti              ATA       7   16  -          i numeri: +14.5 alla tua formazione
  D Obert                 CAG       7   15  -          i numeri: +15.4 alla tua formazione
  D Gallo                 LEC       6   12  -          i numeri: +18.8 alla tua formazione
  D Kabasele              UDI       4   12  -          i numeri: +10.6 alla tua formazione
  D Veiga D.              LEC       6   12  -          i numeri: +13.0 alla tua formazione
  D Ranieri L.            FIO       3   10  -          i numeri: +13.2 alla tua formazione
  D Walukiewicz           SAS       4   10  -          i numeri: +13.9 alla tua formazione
  D Pongracic             FIO       4    8  -          i numeri: +12.7 alla tua formazione
  D Tomori                MIL       6    8  -          i numeri: +14.4 alla tua formazione
  D Terracciano F.        MIL       2    4  -          i numeri: +15.8 alla tua formazione
  A Leao                  MIL      18   75  -          attaccante (2 colpi su 16 fra i pagati <= 5)
  A Lukaku                NAP      10   45  -          attaccante (2 colpi su 16 fra i pagati <= 5)
  A Romero D.             PAR      10   37  -          attaccante (2 colpi su 16 fra i pagati <= 5)
  A Osmajic               GEN       8   28  -          attaccante (2 colpi su 16 fra i pagati <= 5)
  A David                 JUV       8   25  -          attaccante (2 colpi su 16 fra i pagati <= 5)
  A Ratkov                LAZ       9   22  -          attaccante (2 colpi su 16 fra i pagati <= 5)
  A Dia                   LAZ      10   20  -          attaccante (2 colpi su 16 fra i pagati <= 5)
```
