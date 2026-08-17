# Allenatori: storia tattica · e cosa studiare dopo

**10/08/2026** — complemento a `squadre.py` e `analisi.py`.

Etichette: **[oss]** misurato nei dati di questo repo · **[pub]** riportato da fonti pubbliche,
non verificato qui · **[stima]** mia inferenza · **[dav]** da verificare

---

## 1. I venti allenatori, e cosa dice il dato

Il PPDA della colonna è **[oss]** (Understat 2025/26, aggregato da `squadre.py`). Lo stile è
**[pub]**: viene dalla reputazione dei tecnici, non da una misura fatta qui. Dove i due divergono,
vince il dato — ed è successo.

### Le 9 squadre dove il dato 2025/26 vale ancora (stessa guida)

| Squadra | Allenatore | Mod. | PPDA **[oss]** | npxG/npxGA **[oss]** | Lettura |
|---|---|---|---|---|---|
| **Como** | Fabregas | 4-2-3-1 | **7,71** (1° per pressing) | 1,63 / 0,92 | il pressing più alto della Serie A, 19 clean sheet. Il contesto più affidabile del listone |
| **Roma** | Gasperini | 3-4-2-1 | **8,66** | 1,51 / 1,10 | pressing altissimo coerente con la fama; 18 clean sheet |
| **Inter** | Chivu | 3-5-2 | 9,66 | **2,17** / **0,86** | miglior produzione E miglior difesa. 89 gol |
| **Genoa** | De Rossi | 3-4-2-1 | 10,05 | 1,09 / 1,33 | pressa più di quanto il piazzamento suggerisca |
| **Juventus** | Spalletti | 3-4-2-1 | 10,58 | 1,85 / 0,89 | 69 punti su 75,5 attesi: ha raccolto **meno** dei meriti |
| **Cagliari** | Pisacane | 3-5-2 | 14,78 | 1,11 / 1,55 | blocco basso, difesa fragile |
| **Parma** | Cuesta | 3-5-2 | 13,33 | 0,91 / 1,51 | 45 punti su 37,6 attesi: **+7,4**, il secondo miglior scarto |
| **Lecce** | Di Francesco | 4-3-3 | 11,93 | 0,94 / **1,59** | la difesa che concede di più |
| **Udinese** | Runjaic | 3-5-2 | 11,60 | 1,14 / 1,36 | |

### Le 8 dove l'allenatore è cambiato — il dato è storia, non previsione

| Squadra | Nuovo | Mod. | PPDA del predecessore **[oss]** | Cosa cambia **[stima]** |
|---|---|---|---|---|
| **Napoli** | Allegri | 4-3-3 | 11,87 | Allegri **[pub]** gioca più basso e reattivo: il PPDA dovrebbe salire (= meno pressing). E il Napoli aveva già +12,5 punti sopra i meriti → doppia cautela |
| **Milan** | Amorim | 3-4-2-1 | 14,62 | Amorim **[pub]** è associato al 3-4-2-1 aggressivo: il PPDA 14,62 di Allegri è tra i più bassi come intensità, quindi ci si aspetta un calo (= più pressing) |
| **Atalanta** | Sarri | 4-3-3 | 10,63 | discontinuità forte: il 4-3-3 posizionale di Sarri **[pub]** è l'opposto delle marcature a uomo che hanno definito l'Atalanta |
| **Lazio** | Gattuso | 4-2-3-1 | **16,66** (il più passivo) | la Lazio pressava meno di tutti; Gattuso **[pub]** è tecnico di intensità → atteso calo del PPDA |
| **Bologna** | Tedesco | 4-2-3-1 | 9,89 | il Bologna pressava alto: se Tedesco mantiene, il contesto regge |
| **Fiorentina** | Grosso | 4-3-3 | 12,49 | |
| **Sassuolo** | Aquilani | 3-4-2-1 | 14,98 | |
| **Torino** | Abate | 3-5-2 | 13,10 | 63 gol subiti, il peggior dato reale del campionato |

### Le 3 senza alcun dato di Serie A

Frosinone (Alvini, 4-3-3), Monza (Juric, 3-4-2-1), Venezia (Stroppa, 3-5-2).
Juric **[pub]** è un tecnico da pressing uomo-su-uomo molto aggressivo: se il Monza lo applica,
sarà tra i PPDA più bassi. **Ma è un'aspettativa, non una misura.**

### 🔴 Il difetto di questa tabella, dichiarato

La colonna "stile" è **reputazione**, e la reputazione è il tipo di informazione che il resto di
questo progetto tratta con sospetto. La verifica seria è: a fine ottobre, ricalcolare il PPDA
delle prime 8 giornate e confrontarlo con quello del predecessore. Se Allegri al Napoli ha lo
stesso PPDA di Conte, la mia riga sopra è sbagliata — e va corretta, non difesa.

---

## 2. Cosa studiare dopo, in ordine di resa

### ✅ FATTO il 10/08: field tilt e tenuta difensiva

```bash
python squadre.py --tilt      # dove si gioca la partita
python squadre.py --tenuta    # quanto si è subito meno dell'atteso
```

**Field tilt** — quota dei passaggi profondi prodotti su prodotti+concessi. Inter **77,9%**,
Juventus 69,1%, Roma 65,0%. Sotto: Cremonese e Pisa sotto il 30%. È il proxy sui `deep` di
Understat, non sui tocchi nel terzo offensivo: misura la stessa idea in modo più grezzo, ed è
scritto nel modulo.

