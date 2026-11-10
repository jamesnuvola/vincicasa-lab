# SONAR Q88 — preregistrazione del trasferimento firmato nodo-grafo

Data: 10 novembre 2026. Stato: **PREREGISTERED; WALK-FORWARD NON ANCORA ESEGUITO**.

## Stato recuperato

Q87 è verificato sul commit eee0ad895e054ed364a9d3e200813656208da55d: 3.202 target prior-only, 38.424 rank vector riprodotti, 512.320 valori di fase riprodotti, acceptance PASS, read-only replay PASS e CI generale PASS. Il candidato selezionato su Discovery (DYN::BIDIRECTIONAL_PHASE_COHERENCE) ha ottenuto Blind OOS Top20 2,531981 contro Equal42 2,546022; delta −0,014041, IC95% [−0,032761; +0,006279], paired Holm 1,000, exact-null Holm 1,000. Gate NOT_MET. Il Blind OOS storico è già esposto e resta esplorativo.

## Diagnosi e nuova ipotesi

Q87 correlava le magnitudini dei movimenti nodali e delle righe del grafo. Q86 conservava la direzione del moto nello stesso spazio, ma non proiettava il cambiamento relazionale sulle caratteristiche dei vicini.

Q88 definisce, per ogni numero i:
- node_delta_i = X_t[i] - X_(t-1)[i] (6 caratteristiche);
- graph_delta = E_t - E_(t-1) (matrice simmetrica 40×40);
- projected_graph_change_i = graph_delta[i,:] @ X_(t-1) / sqrt(39) (6 caratteristiche);
- signed_transfer_i = cosine(node_delta_i, projected_graph_change_i).

Il segnale utilizzato nel ranking è la media esponenziale delle ultime 20 transizioni osservate, decay 0,80. La transizione corrente usa esclusivamente il campo e il grafo dei dati già osservati prima del target.

## Disegno preregistrato

- Archivio congelato: 3.402 estrazioni, 2017-07-17 → 2026-11-08; SHA-1 Git blob 77ca692a6082809fcc6c471501617433ec7c36cf; SHA-256 5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b.
- 3.202 target, Discovery/Validation/Blind OOS storico 1.921/640/641.
- Tre operatori a peso fisso 0,20; nessun tuning di finestra, decay o alpha.
- 15 modelli totali: 12 controlli Q87 e 3 candidati Q88.
- 135 test exact-null con Holm globale.
- 96 confronti paired (12 comparatori × 2 split × 4 endpoint) con moving-block bootstrap, blocco 20, 2.000 repliche, Holm globale.
- Selezione soltanto su Discovery, mean Top20; tie-break mean actual rank e ID.
- Ledger completo: due vettori firmati per numero e 15 ranking completi per target.
- Validator indipendente: archive identity, cutoffs, target quintets, vettori, permutazioni 1..40, metriche, selection Discovery e famiglie Holm.

## Limiti e salvaguardie

Il Blind OOS storico è esposto: non è conferma indipendente. Il grafo rappresenta co-occorrenze statistiche, non accoppiamento fisico né causalità. L'exact-null presuppone estrazioni indipendenti; il bootstrap paired è un controllo separato della dipendenza seriale. Un eventuale risultato positivo richiede nuove estrazioni prospettiche e revisione umana.

Nessun motore promosso, nessun freeze modificato, nessuna shadow insertion, nessun merge automatico. PR #6, #7 e #8 non vengono modificati.

## Prossima azione

Eseguire test sintetici e walk-forward completo. In caso di errore, riprendere da questo checkpoint e correggere la causa radice senza cambiare ipotesi o parametri. Poi acceptance replay, persistenza append-only, byte readback, read-only replay e CI generale sul preciso head; infine revisione umana.
