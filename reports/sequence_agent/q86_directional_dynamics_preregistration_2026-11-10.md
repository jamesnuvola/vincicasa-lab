# Q86-DIR-01 — preregistrazione cinematica direzionale

Data: 10 novembre 2026  
Archivio congelato: 3.402 estrazioni, 17 luglio 2017 → 8 novembre 2026.

## Ipotesi quantitativa

Q85 misurava soprattutto l'ampiezza RMS di velocità e accelerazione. Tale riduzione elimina la direzione. Q86-DIR conserva, per ciascuno dei 40 numeri:

- coseno firmato tra velocità e accelerazione nelle 6 caratteristiche del nodo;
- coseno firmato tra velocità e accelerazione della riga corrispondente del grafo 40×40;
- coerenza nodo-grafo come prodotto dei due coseni.

I coseni sono compresi in [-1,1]; vettori nulli producono 0 neutro. Il grafo descrive associazioni storiche, non forze fisiche.

## Quattro operatori fissi

1. Reversione nodale × coseno nodale.
2. Reversione nodale × coseno nodale invertito.
3. Segnale grafo × coseno del grafo.
4. Segnale medio nodo/grafo × prodotto dei due coseni.

Tutti usano alpha fisso 0,20. Non si ottimizzano soglie o pesi su Validation o Blind OOS.

## Protocollo

3.202 target: 1.921 Discovery, 640 Validation, 641 Blind OOS. Ogni stato del target t usa esclusivamente draws[:t]. Quattro baseline/controlli e quattro operatori direzionali, 8 modelli totali. Selezione solo su Discovery.

Famiglia globale Holm: 8 modelli × 3 split × 3 endpoint = 72 test esatti. Confronti paired: 2 split × 4 comparatori × (3 endpoint + rank medio) = 32, bootstrap a blocchi mobili, lunghezza 20, 2.000 repliche e Holm.

## Limiti e salvaguardie

Il segmento storico Blind OOS è già esposto a precedenti ricerche SONAR: è esplorativo. Il replay dimostra correttezza computazionale, non capacità predittiva. Nessun freeze, forecast prospettico o motore viene modificato/promosso. Revisione umana obbligatoria. Q86-DIR è distinto dal Q86 della grammatica a sei caratteristiche.