**Tenuta difensiva** — `npxGA totale − gol subiti`. Atalanta +12,6 · Parma +11,4 · Roma +10,8 ·
**Lecce +10,4**. Quest'ultimo è il caso interessante: il Lecce concede più di chiunque
(1,59 npxGA/partita) **ma ha subito 10 gol meno dell'atteso**. Può essere Falcone che para
davvero, o deviazioni e pali. **Senza PSxG non è distinguibile**, e il modulo si ferma lì invece
di concludere.

### 🔴 PSxG: NON si può fare, e non per pigrizia

**Il 20 gennaio 2026 Stats Perform (Opta) ha rescisso l'accordo con Sports Reference** e preteso
la rimozione immediata di tutte le statistiche avanzate da FBref **[oss]** — la causa è l'accordo
di Opta come primo distributore ufficiale FIFA di dati per il betting. Rimossi: xG, xA,
progressive passes e carries, SCA/GCA, pressing, azioni difensive, possesso avanzato e **tutte le
metriche avanzate dei portieri, PSxG compreso**. Il fetch diretto a `fbref.com/.../keepersadv/`
restituisce **403** **[oss]**.

Alternative note **[pub]**, tutte a pagamento o con accesso limitato: xgstat.com, StatsBomb (i
dati free coprono competizioni selezionate, non la Serie A corrente), SkillCorner.

**Conseguenza pratica:** il difetto sui portieri **resta aperto** e non si chiude con fonti
gratuite. Chi volesse chiuderlo davvero deve mettere a budget un fornitore dati — ed è una
decisione economica, non tecnica.

### 🔴 Fatto nuovo che cambia la roadmap
**FBref ha chiuso le statistiche avanzate a gennaio 2026** **[pub]**. Era la fonte gratuita
principale per progressive carries, pressure, PSxG e passaggi per zona. Chi scrive guide di
football analytics le dà ancora per disponibili: non lo sono più. **[dav]** verificare cosa
resta accessibile prima di progettare qualunque cosa che ci si appoggi.

### a) **PSxG** — post-shot expected goals · *la priorità n.1*
`PSxG − gol subiti` è **la** metrica per isolare la bravura di un portiere: misura quanto para
rispetto alla difficoltà dei tiri che affronta. Chiude il difetto che il tool ha ancora aperto —
i portieri valutati sulla squadra e non su sé stessi.
Fonte: era FBref **[pub]** → ora **[dav]**. Alternative da valutare: StatsBomb free data, xgstat.

### b) **Set-piece xG** — quanto di una squadra viene da palla inattiva
Una squadra che produce 1,5 npxG di cui 0,5 su corner ha un profilo diverso da una che li
costruisce tutti su azione. Cambia il valore dei **difensori alti** (che al fantacalcio segnano
di testa) e la stabilità del rendimento: le palle inattive dipendono meno dai compagni.

### c) **Field tilt** — quota di possesso nell'ultimo terzo
Il possesso totale è una metrica quasi inutile (ce l'ha anche chi gira palla dietro). Il field
tilt misura dove il possesso avviene davvero. Con PPDA e deep completa il quadro tattico.

### d) **Progressive passes / carries** — chi fa avanzare la palla
Distingue chi tocca molti palloni da chi li porta avanti. È la metrica che valorizza i terzini
moderni, ed è quella che manca per capire i difensori oltre i clean sheet.

### e) **Minuti pesati per contesto** — non tutti i 90' sono uguali
Un giocatore che entra al 75' con la squadra sotto 3-0 gioca 15 minuti che non valgono i 15 di
chi entra sullo 0-0. Si stima con lo stato del punteggio (game state), che Understat espone a
livello di partita.

### f) **La strada seria per il fattore campionato**
I coefficienti in `estero.py` sono **[stima] da fonte singola** e sono il numero più fragile di
tutto il progetto. Il metodo corretto: prendere i giocatori che hanno **cambiato campionato** e
confrontare npxG/90 prima e dopo. Serve uno storico di più stagioni — è un progetto a sé, ed è
molto più difendibile di qualunque tabella scaricata.

### g) Cose che **non** studierei adesso
- **Modelli xG proprietari**: rifare un xG da zero richiede i dati dei tiri con posizione e
  contesto. Understat lo regala già fatto; rifarlo peggio non aggiunge niente.
- **Machine learning sul rendimento**: con una stagione di storico e 20 squadre il campione è
  troppo piccolo. Più dati e meno modello, in questa fase.
- **Dati di tracking** (posizioni a 25 fps): la frontiera vera dell'analisi tattica, ma non
  esiste accesso pubblico gratuito per la Serie A.

---

## 3. Riepilogo onesto di cosa il tool sa e non sa

| Domanda | Risposta |
|---|---|
| Chi è forte? | ✅ npxG, xA, xGBuildup su 489 giocatori |
| Chi ha avuto fortuna? | ✅ delta gol−npxG, punti−xPunti |
| In che contesto gioca? | ✅ per 9 squadre su 20; ⚠️ storia per 8; ❌ niente per 3 |
| Quanto vale un portiere? | ⚠️ solo via forza difensiva della squadra; manca PSxG |
| Chi arriva dall'estero? | ⚠️ 12 giocatori con dati; il fattore di conversione è fragile |
| Come giocherà con il nuovo allenatore? | ❌ **no**, e nessun dato storico può dirlo |
