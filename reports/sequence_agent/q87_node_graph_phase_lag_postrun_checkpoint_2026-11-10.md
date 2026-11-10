# Q87 — risultati del primo walk-forward e stato di persistenza

Data: 10 novembre 2026. Stato: **ACCEPTANCE PASS; EXACT-HEAD READ-ONLY REPLAY PENDING**.

## Protocollo eseguito

- Archivio congelato: 3.402 estrazioni, 2017-07-17 → 2026-11-08.
- 3.202 target con 200 o più estrazioni strettamente precedenti.
- Split cronologico: Discovery 1.921, Validation 640, storico Blind OOS 641.
- 12 modelli: 8 controlli Q86-DIR e 4 operatori di fase Q87.
- Finestra di 80 transizioni; lag 1, 2, 3; minimo 30 coppie; alpha fisso 0,20.
- 108 test exact-null con Holm globale; 32 confronti paired con moving-block bootstrap (blocco 20, 2.000 repliche) e Holm.
- 38.424 ranking e 512.320 valori di fase riprodotti dal validatore.

## Risultati

Selezione effettuata soltanto su Discovery: `DYN::BIDIRECTIONAL_PHASE_COHERENCE`.

| Split | Q87 Top20 | Equal42 Top20 | Delta |
|---|---:|---:|---:|
| Discovery | 2,519521 | 2,515357 | +0,004165 |
| Validation | 2,506250 | 2,498438 | +0,007813 |
| Blind OOS storico | 2,531981 | 2,546022 | −0,014041 |

Blind OOS:
- Top5: 0,616225 contro 0,608424.
- Top10: 1,252730 contro 1,244930.
- Top20: 2,531981 contro 2,546022.
- Delta paired Top20: −0,014041; IC95% [−0,032761; +0,006279].
- p paired grezzo 0,226; Holm paired 1,000; Holm exact-null 1,000.
- Gate primario: **NOT_MET**.

Nessun vantaggio predittivo dimostrato. Il piccolo miglioramento Top5/Top10 non compensa il Top20 sotto baseline e non supera i test corretti.

## Accettazione e persistenza

Il workflow Q87 run `42727011446` ha completato con successo:
- 10/10 test unitari;
- walk-forward completo;
- acceptance validator PASS;
- 3.202 cutoff strettamente precedenti;
- replay di 38.424 ranking e 512.320 valori di fase;
- 108 test exact-null e 32 paired;
- commit append-only `667cb82880dd40dce29bcda36cdee9a165564b30`;
- confronto byte-per-byte dei sei artefatti riletti da Git.

Il CI generale sul commit sorgente prima della persistenza, run `42727011309`, è PASS.

Dopo la persistenza, GitHub ha creato i run `42727378770` (Q87 read-only) e `42727378338` (CI generale) con stato `action_required` e zero job: non li considero eseguiti. Questo checkpoint documentale è un nuovo commit sul ramo Q87 per richiedere una nuova esecuzione PR-synchronize sul head aggiornato. L'esito del replay read-only e del CI sul nuovo head resta da verificare.

## Interpretazione e prossima azione

Il test della fase basata su magnitudini non ha aggiunto informazione utile al ranking. Non modificare finestra, lag o alpha per inseguire il risultato storico.

Dopo il replay read-only e il CI sul preciso head:
1. mantenere Q87 come risultato esplorativo negativo;
2. sottoporre a revisione umana la definizione delle correlazioni e il loro significato;
3. se la revisione approva un altro esperimento, preregistrare un singolo test di trasferimento direzionale nodo→grafo basato su proiezioni firmate, senza riutilizzare il Blind OOS come conferma;
4. riservare una vera valutazione confermativa a nuove estrazioni prospettiche.

Nessun motore promosso, nessun freeze modificato, nessuna shadow insertion e nessun merge automatico.
