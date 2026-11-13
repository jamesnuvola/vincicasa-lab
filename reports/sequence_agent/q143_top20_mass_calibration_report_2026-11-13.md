# Q143 — Top20 score-mass calibration

**Stato:** calcolo locale completato; CI e readback remoto da verificare.  
**Base:** 4a55fb7da216bd3850b79f862bf10b2cbcafa968 · **Dati:** 3.406 estrazioni fino al 12/11/2026.

## Risultati

| Split | Target | OLS MSE | Rolling MSE | Uniforme MSE | OLS MAE | Rolling MAE | Uniforme MAE |
|---|---:|---:|---:|---:|---:|---:|---:|
| Discovery | 1.683 | 1,13666 | 1,13720 | 1,13414 | 0,88210 | 0,88858 | 0,88800 |
| Validation | 561 | 1,09797 | 1,10179 | 1,09848 | 0,85817 | 0,87145 | 0,87077 |
| Blind OOS | 562 | **1,15170** | **1,14501** | **1,13968** | **0,89241** | **0,89089** | **0,88968** |

Nel Blind OOS la correlazione score-mass/hit Top20 è **+0,0187**, sostanzialmente nulla. La media delle pendenze rolling è -0,614; il 59,96% è negativo.

| Endpoint | Improvement | IC bootstrap 95% | p grezzo | p Holm (4) |
|---|---:|---:|---:|---:|
| MSE vs rolling mean | -0,00669 | [-0,01419; -0,00072] | 0,03760 | 0,15039 |
| MAE vs rolling mean | -0,00151 | [-0,00448; +0,00120] | 0,32768 | 0,55147 |
| MSE vs uniforme | -0,01202 | [-0,02357; -0,00153] | 0,04630 | 0,15039 |
| MAE vs uniforme | -0,00273 | [-0,00713; +0,00148] | 0,27574 | 0,55147 |

Il modello è peggiore di entrambe le baseline su tutti gli endpoint. I due test MSE hanno p grezzi inferiori a 0,05, ma non superano Holm. Nessun vantaggio dimostrato.

## Integrità e criticità
- 3.206 record score/hit con prefisso stretto; 2.806 valutati dopo calibrazione.
- Il ranking corrente riproduce esattamente il freeze APP del 13/11.
- Ledger con target e cutoff per ogni riga.
- Il report active-engine segnala 19/20 freeze con Top20 esatta e un mismatch il 25/10, pur con Top5 set coincidente. Mancano hash sorgente/versione per riga: causa non attribuibile con certezza.
- 43 freeze shadow FROZEN_PENDING per il target corrente.
- Q60: 25/200; promozione non consentita.
- Blind OOS esposto alla ricerca precedente; nessuna pretesa confermativa.

## Prossima azione
Preservare i 43 freeze del 13/11; riconciliare gli esiti solo dopo la pubblicazione ufficiale e in modalità append-only. Aggiungere model_version e app_source_blob_sha solo alle nuove righe future. Continuare Q60 verso 200 coppie complete.
