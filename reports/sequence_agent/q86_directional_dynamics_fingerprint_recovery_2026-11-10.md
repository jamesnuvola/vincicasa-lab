# Q86-DIR — recupero fingerprint floating-point

Data: 10 novembre 2026  
Stato: correzione del validatore verificata; risultati e ledger non modificati.

## Evento

Dopo la persistenza Q86-DIR, il replay read-only sul commit `b87137f021fc38e180281f06ccd0a7d3f84f4ee3` era passato. Un replay successivo, su un commit che aggiungeva soltanto il checkpoint documentale, si è fermato alla prima riga per discordanza di `field_state_sha256`.

## Causa radice

Il fingerprint upstream è calcolato come SHA-256 dei byte grezzi di una matrice float64 (`column_stack([features, graph_signal])`). Non è una serializzazione canonica decimale e può variare tra contesti di replay floating-point anche quando le classifiche e i valori numerici restano equivalenti. Il progetto aveva già incontrato questo limite nei replay Q84/Q85: il digest float non deve essere usato da solo come gate di correttezza.

## Correzione

Il validatore conserva entrambi i digest nel ledger e ne controlla il formato esadecimale, ma li tratta come fingerprint diagnostici. I gate vincolanti restano:
- archivio SHA-256 e Git blob SHA-1;
- 3.202 cutoff strettamente precedenti al target;
- 25.616 ranking completi, verificati come permutazioni e riprodotti esattamente;
- 384.240 valori direzionali riprodotti numericamente entro 1e-9;
- prodotto di coerenza nodo-grafo;
- medie direzionali;
- selezione Discovery;
- 72 test exact-null e 32 paired con Holm;
- hash e byte count dei file persistiti.

Dopo la correzione, il replay read-only Q86-DIR sul commit `6f888d707e916a0c2622a401788deaa3009937ba` è PASS; la CI generale sullo stesso head è PASS. Il report, il ledger e la validation persistiti non sono stati riscritti.

## Limite e prossima azione

Un fingerprint diagnostico non dimostra equivalenza matematica; per questo il controllo sostanziale usa vettori e ranking ricalcolati. Mantenere i digest per tracciare differenze, ma non bloccare un replay quando i dati strutturati e i ranking superano i controlli registrati. Nessuna promozione: resta necessaria la revisione umana e un'eventuale conferma prospettica.
