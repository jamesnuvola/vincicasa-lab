# SONAR — audit di trasferibilità del metodo OpenAI Navier–Stokes (166 pp.)

**Data audit:** 2026-11-08  
**Fonte primaria:** OpenAI, *Finite Time Blowup for Navier–Stokes*, PDF ufficiale, 166 pagine.  
**Stato:** lettura strutturale e verifica dei passaggi chiave consultabili nel testo PDF; non è una replica della dimostrazione PDE né una revisione matematica indipendente. Nessun risultato di previsione VinciCasa viene qui asserito.

## 1. Verifica di che cosa sia il metodo

Il lavoro non consiste nell'applicare una formula singola «Navier–Stokes» a una serie numerica. Costruisce un campo di velocità e pressione per le equazioni incomprimibili 3D, con una forza esterna liscia progettata in modo da rendere compatibile la soluzione con una singolarità in tempo finito (teorema 1.1, pp. 1–2).

La struttura del paper, secondo indice:
- §3 proof outline (p. 6);
- §4 leading-order flow (p. 24);
- §5 correzioni del base flow a ogni ordine (p. 45);
- §6 torus ausiliario/separazione supporti oscillatori (p. 62);
- §7 realizzazione oscillatoria e correzione residual stress (p. 73);
- §8 correzioni della media a supporto compatto (p. 88);
- §9 miglioramento residuo/campo locale (p. 100);
- §10 forcing compatto e costruzione globale (p. 116);
- appendici A–C (pp. 126–164).

Idea centrale: non basta ottenere un profilo principale. Si calcola il residuo del bilancio di quantità di moto; i termini individuali possono diventare grandi, ma sono costruite cancellazioni precise perché la somma (e le sue derivate) rimanga regolare. Il profilo di base viene raffinato con correzioni; componenti oscillanti producono flussi quadratici medi che compensano lo stress residuo; successive correzioni della media e miglioramento del residuo completano la costruzione. La forza è definita come residuo finale, e la sua regolarità è una condizione essenziale (intro §2, pp. 3–5; §§5, 7–9).

## 2. Distinzione rigorosa per SONAR

| Elemento OpenAI/PDE | Trasferibilità a VinciCasa |
|---|---|
| Equazioni Navier–Stokes letterali, velocità, pressione, incomprimibilità | **Non trasferibili letteralmente**: estrazione discreta di 5 interi ordinati non è un campo fluido 3D. |
| Profili leading-order, scale e regimi | Analogia sperimentale possibile come modelli di regime/scala; non è una derivazione fisica. |
| Residuo definito rispetto a un modello-base | **Trasferibile come metodo statistico**: errore out-of-sample del modello base, analizzato per posizione e condizione. |
| Correzioni iterative del profilo-base | Possibile per addestramento cronologico: aggiungere una correzione solo se migliora il residuo su validazione temporale non usata per fit. |
| Cancellazione di stress/residui via onde e correzioni della media | Non ha corrispondenza automatica con frequenze o combinazioni di numeri. Richiede una variabile e un obiettivo statistico definiti; non usare «stress» come etichetta suggestiva. |
| Forcing esterno costruito insieme alla soluzione | **Rischio metodologico per SONAR**: adattare retrospettivamente il modello al risultato può produrre overfit/leakage. L'estrazione futura deve restare intoccata e le correzioni devono essere congelate prima del test. |
| Formalizzazione Lean della prova | Utile come analogia di controllo di specifiche e invarianti, ma non certifica un predittore statistico. |

## 3. Protocollo candidato (analogia, non formula Navier–Stokes)

1. **Definire target:** probabilità per ogni posizione P1–P5, più metriche ticket intero (cinquina ordinata/distinta).
2. **Baseline congelata:** modello SONAR attivo e baseline uniforme; acquisire il loro forecast esattamente per gli stessi cutoff.
3. **Leading profile:** costruire distribuzione condizionata per posizione/regime usando esclusivamente estrazioni precedenti al cutoff.
4. **Residuo:** errore probabilistico (preferire log-loss/Brier/calibrazione) rispetto a forecast del modello base; hit rate Top-1 resta metrica supplementare, non sufficiente.
5. **Correzioni iterative:** addestrare correzione su passato; scegliere intensità e feature in validazione walk-forward annidata; evitare di ottimizzare sulla finestra blind.
6. **Confronto appaiato:** stessa sequenza di target e stessi cutoff; intervalli di confidenza con dipendenza temporale rispettata; correzione multipli test per la famiglia completa di varianti.
7. **Blocco e prospettiva:** preregistrare la variante, congelare codice/parametri, test blind e prospettico; no promozione se il vantaggio non è stabile e calibrato.
8. **Vincoli congiunti:** le cinque marginali devono essere riconciliate con l'ordine crescente e l'unicità, senza fingere indipendenza tra posizioni.

## 4. Audit del codice disponibile

Il PSR-01 già scritto è un **baseline diagnostico**, non una realizzazione della costruzione OpenAI:
- min/max per posizione vengono calcolati solo dal passato (expanding window);
- frequency Top-1 è candidato trasparente, con tie-break deterministico;
- metriche marginali e range escape sono separate;
- lo stesso codice avverte che non produce un ticket joint né una promozione.

La sua esecuzione e validazione non sono ancora disponibili nell'ambiente di lavoro. Questo audit del paper non equivale a una verifica end-to-end di tutti i moduli SONAR attivi: per dichiarare applicazione «esatta» occorre ispezionare e riprodurre codice/forecast/ledger del motore in uso, con le versioni e cutoff registrati.

## 5. Decisione / prossime prove

**Decisione attuale: NO PROMOTION; nessuna modifica al motore attivo.**

Sequenza raccomandata:
- Audit code-level del motore attivo e di position_regime_residual_lab/ledger, identificando la formula realmente applicata e le finestre di fit.
- Eseguire PSR-01 su storico canonico, controllo integrità input e riproducibilità.
- Solo poi avviare PSR-02: residuo probabilistico per P1…P5, baselines uniform/active, walk-forward annidato, metriche proper scoring e paired tests.
- Tenere le analogie fluid-inspired come famiglie di ipotesi distinte; evitare di chiamarle Navier–Stokes «applicate» finché non si specifica la corrispondenza matematica.

## Fonti
- OpenAI, *Finite Time Blowup for Navier–Stokes*, PDF ufficiale: https://cdn.openai.com/pdf/32d9f210-8b73-45e0-91bc-82a30aef8a9a/navier-stokes.pdf
- OpenAI, annuncio e descrizione del problema: https://openai.com/index/navier-stokes-solution/
