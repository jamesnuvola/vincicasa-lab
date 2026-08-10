#!/usr/bin/env python3
"""
Scarica le estrazioni piu' recenti da vincicasa.it e appende al CSV quelle
non ancora presenti. Pensato per girare ogni sera su GitHub Actions; dopo di
lui va lanciato scripts/rigenera_dati.py per aggiornare src/data.json.

Solo libreria standard (urllib), nessuna dipendenza.
Se il sito cambia layout e il parsing non trova nulla, esce con errore
chiaro SENZA toccare il CSV.
"""
import csv, os, re, sys, urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(BASE, "data", "storico_daily.csv")

URLS = [
    "https://www.vincicasa.it/archivio-estrazioni",
    "https://www.vincicasa.it/",
]
MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4,
    "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
    "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
UA = "Mozilla/5.0 (compatible; vincicasa-lab/1.0; aggiornamento archivio personale)"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_estrazioni(html):
    """Ritorna {data_iso: [n1..n5]} per ogni blocco 'g Mese aaaa' seguito,
    nel testo linearizzato, da 5 numeri 1-40 strettamente crescenti."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    out = {}
    pat = re.compile(
        r"(\d{1,2})\s+(Gennaio|Febbraio|Marzo|Aprile|Maggio|Giugno|Luglio|"
        r"Agosto|Settembre|Ottobre|Novembre|Dicembre)\s+(\d{4})",
        re.IGNORECASE,
    )
    for m in pat.finditer(text):
        g, mese, anno = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        data = f"{anno}-{MESI[mese]:02d}-{g:02d}"
        finestra = text[m.end(): m.end() + 260]
        token = [int(x) for x in re.findall(r"\b(\d{1,2})\b", finestra)]
        token = [t for t in token if 1 <= t <= 40]
        cinq = None
        for i in range(len(token) - 4):
            c = token[i:i + 5]
            if all(c[j] < c[j + 1] for j in range(4)):
                cinq = c
                break
        if cinq and data not in out:
            out[data] = cinq
    return out


def main():
    rows = list(csv.DictReader(open(CSV)))
    ultima = max(r["data"].strip() for r in rows)
    print(f"Ultima estrazione nel CSV: {ultima}")

    trovate = {}
    errori = []
    for url in URLS:
        try:
            trovate.update(parse_estrazioni(fetch(url)))
            if trovate:
                break
        except Exception as e:  # noqa: BLE001
            errori.append(f"{url}: {e}")

    if not trovate:
        print("Parsing fallito su tutti gli URL:")
        for e in errori:
            print("  ", e)
        print("Nessuna estrazione riconosciuta: probabile cambio di layout del sito.")
        sys.exit(1)

    nuove = sorted((d, n) for d, n in trovate.items() if d > ultima)
    if not nuove:
        print(f"Nessuna nuova estrazione (il sito riporta fino al {max(trovate)}).")
        return

    with open(CSV, "a", newline="") as f:
        w = csv.writer(f)
        for d, n in nuove:
            w.writerow([d] + n)
            print(f"Aggiunta: {d} -> {n}")
    print(f"{len(nuove)} estrazioni aggiunte al CSV.")


if __name__ == "__main__":
    main()
