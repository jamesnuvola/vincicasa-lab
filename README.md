# VinciCasa Lab

Laboratorio di verifica della strategia nucleo per VinciCasa (5 numeri da 40, un'estrazione al giorno).

Non prevede le estrazioni: mostra la struttura reale del gioco, costruisce un rank per posizione
con gli indicatori scelti, e **registra il rank che ogni numero aveva prima di uscire** — così la
strategia si verifica sulle estrazioni future, non a posteriori sullo storico.

## Cosa mostra

| Scheda | Contenuto |
|---|---|
| **Andamento** | Ultime 15 estrazioni, una linea tratteggiata per posizione con il numero stampato su ogni punto. Sotto: delta di ogni posizione rispetto all'estrazione precedente e fascia di P1/P5 (zona forte / media / fuori zona). |
| **Nucleo** | Nucleo per posizione (numeri usciti in tutti i 2 o 3 mesi precedenti). Bordo ambra = numero del nucleo non ancora uscito nel mese in corso. |
| **Rank** | Classifica per posizione: pavimento (frequenza storica, normalizzata 0–100) + premio RITORNO + bonus attesi. I due pesi si regolano con gli slider. |
| **Gioca** | "Gioca ora": cinquina dai top rank con vincolo d'ordine e controllo anti-affollamento. Generatore che campiona dai rank scartando pattern affollati e duplicati recenti. |
| **Verifica** | Per ogni estrazione, il rank che il numero uscito aveva **prima** dell'estrazione, calcolato con i soli dati precedenti. Verde = era in top-5, ambra = top-10. Sotto, la distribuzione per fasce di rank. |

## Aggiornamento automatico delle estrazioni

Il workflow `aggiorna.yml` gira ogni sera (19:45 e 21:30 UTC, due tentativi per coprire
ritardi e ora legale): scarica l'estrazione del giorno da vincicasa.it
(`scripts/aggiorna_estrazioni.py`), la appende a `data/storico_daily.csv`, rigenera
`src/data.json` e, se c'è una novità, fa commit e avvia il deploy su Pages. L'app si
aggiorna da sola, con nucleo, attesi e conteggi mensili ricalcolati (i conteggi si
azzerano automaticamente al cambio mese).

Al primo utilizzo conviene lanciarlo una volta a mano da **Actions → Aggiornamento
estrazioni → Run workflow** e controllare il log. Se in futuro il sito cambia layout,
lo script esce con un errore chiaro senza toccare il CSV: in quel caso va ritoccata la
regex in `aggiorna_estrazioni.py`.

## Inserimento manuale

Se l'automatismo non è ancora passato, puoi inserire data e 5 numeri in alto e premere
**Aggiungi**: l'estrazione resta salvata nel browser del dispositivo e viene ignorata
automaticamente quando la stessa data arriva dal repository (3.311 estrazioni al 09/08/2026).

## Pubblicare su GitHub Pages

1. Crea un repository nuovo e carica questi file mantenendo le cartelle
   (`src/`, `scripts/`, `data/`, `.github/workflows/`).
2. Settings → Pages → **Source: GitHub Actions**.
3. Al primo push il workflow `deploy.yml` compila con Vite e pubblica.

Non serve nulla di installato in locale: la build gira su GitHub Actions.

## Come sono calcolati i due indicatori

**Pavimento** — frequenza storica di ciascun numero nella sua posizione, su tutte le estrazioni.
Ogni posizione ha solo 36 valori possibili, non 40 (P1: 1–36, P2: 2–37, P3: 3–38, P4: 4–39, P5: 5–40):
gli altri sono impossibili per costruzione dell'ordinamento.

**Ritorno** — quando un numero esce, riceve un premio decrescente nei giorni successivi.
La finestra è la terza distanza di ritorno più frequente del suo profilo storico, tagliata a 10 giorni
per P1/P5 e 15 per P2/P3/P4. La base scende da 15 a 0 lungo la finestra, con intensità maggiore se la
finestra è corta, e riceve +3 sulle distanze a cui quel numero è storicamente rientrato almeno 3 volte.
Il premio si ricarica a ogni nuova uscita; sotto le 5 uscite storiche il numero non lo riceve.

**Attesi** — numeri del nucleo non ancora usciti nel mese in corso. Dal backtest su 105 mesi il pool
rende di più nei primi 5–10 giorni del mese (0,055 colpi per numero giocato) e cala fino a 0,044
nell'ultima settimana, quando contiene soprattutto i numeri deboli del mese.
