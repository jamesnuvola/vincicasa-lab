# VinciCasa SONAR — ciclo 26 (13 novembre 2026)

## Stato del lavoro

Q141-D3, **Effective Feature-Rank State & Formula-Family Behaviour**, è stato preregistrato, implementato ed eseguito in walk-forward. Il replay dedicato ha completato 12 test automatici e due esecuzioni identiche. Il report completo e il ledger sono stati generati in un artifact GitHub Actions (run 43429170989, artifact 14038935622, 4 file; 623.081 byte).

La prima persistenza Git è fallita per un push non-fast-forward: il ramo è avanzato mentre il job lavorava. Il workflow è stato corretto per fare `git fetch` e `git reset --hard origin/<branch>` prima di copiare e committare gli output. Il run 43429685137 ha persistito report, ledger, manifest, checkpoint e ricevuta. Sono stati corretti due difetti di readback (escape del NUL nel Git blob SHA e import di `hashlib` nel controllo finale). Il run **43430133247** è terminato con successo: 12/12 test, doppio replay byte-identico, persistenza e verifica remota completati. Il checkpoint e la ricevuta riportano `REMOTE_GIT_READBACK_VERIFIED`; manifest 3/3 e ricevuta 5/5 corrispondono per Git blob SHA e dimensioni.

## Ipotesi e metodo

Il segnale pre-target è la dimensionalità effettiva della matrice 40×59:

`R_t = trace(C_t)^2 / (39 × trace(C_t C_t))`

con `C_t` covarianza delle 59 feature centrate sui 40 numeri. Lo stato alto vale 1 se `R_t` supera la mediana dei 100 valori precedenti. L'outcome è la differenza fra la media delle famiglie pairwise-interaction/conditional-gate e la famiglia linear-mean sul Top-5 del target.

Il campione usa Q90 artifact 13627507532 (SHA-256 `12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077`) e Q141-A6 artifact 13997032604 (SHA-256 `e139ed4587f04ae584c12bff76bcb49d7cd397d41d7fde5a159cc487570ea3fc`). Matrice e ledger sono allineati esattamente su 3.351 target; cutoff < target, prior_draws = target_index + 50. I primi 100 target sono warm-up; restano 1.911 Discovery, 670 Validation, 670 Blind OOS storico.

## Evidenze misurate

Media dei successi Top-5 per formula (baseline uniforme per numero = 0,125):

| Split | Linear | Interaction | Gate | Media non-lineare |
|---|---:|---:|---:|---:|
| Discovery | 0,127159 | 0,126785 | 0,126867 | 0,126826 |
| Validation | 0,121561 | 0,122048 | 0,121990 | 0,122019 |
| Blind OOS | 0,124662 | 0,124776 | 0,124530 | 0,124653 |

Effetto primario = differenza della media non-lineare meno linear fra stato alto e basso:

| Split | Alto − basso | Conteggi alto/basso |
|---|---:|---:|
| Discovery | -0,000168 | 951 / 960 |
| Validation | -0,000365 | 346 / 324 |
| Blind OOS | **-0,000294** | 338 / 332 |

Blind OOS:
- IC 95% circular moving-block bootstrap (20.000 repliche, blocco 20): [-0,001833; +0,001239].
- p circular-shift a due code (20.000): 0,679516.
- Sensibilità HAC/Newey-West, 20 lag, trend lineare: coefficiente stato -0,000349; p normale approssimato 0,631339.
- Holm sui tre endpoint preregistrati: p aggiustato = 1,000 per tutti.
- Soglia pratica primaria preregistrata: +0,005.

**Decisione:** `NO_EFFECTIVE_RANK_CONDITIONAL_LIFT_DEMONSTRATED`. L'effetto osservato ha segno opposto all'ipotesi, è molto inferiore alla soglia pratica e l'intervallo comprende zero. D3 non è promosso.

## Controlli e limiti

- 12/12 test automatici superati nel replay dedicato; due esecuzioni hanno prodotto output identici.
- Verificati allineamento date/cutoff/cinquine, 59 feature finite, conteggi formula per scope, warm-up e invarianza del segnale alla mutazione dei suffissi futuri.
- Inferenza al livello target; i 650 linear, 2.100 interaction e 2.800 gate per scope sono campioni deterministici dipendenti, non osservazioni formula indipendenti.
- Il Blind OOS storico è già stato esposto alla ricerca SONAR: è esplorativo, non una nuova conferma prospettica.
- Holm copre i tre endpoint D3, non l'intera famiglia Q00-Q141.
- Il test valuta quote Top-5 per numero, non la probabilità di una cinquina esatta.

## Atlante AST comune: audit completato

Audit separato sul branch sorgente Q141: 13/13 blob del Git tree coincidono con SHA-1 e byte size dei manifest (8 Q90, 5 Q7). Le finestre sono prefissi annidati: Q7 3.387 estrazioni fino al 24 ottobre; Q90 3.401 fino al 7 novembre; main 3.406 fino al 12 novembre. I record ordinati coincidono sui prefissi.

Q90 contiene 330.429 AST `per_number_score`; Q7 1.023 AST `quintet_score`. I due output non sono direttamente confrontabili: unità, feature space e metriche sono differenti. La prossima implementazione deve ricalcolare entrambi su cutoff comuni e mantenere endpoint separati.

## Prospettico e governance

- Archivio main: 3.406 estrazioni, ultimo risultato ufficiale 12 novembre, concorso 316 (2, 4, 7, 23, 33). Il concorso 317 del 13 novembre è ancora “In programmazione / In attesa” al controllo odierno.
- Q141-A7/B11: una previsione congelata per il 13 novembre, zero esiti riconciliati; hash invariato `009f56ae414852c223a81a7d209e17bc4f94076b72556c87d15273001470a1f3`.
- Q60: 25/200 target prospettici validi; gate `INSUFFICIENT_PROSPECTIVE_CASES`, promozione non consentita.
- PR #92 è draft; il suo controllo generale `Test VinciCasa Lab` (run 43430394550) è ancora pending, quindi non lo considero superato. Il workflow D3 dedicato 43430133247 è invece concluso con successo. PR #6, #7 e #8 restano aperte e invariate; #89, #90 e #91 non sono state modificate. Nessun merge, rebase, mutazione dell'archivio, modifica ai freeze o promozione di motori.

## Prossima iterazione

Costruire un **common-source AST evaluator**: riconciliare le grammatiche Q90/Q7, ricostruire feature strict-prior su cutoff identici, deduplicare AST per semantica e misurare ridondanza/complementarità e cambi di regime. Mantenere score per numero e score per cinquina in metriche separate. La verifica prospettica B11/Q60 continua senza peek intermedio.

## Nota di governance e recupero

Per errore, una prima versione di questo report è stata creata su `main` e subito rimossa con un commit separato; il report autorevole è sul ramo D3. I due commit amministrativi restano nella storia di `main`, ma non hanno modificato archivio canonico, motori, gate o dati di previsione. La verifica successiva ha confermato che il blob dell'archivio `data/storico_daily.csv` su `main` resta `6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb`.
