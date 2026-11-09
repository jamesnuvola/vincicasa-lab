# SONAR Q84–Q85 — checkpoint di riconciliazione e prossima ipotesi

Data: 9 novembre 2026  
Ambito: storico esplorativo, nessuna promozione del motore.

## Stato verificato

### Q84 — Campo 40 nodi × 6 caratteristiche

- Archivio: 3.402 estrazioni, 2017-07-17 → 2026-11-08.
- Walk-forward: 3.202 target; 1.921 Discovery, 640 Validation, 641 Blind OOS.
- 14 modelli (2 baseline + 12 candidati di campo), 44.828 rank-vector verificati.
- Validatore Q84: PASS; 126 test nella famiglia globale Holm.
- Selezione Discovery: `FIELD::REVERSION::A20`.
- Top20 Validation: 2,4953 contro 2,4984 di `BASE::EQUAL42` (delta −0,0031).
- Top20 Blind OOS: 2,5413 contro 2,5460 (delta −0,0047).
- Top5 Blind OOS: 0,6427 contro 0,6084; bootstrap paired p=0,057, IC95% [0; 0,0671]. Segnale non conclusivo e non sufficiente per il gate primario.
- I p-value esatti della famiglia globale Holm non hanno prodotto candidati significativi.

### Q85 — Accelerazione causale del campo e del grafo

Ipotesi preregistrata: modulare l'intensità del segnale di reversione o del grafo usando il percentile causale dell'accelerazione del campo nodale o del grafo. Il percentile usa al massimo 300 stati precedenti; i primi 100 stati usano il valore neutro 0,5. Quattro operatori adattivi, alpha vincolato a [0,10; 0,30].

- Walk-forward: 3.202 target, stessi split cronologici.
- 8 modelli: 2 baseline, 2 controlli fissi, 4 operatori adattivi.
- 7 test automatici originari più il test aggiunto sullo schema del ledger: il job Q85 conclusivo ha superato il passo test.
- 72 test esatti con Holm globale; 32 confronti paired con moving-block bootstrap (blocco 20, 2.000 repliche) e Holm separato.
- 25.616 rank-vector ricalcolati e confrontati; 3.202 cutoff strettamente precedenti; archivio SHA-256 `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`.
- Validatore Q85: PASS. Artefatti persistiti con commit `ceb6ca3915257c3c781b10949e75ac12c3dc1dd5`; il workflow ha riletto i sei file dal commit e verificato i byte con `cmp`.

Selezione effettuata solo su Discovery: `DYN::GRAPH_ACCEL_DOWN`.

| Split | Q85 selezionato Top20 | Equal42 Top20 | Delta |
|---|---:|---:|---:|
| Discovery | 2,5252 | 2,5154 | +0,0099 |
| Validation | 2,5141 | 2,4984 | +0,0156 |
| Blind OOS | 2,5226 | 2,5460 | −0,0234 |

Sul Blind OOS:
- Top5: 0,5975 contro 0,6084.
- Top10: 1,2356 contro 1,2449.
- Top20: 2,5226 contro 2,5460.
- Delta paired Top20: −0,0234; IC95% moving-block [−0,0546; +0,0062]; p raw 0,152; p Holm 1,000.
- p Holm esatto Top20: 1,000.
- Gate primario: NOT_MET.

Diagnostica descrittiva, non confermativa:
- In 5 dei 7 blocchi temporali Blind OOS da circa 100 target il delta Top20 selezionato−Equal42 è negativo; 2 positivi, 1 nullo.
- Per il regime di accelerazione del grafo, il delta Top20 Blind OOS è −0,0478 nel regime basso (209 target), −0,0356 nel medio (225) e +0,0145 nell'alto (207). Questi sottogruppi non hanno superato un test inferenziale dedicato e non vanno trattati come evidenza predittiva.

## Cause radice e correzioni durante Q85

1. Il primo test unitario ha rilevato l'arrotondamento floating-point `0.30000000000000004`; alpha è stata saturata esplicitamente nell'intervallo [0,10; 0,30].
2. Il primo walk-forward ha poi rilevato una divergenza tra i nomi delle variabili di transizione e le colonne del ledger. È stata introdotta una mappatura esplicita e un test di schema.
3. La riesecuzione conclusiva ha superato test, walk-forward, replay del validatore, persistenza e verifica byte-per-byte.

## Limiti e stato di promozione

- Q84 e Q85 sono analisi storiche esplorative: il segmento Blind OOS è già stato consultato in precedenti ricerche SONAR e non è un holdout vergine.
- Q85 PASS certifica la correttezza e riproducibilità degli artefatti, non l'efficacia predittiva.
- Nessuna delle due famiglie ha dimostrato un miglioramento stabile rispetto a Equal42.
- Nessun motore promosso; nessun freeze prospettico o storico modificato.
- PR #26 resta draft e richiede revisione umana.
- I workflow sul commit bot che ha persistito Q85 risultano `action_required` senza job avviati; il CI sul preciso head post-persistenza non è quindi ancora attestato come PASS.
- Q92 resta separato: l'aggregatore del vecchio walk-forward fallì per import mancante di `heapq`; la correzione è presente in PR #23 e la CI generale sul commit corretto è passata, ma il walk-forward/aggregazione completa Q92 non è stato rilanciato e accettato.

## Prossima ipotesi quantitativa — Q86: cinematica direzionale

Q85 ha testato soprattutto l'ampiezza RMS delle accelerazioni. Questa compressione elimina direzione e geometria della traiettoria. Il prossimo test dovrebbe conservare, per ciascuno dei 40 numeri:

- il vettore di velocità nelle 6 caratteristiche del nodo;
- il vettore di accelerazione;
- il coseno firmato fra velocità e accelerazione (allineamento o inversione);
- l'allineamento fra velocità e accelerazione della riga corrispondente del grafo 40×40;
- la coerenza nodo-grafo come prodotto dei due allineamenti.

Quattro operatori da preregistrare con peso fisso 0,20: allineamento nodale, inversione/curvatura nodale, allineamento del grafo e coerenza nodo-grafo. Nessuna soglia o peso da ottimizzare sul Blind OOS. Stessi split, baseline, famiglie Holm e paired block bootstrap. La selezione resta solo su Discovery; il Blind storico rimane esplorativo. La conferma vera dovrà essere prospettica.

**Prossima azione:** eseguire Q86 solo dopo aver ottenuto la revisione/approvazione dei workflow sul preciso head Q85 e mantenere separata la conferma prospettica.
