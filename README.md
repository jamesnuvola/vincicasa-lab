# VinciCasa Lab · SONAR

Laboratorio statistico per VinciCasa (5 numeri distinti e crescenti da 1 a 40). L'obiettivo è verificare metodi e segnali su estrazioni successive, evitando di usare informazioni future durante i test. **Le analisi sono esplorative: non garantiscono né dimostrano la previsione delle estrazioni future.**

## Schede dell'app

| Scheda | Contenuto |
|---|---|
| **ANDAMENTO** | Ultime 15 estrazioni, grafico per posizione P1–P5, numeri annotati, variazioni rispetto all'estrazione precedente e fasce storiche. |
| **NUCLEO** | Numeri comparsi in ciascuno dei 2 o 3 mesi precedenti, per posizione. Il bordo ambra segnala gli attesi ancora non usciti nel mese corrente. |
| **RANK** | Classifiche P1–P5 con frequenza storica, ritorno e bonus attesi; i pesi sono regolabili. |
| **GIOCA** | Motore SONAR: analoghi storici, core, traiettoria e completamento. Mostra la cinquina e gli analoghi usati, con grafico delle ultime 15 estrazioni e tratto di proiezione. |
| **VERIFICA 2.0** | Walk-forward dei metodi Frequency, Return, Nucleus e Combo. Ogni target è valutato usando solo il prefisso storico disponibile prima di quell'estrazione, con benchmark Monte Carlo e statistiche per posizione e mese. |
| **TREND** | Finestre 7/14/21/30, accelerazione, persistenza, coppie, regimi e validazione walk-forward su diversi orizzonti. |
| **PROIEZIONE** | Confronto Trend + Memory, cinquina selezionata, grafico storico e rank per posizione. |
| **GRIGLIA** | Matrice dei rank per numero e posizione, con colori per fasce e indicatori del nucleo. |

## Dati e aggiornamento automatico

- Archivio canonico: `data/storico_daily.csv`, con una riga per data.
- Dati consumati dal frontend: `src/data.json`, rigenerati da `scripts/rigenera_dati.py`.
- Aggiornamento programmato: `.github/workflows/aggiorna.yml`, con due tentativi serali.
- Pubblicazione: `.github/workflows/deploy.yml` su GitHub Pages.
- Controllo qualità: `scripts/audit_dataset.py`, eseguito prima e dopo la rigenerazione dei dati.

L'audit verifica intestazione e struttura del CSV, date ISO univoche e in ordine cronologico, cinque numeri distinti e crescenti, intervalli validi per ogni posizione e coerenza fra CSV e JSON generato. Se trova dati non validi, il workflow si interrompe prima del commit automatico.

Il workflow può essere avviato anche manualmente da **Actions → Aggiornamento estrazioni → Run workflow**. Se il sito ufficiale cambia layout e il parsing non riconosce i risultati, lo script di aggiornamento termina con errore anziché aggiungere record non verificati.

## Controlli automatici

Il workflow `Test VinciCasa Lab` controlla ogni push e pull request:

1. audit dell'archivio canonico;
2. rigenerazione riproducibile di `src/data.json`;
3. audit del JSON generato;
4. build frontend con Vite.

## Metodo e limiti

**Pavimento / frequenza.** Frequenza storica di ciascun numero nella sua posizione, normalizzata rispetto al massimo della posizione. I domini posizionali validi sono P1: 1–36, P2: 2–37, P3: 3–38, P4: 4–39, P5: 5–40.

**Ritorno.** Premio decrescente dopo un'uscita, parametrizzato con il profilo storico delle distanze di ritorno. Il profilo è descrittivo: non implica che un numero sia dovuto a una certa distanza.

**Attesi / nucleo.** Numeri comparsi in ciascuno dei mesi precedenti configurati e non ancora usciti nel mese corrente. La composizione del nucleo dipende dal calendario e dallo storico disponibile.

**SONAR.** Il core viene costruito da analoghi storici con sovrapposizione di almeno tre numeri; i livelli di completamento combinano segnali di relazione, persistenza e presenza recente. È un algoritmo deterministico e sperimentale, non una probabilità calibrata.

**Validazione.** I test walk-forward ricostruiscono il punteggio usando soltanto le estrazioni precedenti al target. I risultati vanno letti insieme al benchmark casuale, alla numerosità del campione e alla variabilità fra periodi; un buon risultato storico non dimostra un vantaggio futuro.

## Sviluppo locale

Richiede Node.js 20 e Python 3.12:

```bash
pip install numpy
python scripts/audit_dataset.py
python scripts/rigenera_dati.py
python scripts/audit_dataset.py --check-json
npm install
npm run dev
```

Per una build di produzione:

```bash
npm run build
```
