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
from html.parser import HTMLParser

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


class _ArchiveTableParser(HTMLParser):
    """Collect text from table cells; ignore scripts and unrelated page text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "tr":
            self.row = []
            self.cell = None
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.cell is not None:
                self.row.append(" ".join(" ".join(self.cell).split()))
                self.cell = None
            self.rows.append(self.row)
            self.row = None


_DATE_RE = re.compile(
    r"(\d{1,2})\s+(Gennaio|Febbraio|Marzo|Aprile|Maggio|Giugno|Luglio|"
    r"Agosto|Settembre|Ottobre|Novembre|Dicembre)\s+(\d{4})",
    re.IGNORECASE,
)
_RESULT_CELL_RE = re.compile(r"\s*\d{1,2}(?:\s+\d{1,2}){4}\s*")


def parse_estrazioni(html):
    """Return draws only when date and exactly five numbers share one table row.

    The result must occupy the second cell by itself. Pending labels, adjacent
    rows, scripts, navigation text, and arbitrary numbers elsewhere on the page
    can never be attached to a contest date.
    """
    parser = _ArchiveTableParser()
    parser.feed(html)
    parser.close()

    out = {}
    for cells in parser.rows:
        if len(cells) < 2:
            continue
        match = _DATE_RE.search(cells[0])
        if not match:
            continue

        day, month, year = int(match.group(1)), match.group(2).lower(), int(match.group(3))
        data = f"{year}-{MESI[month]:02d}-{day:02d}"
        result_cell = cells[1]
        if not _RESULT_CELL_RE.fullmatch(result_cell):
            continue

        nums = [int(x) for x in re.findall(r"\d{1,2}", result_cell)]
        if (
            len(nums) != 5
            or len(set(nums)) != 5
            or nums != sorted(nums)
            or any(n < 1 or n > 40 for n in nums)
        ):
            continue

        if data in out and out[data] != nums:
            raise ValueError(f"conflicting result rows for {data}: {out[data]} vs {nums}")
        out[data] = nums

    return out

def merge_page_results(target, page_results):
    """Merge page results without silently replacing conflicting dates."""
    for data, numbers in page_results.items():
        if data in target and target[data] != numbers:
            raise ValueError(f"conflicting source results for {data}: {target[data]} vs {numbers}")
        target[data] = numbers


def page_contains_new_draw(page_results, latest_date):
    """A page is a valid stopping point only if it contains a date newer than the CSV."""
    return any(data > latest_date for data in page_results)


def main():
    rows = list(csv.DictReader(open(CSV)))
    ultima = max(r["data"].strip() for r in rows)
    print(f"Ultima estrazione nel CSV: {ultima}")

    trovate = {}
    errori = []
    for url in URLS:
        try:
            page_results = parse_estrazioni(fetch(url))
            merge_page_results(trovate, page_results)
            # Do not stop on a stale archive page that contains only old draws:
            # continue to the homepage and other configured sources.
            if page_contains_new_draw(page_results, ultima):
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
