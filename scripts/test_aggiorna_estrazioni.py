#!/usr/bin/env python3
"""Regression tests for strict, row-bound VinciCasa archive parsing."""
import re
import unittest

from aggiorna_estrazioni import MESI, parse_estrazioni


def legacy_window_parse(html):
    """The pre-Q132 parser, retained only to demonstrate the look-ahead defect."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    out = {}
    pattern = re.compile(
        r"(\d{1,2})\s+(Gennaio|Febbraio|Marzo|Aprile|Maggio|Giugno|Luglio|"
        r"Agosto|Settembre|Ottobre|Novembre|Dicembre)\s+(\d{4})",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        day, month, year = int(match.group(1)), match.group(2).lower(), int(match.group(3))
        date = f"{year}-{MESI[month]:02d}-{day:02d}"
        window = text[match.end():match.end() + 260]
        tokens = [int(x) for x in re.findall(r"\b(\d{1,2})\b", window)]
        tokens = [value for value in tokens if 1 <= value <= 40]
        for i in range(len(tokens) - 4):
            candidate = tokens[i:i + 5]
            if all(candidate[j] < candidate[j + 1] for j in range(4)):
                out.setdefault(date, candidate)
                break
    return out


class ArchiveParserTests(unittest.TestCase):
    def test_valid_result_row_is_accepted(self):
        html = """
        <table><tr>
          <td>Concorso Nº 314 del 10 Novembre 2026</td>
          <td><span>1</span><span>7</span><span>11</span><span>22</span><span>25</span></td>
          <td><a>Dettagli</a></td>
        </tr></table>
        """
        self.assertEqual(parse_estrazioni(html), {"2026-11-10": [1, 7, 11, 22, 25]})

    def test_pending_row_does_not_consume_nearby_numbers(self):
        html = """
        <table><tr>
          <td>Concorso Nº 315 del 11 Novembre 2026</td>
          <td>In programmazione</td><td>In attesa</td>
        </tr></table>
        <div>Promozione numerica: 1 21 22 27 29</div>
        """
        self.assertEqual(legacy_window_parse(html), {"2026-11-11": [1, 21, 22, 27, 29]})
        self.assertEqual(parse_estrazioni(html), {})

    def test_script_numbers_are_not_attached_to_pending_row(self):
        html = """
        <table><tr>
          <td>Concorso Nº 315 del 11 Novembre 2026</td>
          <td>In programmazione</td><td>In attesa</td>
        </tr></table>
        <script>window.otherWidget = [1, 21, 22, 27, 29];</script>
        """
        self.assertEqual(parse_estrazioni(html), {})

    def test_result_cell_must_contain_exactly_five_numbers(self):
        html = """
        <table><tr>
          <td>Concorso Nº 315 del 11 Novembre 2026</td>
          <td>1 7 11 22 25 29</td><td>Dettagli</td>
        </tr></table>
        """
        self.assertEqual(parse_estrazioni(html), {})

    def test_result_must_be_distinct_sorted_and_in_range(self):
        for numbers in ("1 7 7 22 25", "7 1 11 22 25", "1 7 11 22 41"):
            with self.subTest(numbers=numbers):
                html = (
                    "<table><tr><td>Concorso Nº 315 del 11 Novembre 2026</td>"
                    f"<td>{numbers}</td><td>Dettagli</td></tr></table>"
                )
                self.assertEqual(parse_estrazioni(html), {})

    def test_conflicting_duplicate_date_fails_closed(self):
        html = """
        <table>
          <tr><td>Concorso Nº 314 del 10 Novembre 2026</td><td>1 7 11 22 25</td></tr>
          <tr><td>Concorso Nº 314 del 10 Novembre 2026</td><td>1 8 11 22 25</td></tr>
        </table>
        """
        with self.assertRaises(ValueError):
            parse_estrazioni(html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
