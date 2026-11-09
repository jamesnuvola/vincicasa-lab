# Q86-DIR-01 — checkpoint di accettazione

Data: 10 novembre 2026  
Stato: **VALIDATED_PENDING_HUMAN_REVIEW** (non promosso).

## Archivio e protocollo

- Archivio canonico: 3.402 estrazioni, 2017-07-17 → 2026-11-08.
- SHA-256 archivio: `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`.
- Target prior-only: 3.202; Discovery 1.921, Validation 640, storico Blind OOS 641.
- 8 modelli: 4 controlli e 4 operatori direzionali a peso fisso 0,20.
- 72 test exact-null con Holm globale; 32 confronti paired con moving-block bootstrap (blocco 20, 2.000 repliche) e Holm.
- Ogni target usa esclusivamente le estrazioni precedenti. Il ledger conserva 40 coseni nodali, 40 coseni delle righe grafo, 40 prodotti di coerenza e otto ranking completi.

## Risultato selezionato solo su Discovery

Operatore: `DYN::NODE_DIRECTIONAL_ALIGNMENT`.

| Split | Top20 direzionale | Equal42 | Delta |
|---|---:|---:|---:|
| Discovery | 2,526288 | 2,515357 | +0,010932 |
| Validation | 2,482813 | 2,498438 | −0,015625 |
| Blind OOS storico | 2,547582 | 2,546022 | +0,001560 |

Blind OOS aggiuntivo:
- Top5: 0,624025 contro 0,608424.
- Top10: 1,230889 contro 1,244930.
- Rank medio dei cinque numeri effettivi: 20,460842 contro 20,481747 (più basso è migliore).
- Delta Top20 paired 95% CI: [−0,026521; +0,029641].
- p paired grezzo 0,918; Holm paired 1,000; Holm exact-null 1,000.
- Gate primario: **NOT_MET** (richiedeva lift Top20 ≥0,10, CI inferiore >0 e significatività corretta).

Le 72 prove exact-null e le 32 prove paired non hanno evidenziato un vantaggio statisticamente significativo. Il piccolo delta Blind OOS è compatibile con zero e non supera il gate. La Validation è negativa.

## Verifiche e recupero

- 10/10 test unitari Q86-DIR superati.
- 3.202 cutoff prior-only verificati.
- 25.616 ranking completi ricalcolati.
- 384.240 valori direzionali ricalcolati e confrontati; coerenza nodo-grafo verificata come prodotto dei coseni.
- Hash e medie direzionali ricalcolati; replay Discovery e metriche riprodotti.
- Artefatti catalogo, ledger compresso, report, manifest, checkpoint e validation persistiti; il workflow ha confrontato i byte Git riletti con i file locali.
- Acceptance validator: PASS.
- Replay read-only del commit sorgente `b87137f021fc38e180281f06ccd0a7d3f84f4ee3`: PASS.
- CI generale sullo stesso commit: run `42724337793`, PASS.
- Workflow Q86-DIR di replay read-only: run `42724337711`, PASS.
- Un primo tentativo si era fermato con KeyError `node_percentile`: la diagnostica per regimi è stata corretta usando le medie dei coseni firmati e le classi negative/neutrali/positive; sono stati aggiunti test dei confini. Il successivo walk-forward e il replay completo sono riusciti.

## Interpretazione e limiti

La direzione dei vettori non ha aggiunto un vantaggio predittivo misurabile rispetto a Equal42. Il modello è leggermente sopra sul Top20 storico Blind OOS, ma l'effetto è quasi nullo, l'intervallo include zero e i p-value corretti sono 1,000. La Validation è sotto baseline. Non va promosso.

Il segmento storico Blind OOS è già stato osservato in ricerche SONAR precedenti: è esplorativo, non un holdout vergine. Il grafo è un descrittore statistico di co-occorrenza, non una forza fisica. Il superamento dei replay certifica la riproducibilità computazionale, non la predittività.

## Prossima azione

1. Revisione umana della definizione dei coseni, della standardizzazione dei segnali e dei risultati negativi.
2. Non ritoccare alpha o soglie sullo storico Blind OOS.
3. Se si procede, preregistrare un solo esperimento successivo che studi il ritardo/fase tra variazioni nodali e variazioni del grafo (non aggiungere molti operatori ad hoc), mantenendo il medesimo split e una nuova conferma prospettica.
4. Lasciare il ciclo in stato **VALIDATED_PENDING_HUMAN_REVIEW**. Nessuna promozione, nessun freeze modificato, nessun merge automatico.

Nota di nomenclatura: Q86-DIR è separato dal Q86 della grammatica di formule a sei variabili già presente in un altro ramo.
