# SONAR — adattamento operativo della metodologia NS166 e strategia posizione-vs-joint

**Data:** 2026-11-08  
**Stato:** documento metodologico di ricerca; ipotesi non testate, nessuna promozione.  
**Fonte:** OpenAI, *Finite Time Blowup for Navier–Stokes* (166 pp.; PDF ufficiale).

## A. Sintesi dello studio: architettura che vale la pena conservare

Il paper costruisce un campo fluido 3D incomprimibile per equazioni forzate. Il procedimento è specifico della PDE: leading self-similar profile, residual momentum/stress, pulse/oscillatory realization, mean corrections, residual improvement, localization e smooth force. L'idea trasportabile per SONAR non è la formula Navier–Stokes né il forcing, ma il rigore di una pipeline: definire un oggetto-base, quantificare un residuo, costruire una correzione con un meccanismo esplicito, aggiornare il residuo dopo la correzione, controllare invarianti/constraints e provare convergenza/robustezza.

**Non trasferire letteralmente:** incompressibility, pressure, velocity field, stress tensor, PDE terms, spatial waves, energy cancellation. Sono quantità fisiche non definite nel dominio delle cinquine.

## B. Due ipotesi da confrontare, non da scegliere per intuizione

### B1. Modello marginale per posizione (P1…P5)

Per ogni cut-off temporale t, il training usa solo estrazioni precedenti. Si stima una distribuzione marginale per la posizione ordinata k, (p_k(n|history_t)). Le correzioni del residuo sono specifiche per posizione e condizione/regime.

**Pro:** può isolare strutture statistiche diverse delle order statistics; diagnostica chiara e metriche per posizione; se una posizione è più prevedibile può migliorare hit rate marginale.  
**Contro:** le cinque marginali non sono un modello joint. Campionarle indipendentemente può generare numeri duplicati o violare l'ordine; scegliere il top marginale per ciascuna non massimizza necessariamente la probabilità della cinquina né il numero di hits congiunti.

### B2. Modello joint della cinquina per estrazione

Si modella l'oggetto completo come un set/cinquina ordinata (Y_t=(P1,…,P5)), imponendo valori distinti e crescente. Residuo e correzione operano sul forecast joint, non su cinque forecast separati.

**Pro:** ottimizza direttamente obiettivi ticket-level, rappresenta dipendenze tra posizioni e combinazioni; rispetta vincoli strutturali nativamente.  
**Contro:** spazio di output più grande e più difficile da stimare; rischio overfit, minore potenza statistica con campioni limitati; attribution of improvement meno semplice.

### B3. Strategia raccomandata: ibrido marginali + joint constraint (test comparativo)

Non decretare a priori una vittoria. Costruire in parallelo:
1. **M0:** baseline uniforme legale;
2. **M1:** baseline motore SONAR attivo, congelata;
3. **M2:** marginali position-specific P1…P5, poi ricostruzione con vincolo crescente/distinto;
4. **M3:** modello joint diretto/conditional autoregressive con vincolo P1<P2<P3<P4<P5;
5. **M4:** ibrido che usa marginals come leading profile e un correttore joint per residui/dependenze.

Per ciascuno, stessi cut-off cronologici e stessi draw target. La variante non può aggiornare pesi/parametri con l'estrazione target o con il blind set.

## C. Metrica primaria: distinguere hits e probabilità

L'obiettivo dichiarato è aumentare il numero di numeri indovinati in una draw. Misurare in primo luogo il numero di intersezioni (H_t=|pred_t\cap Y_t|) (media, distribuzione e rate di 2/3/4/5 hits), ma non usare questo solo criterio per fitting: anche precisione top-k marginale e probabilità joint/log-loss/Brier, calibrazione e confronto appaiato con M0/M1 sono necessarie per evitare ottimizzazione casuale. Definire prima di test metriche, cutoffs, comparatori e multiple-testing correction.

## D. Adattamento residual-style

Per ogni cutoff:
- congelare il leading profile da passato;
- calcolare residuo probabilistico su validazione cronologica interna;
- progettare una correzione con rationale esplicito (posizione/regime/dependence); niente feature decorative chiamate «stress» o «fluid» senza un significato matematico;
- applicare correction to forecast, re-compute residual after update;
- selezionare intensità e complessità in nested walk-forward;
- congelare e registrare variante, hash/script, parametri, cutoff;
- valutare blind/OOS una sola volta e poi prospectively.

Se il residuo è rumoroso e non offre segnale stabile, non aggiungere una correzione. Promozione solo se improvement è robust, calibrated and significant after family-wise/FDR controls.

## E. Analogia con movimento delle folle

I modelli fluid-dynamics per folle descrivono un sistema spaziale con densità, velocità, interazioni locali, boundary conditions e traiettorie. VinciCasa, al contrario, è una sequenza di draw discrete e normalmente indipendenti; l'ordine P1…P5 è l'ordine statistico dei valori sortati, non un flusso temporale o spaziale. Perciò l'analogia crowd-flow non giustifica un campo fluido per i numeri. Potrebbe solo motivare una matematica generica di sistemi collettivi se venisse definita una mappa verificabile, che oggi manca.

## F. Decisione attuale e task successivi

**Scelta di ricerca:** ibrido, con esperimenti comparativi marginal vs joint vs hybrid; non adottare come superiore prima dei test. Il modello joint è il target più coerente per l'obiettivo di hits-per-draw, mentre marginal per posizione è più interpretabile e potrebbe identificare subproblemi più apprendibili. La raccomandazione è pipeline in due stadi, ma valida solo se walk-forward mostra vantaggio.

Task:
1. Audit del motore attivo, forecast log e storico canonico.
2. Eseguire PSR01 per diagnosticare distribuzioni per posizione (not predictive promotion).
3. Definire un protocollo preregistrato M0–M4, con nested walk-forward, metriche ticket and probabilistic, dependence-aware uncertainty, correction multiple testing.
4. Se l'ambiente non può eseguire script, documentare la limitation and do not assert results; obtain an execution runner/repository action.
5. Report each test: data span, draw count, forecast snapshot, code SHA, metric, baseline, CI, status and no-promotion decision.

## Fonti
- OpenAI PDF: https://cdn.openai.com/pdf/32d9f210-8b73-45e0-91bc-82a30aef8a9a/navier-stokes.pdf
- OpenAI announcement: https://openai.com/index/navier-stokes-solution/
