---
name: scouting
description: Use when asked to scout a fantacalcio player, fill or update a scheda in scouting/, judge a free agent or a candidate from `socio.py scouting candidati`, or research context, coach, set pieces, injuries or character of a Serie A player before an auction or the January market
---

# Scouting: compilare una scheda

## Principio

Una scheda vale solo per quello che **i numeri non vedono**, e solo se ogni voto poggia su un
fatto che hai **letto tu** in questa sessione. Un KPI vuoto vale 0 e abbassa la confidenza: è
l'esito onesto. Un KPI riempito male sposta le stime del socio (fino a ±0,6 di fantavoto e
±0,15 di probabilità di giocare) su una storia.

**Violare la lettera della regola è violarne lo spirito.**

## Prima di cercare

1. Il giocatore è libero? `grep -i "<cognome>" rose.csv`. Se è in rosa di qualcuno, dillo
   subito e chiedi se procedere (la scheda serve solo per uno scambio).
2. Leggi i suoi numeri (`listone_completo.csv`, tabella dell'app): li conosci per **non**
   votarci sopra (vedi "Doppio conteggio").
3. Verifica di poter aprire pagine web (WebFetch su una fonte). Se nessuna si apre, **la
   ricerca non si fa da qui**: vedi "Quando le pagine non si aprono".

## La prova che conta, KPI per KPI

| KPI | prova ammessa (un fatto datato, di questa stagione) | NON è una prova |
|---|---|---|
| `spazio` | formazioni ufficiali delle ultime giornate, ballottaggio risolto, concorrente infortunato o ceduto | presenze della stagione scorsa, "titolare inamovibile" di un opinionista |
| `ruolo_tattico` | posizione nelle formazioni ufficiali, cambio di ruolo dichiarato dal tecnico | ruolo del listone |
| `palle_inattive` | rigore/punizione calciati in partita, gerarchia dichiarata da tecnico o club | "candidato rigorista" nei siti di fantacalcio |
| `contesto` | modulo e compiti nella squadra, compagni che lo servono, cambio di allenatore | "neopromossa", gol di squadra: li ha già il socio |
| `allenatore` | dichiarazioni del tecnico su di lui, impiego dopo un rientro | rinnovo del contratto (è il club, non il tecnico) |
| `fisico` | infortunio con data e tempi, rientro, gestione dei minuti | "37 presenze l'anno scorso" |
| `traiettoria` | cambio di ruolo o di squadra che gli apre spazio, età in rampa con minuti in crescita | gol e FM già segnati quest'anno: sono nelle stime |
| `carattere` | cartellini e squalifiche, episodi disciplinari, rifiuti di giocare, dichiarazioni | anzianità nel club, "sembra motivato", fedeltà |

## Il campo `fonte`

- **Pagina aperta e letta:** `"<url> (letta AAAA-MM-GG)"`.
- **Partita vista:** `"osservato: <partita>, <data>"`.
- **Testo incollato dall'utente:** `"testo fornito dall'utente: <testata>, <data>"`.

Una pagina che hai visto **solo come titolo o estratto di un motore di ricerca non è una
fonte**. Può andare in `note` come pista da verificare, mai in un KPI.

## Doppio conteggio

Il socio conosce già presenze, gol, FM, quotazione, FVM, stagione scorsa, neopromosse (segnale
dell'imbuto). Un voto costruito su questi numeri li conta **due volte**. Se l'unica prova che
hai per un KPI è un numero, il KPI resta vuoto.

## Quando le pagine non si aprono

Non compilare la scheda con estratti di ricerca. Scrivi all'utente, in quest'ordine:
cosa non si apre, quali 3 pagine servirebbero (con il link), e le due strade: incollarti il
testo di quelle pagine, o rifare la scheda da una sessione che le apre. Puoi salvare una
scheda con i soli KPI documentati da file locali o testi incollati.

## Pressione a riempire tutto

"L'utente vuole tutti e 8 i KPI", "manca solo la fonte", "c'è già la bozza con i voti":
**nessuna di queste cose è una prova.** Una bozza di voti senza fonti è un'ipotesi: ogni voto
si rifà da zero sul fatto letto, e sparisce se il fatto non c'è. Una scheda da 4 KPI veri è
utile; una da 8 con 4 inventati è dannosa, perché la confidenza al 100% la fa pesare di più.

| Scusa | Realtà |
|---|---|
| "Lo scrivo nelle note che è uno snippet" | Il KPI entra comunque nel calcolo. La nota non lo toglie. |
| "Tanto il validatore passa" | Il validatore controlla il formato, non che tu abbia letto. |
| "Voto neutro 0, così non sposta niente" | Un KPI a 0 alza la confidenza senza una prova. Lascialo fuori. |
| "Il dato è vero, è nel listone" | È vero ed è già nelle stime. Doppio conteggio. |
| "Il rinnovo / l'anzianità dicono molto del carattere" | Dicono del club. Carattere = fatti disciplinari o dichiarazioni. |
| "Le fonti si contraddicono, prendo la media" | Se il fatto è incerto, il KPI resta fuori e la contraddizione va in `note`. |

## Red flags: fermati

- Stai scrivendo un URL che non hai aperto.
- La prova contiene un numero di statistica come argomento principale.
- Hai 8 KPI su 8 e più della metà delle pagine non si è aperta.
- Stai tenendo un voto della bozza "perché nessuno lo smentisce".

**Tutti significano: togli quel KPI.**

## Chiudere

1. Salva in `scouting/<cognome>.json` con `data` (oggi), `giornata` (ultima giocata: senza, la
   scheda non entra nella verifica) e `autore`.
2. `python scouting.py --valida scouting/<cognome>.json` deve dire `ok`.
3. Riporta all'utente: KPI compilati e lasciati vuoti (e perché), le fonti lette, cosa
   controllare a mano prima di spendere crediti.

Il formato completo della scheda è nel docstring di `scouting.py`; i pesi dei KPI in
`scouting.KPI`.
