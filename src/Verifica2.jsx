import { useMemo } from "react";
import RAW from "./data.json";

const VALID_LO = [1, 2, 3, 4, 5];
const VALID_HI = [36, 37, 38, 39, 40];
const POS_LABELS = ["P1", "P2", "P3", "P4", "P5"];
const POS_COLORS = ["#ff4d6d", "#4fc46a", "#6a8bff", "#ffa040", "#c07ef5"];

const T = {
  bg: "#0b1020",
  card: "#141b2e",
  edge: "#26304c",
  ink: "#e9edf7",
  dim: "#8f97b0",
  amber: "#f5b942",
  ok: "#49d18a",
  warn: "#ff6b6b",
};

const METHODS = ["frequency", "return", "nucleus", "combo"];

const METHOD_LABEL = {
  frequency: "Frequency",
  return: "Return",
  nucleus: "Nucleus",
  combo: "Combo",
};

const monthKey = (d) => d.slice(0, 7);

function fmtDate(d) {
  if (!d) return "—";
  return `${d.slice(8, 10)}/${d.slice(5, 7)}/${d.slice(0, 4)}`;
}

function validNumbers(p) {
  const out = [];
  for (let n = VALID_LO[p]; n <= VALID_HI[p]; n++) out.push(n);
  return out;
}

function median(values) {
  if (!values.length) return null;
  const a = [...values].sort((x, y) => x - y);
  return a[Math.floor(a.length / 2)];
}

function prevMonth(m) {
  const [y, mo] = m.split("-").map(Number);
  return mo === 1
    ? `${y - 1}-12`
    : `${y}-${String(mo - 1).padStart(2, "0")}`;
}

function buildPrefixStats(draws, beforeIndex) {
  const prefix = draws.slice(0, beforeIndex);
  const counts = Array.from({ length: 5 }, () => ({}));
  const occurrences = Array.from({ length: 5 }, () => ({}));

  prefix.forEach((dr, i) => {
    for (let p = 0; p < 5; p++) {
      const n = dr.n[p];
      counts[p][n] = (counts[p][n] || 0) + 1;
      (occurrences[p][n] ||= []).push(i);
    }
  });

  const maxCount = counts.map((c, p) => {
    const vals = validNumbers(p).map((n) => c[n] || 0);
    return Math.max(1, ...vals);
  });

  return { prefix, counts, occurrences, maxCount };
}

function lastOccurrence(occurrences, p, n) {
  const a = occurrences[p][n];
  return a && a.length ? a[a.length - 1] : -1;
}

function returnHazard(occurrences, p, n, currentGap, beforeIndex) {
  if (currentGap < 1) return 0;

  const hist = occurrences[p][n] || [];
  if (hist.length < 2) return 0;

  const gaps = [];
  for (let j = 1; j < hist.length; j++) {
    if (hist[j] < beforeIndex) gaps.push(hist[j] - hist[j - 1]);
  }

  if (!gaps.length) return 0;

  let numerator = 0;
  let denominator = 0;

  for (const g of gaps) {
    if (g >= currentGap) denominator++;
    if (g === currentGap) numerator++;
  }

  return denominator > 0 ? (100 * numerator) / denominator : 0;
}

function nucleusFor(draws, beforeIndex, p, targetMonth) {
  const prefix = draws.slice(0, beforeIndex);
  const months = [];
  let m = targetMonth;

  for (let k = 0; k < 3; k++) {
    m = prevMonth(m);
    months.push(m);
  }

  const available = new Set(prefix.map((dr) => monthKey(dr.d)));
  if (months.some((x) => !available.has(x))) return null;

  const out = new Set();

  for (const n of validNumbers(p)) {
    const presentEveryMonth = months.every((mth) =>
      prefix.some((dr) => monthKey(dr.d) === mth && dr.n[p] === n)
    );
    if (presentEveryMonth) out.add(n);
  }

  for (const dr of prefix) {
    if (monthKey(dr.d) === targetMonth) out.delete(dr.n[p]);
  }

  return out;
}

function rankRows(scores, p) {
  const rows = validNumbers(p).map((n) => ({
    n,
    score: scores[n] || 0,
  }));

  rows.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    return a.n - b.n;
  });

  rows.forEach((r, i) => {
    r.rank = i + 1;
  });

  return rows;
}

function greedyTicket(rankedByPosition) {
  const chosen = [];
  let previous = 0;

  for (let p = 0; p < 5; p++) {
    const candidates = rankedByPosition[p]
      .filter((r) => r.n > previous)
      .filter((r) => r.n <= 40 - (4 - p));

    if (!candidates.length) return null;

    const pick = candidates[0];
    chosen.push(pick.n);
    previous = pick.n;
  }

  return chosen;
}

function actualTicketHit(ticket, target) {
  if (!ticket) return null;
  const actual = new Set(target);
  return ticket.filter((n) => actual.has(n)).length;
}

/*
 * Benchmark Monte Carlo:
 * per ogni replica generiamo una cinquina casuale uniforme 5/40 per
 * ciascun caso storico e misuriamo la media hit.
 *
 * Il benchmark viene fatto sullo stesso numero di casi del metodo:
 * 178 per Frequency/Return/Combo e 88 per Nucleus.
 *
 * RNG deterministico: i risultati restano riproducibili tra i render.
 */
function makeRng(seed) {
  let state = seed >>> 0;
  return () => {
    state = (1664525 * state + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

function randomTicket(rng) {
  const ticket = [];

  while (ticket.length < 5) {
    const n = 1 + Math.floor(rng() * 40);
    if (!ticket.includes(n)) ticket.push(n);
  }

  return ticket;
}

function monteCarloBenchmark(cases, repetitions, seed) {
  if (!cases.length) return null;

  const rng = makeRng(seed);
  const means = [];
  const oneHitRates = [];

  for (let rep = 0; rep < repetitions; rep++) {
    let totalHits = 0;
    let oneHit = 0;

    for (const c of cases) {
      const ticket = randomTicket(rng);
      const hits = actualTicketHit(ticket, c.target);
      totalHits += hits;
      if (hits >= 1) oneHit++;
    }

    means.push(totalHits / cases.length);
    oneHitRates.push((100 * oneHit) / cases.length);
  }

  means.sort((a, b) => a - b);
  oneHitRates.sort((a, b) => a - b);

  return {
    cases: cases.length,
    repetitions,
    mean: means.reduce((a, b) => a + b, 0) / means.length,
    p95: means[Math.floor(means.length * 0.95)],
    p99: means[Math.floor(means.length * 0.99)],
    low95: means[Math.floor(means.length * 0.025)],
    high95: means[Math.floor(means.length * 0.975)],
    oneHitMean:
      oneHitRates.reduce((a, b) => a + b, 0) / oneHitRates.length,
    oneHitLow95: oneHitRates[Math.floor(oneHitRates.length * 0.025)],
    oneHitHigh95: oneHitRates[Math.floor(oneHitRates.length * 0.975)],
    means,
    oneHitRates,
  };
}

function monteCarloPositionBenchmark(cases, repetitions, seed) {
  if (!cases.length) return null;

  const rng = makeRng(seed);
  const top5Counts = Array.from({ length: 5 }, () => 0);

  /*
   * Per il benchmark di rank, una classifica casuale equivale a una
   * permutazione casuale dei 36 candidati validi della posizione.
   * Qui usiamo il benchmark teorico 5/36 per ogni posizione, senza
   * simulare milioni di classifiche.
   */
  for (let p = 0; p < 5; p++) {
    top5Counts[p] = 100 * 5 / validNumbers(p).length;
  }

  return {
    repetitions,
    top5: top5Counts,
    rngUsed: rng() >= -1,
  };
}

function methodRankStats(cases, method) {
  const perPosition = [];

  for (let p = 0; p < 5; p++) {
    const ranks = cases
      .map((x) => x.ranks[method][p])
      .filter((x) => Number.isFinite(x));

    const n = ranks.length || 1;

    const rate = (k) =>
      (100 * ranks.filter((r) => r <= k).length) / n;

    const size = validNumbers(p).length;

    perPosition.push({
      mean: ranks.length
        ? ranks.reduce((a, b) => a + b, 0) / ranks.length
        : null,
      median: median(ranks),
      top1: rate(1),
      top3: rate(3),
      top5: rate(5),
      top10: rate(10),
      baselineTop5: (100 * Math.min(5, size)) / size,
    });
  }

  return perPosition;
}

function buildBlockStats(cases, method) {
  const byMonth = {};

  for (const c of cases) {
    const hit = c.ticketHits[method];
    if (!Number.isFinite(hit)) continue;

    const m = c.month;
    (byMonth[m] ||= []).push(hit);
  }

  return Object.entries(byMonth)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([month, hits]) => ({
      month,
      cases: hits.length,
      avg: hits.reduce((a, b) => a + b, 0) / hits.length,
      oneHit: (100 * hits.filter((x) => x >= 1).length) / hits.length,
    }));
}

function percentileRank(sortedValues, value) {
  if (!sortedValues.length) return null;
  let count = 0;
  for (const x of sortedValues) {
    if (x <= value) count++;
    else break;
  }
  return (100 * count) / sortedValues.length;
}

export default function Verifica2({ draws }) {
  const sourceDraws = draws && draws.length ? draws : RAW.draws;

  const result = useMemo(() => {
    const ordered = [...sourceDraws].sort((a, b) =>
      a.d.localeCompare(b.d)
    );

    const validSizes = Array.from(
      { length: 5 },
      (_, p) => validNumbers(p).length
    );

    const cases = [];

    for (let i = 1; i < ordered.length; i++) {
      const target = ordered[i];
      const stats = buildPrefixStats(ordered, i);
      const targetMonth = monthKey(target.d);

      const nucleusByPosition = Array.from({ length: 5 }, (_, p) =>
        nucleusFor(ordered, i, p, targetMonth)
      );

      const ranked = {
        frequency: [],
        return: [],
        nucleus: [],
        combo: [],
      };

      const ranks = {
        frequency: [],
        return: [],
        nucleus: [],
        combo: [],
      };

      for (let p = 0; p < 5; p++) {
        const freqScores = {};
        const returnScores = {};
        const nucleusScores = {};
        const comboScores = {};

        for (let n = VALID_LO[p]; n <= VALID_HI[p]; n++) {
          const freq = stats.counts[p][n] || 0;
          freqScores[n] =
            (100 * freq) / stats.maxCount[p];

          const last = lastOccurrence(
            stats.occurrences,
            p,
            n
          );
          const gap = last >= 0 ? i - last : 0;

          returnScores[n] =
            last >= 0
              ? returnHazard(
                  stats.occurrences,
                  p,
                  n,
                  gap,
                  i
                )
              : 0;

          const inNucleus =
            nucleusByPosition[p] !== null &&
            nucleusByPosition[p].has(n);

          nucleusScores[n] = inNucleus ? 100 : 0;

          const components = [
            freqScores[n],
            returnScores[n],
          ];

          if (nucleusByPosition[p] !== null) {
            components.push(nucleusScores[n]);
          }

          comboScores[n] =
            components.reduce((a, b) => a + b, 0) /
            components.length;
        }

        ranked.frequency[p] = rankRows(freqScores, p);
        ranked.return[p] = rankRows(returnScores, p);
        ranked.nucleus[p] =
          nucleusByPosition[p] === null
            ? []
            : rankRows(nucleusScores, p);
        ranked.combo[p] = rankRows(comboScores, p);

        for (const method of METHODS) {
          if (!ranked[method][p].length) {
            ranks[method][p] = null;
            continue;
          }

          const hit = ranked[method][p].find(
            (r) => r.n === target.n[p]
          );

          ranks[method][p] = hit ? hit.rank : null;
        }
      }

      const ticketHits = {
        frequency: null,
        return: null,
        nucleus: null,
        combo: null,
      };

      for (const method of METHODS) {
        const ticket = greedyTicket(ranked[method]);
        ticketHits[method] = actualTicketHit(
          ticket,
          target.n
        );
      }

      cases.push({
        date: target.d,
        month: targetMonth,
        target: target.n,
        ranks,
        ticketHits,
      });
    }

    const methodSummary = {};

    for (const method of METHODS) {
      const validCases =
        method === "nucleus"
          ? cases.filter((c) =>
              c.ranks.nucleus.every((r) => r != null)
            )
          : cases;

      const hits = validCases
        .map((c) => c.ticketHits[method])
        .filter((x) => Number.isFinite(x));

      const rank = methodRankStats(validCases, method);

      const benchmark = monteCarloBenchmark(
        validCases,
        4000,
        method === "nucleus" ? 9173 : 5173
      );

      const avgHits = hits.length
        ? hits.reduce((a, b) => a + b, 0) / hits.length
        : null;

      const topHitRate = hits.length
        ? (100 * hits.filter((x) => x >= 1).length) /
          hits.length
        : null;

      methodSummary[method] = {
        label: METHOD_LABEL[method],
        cases: validCases.length,
        position: rank,
        avgHits,
        topHitRate,
        ticketCases: hits.length,
        benchmark,
        percentile:
          benchmark && Number.isFinite(avgHits)
            ? percentileRank(benchmark.means, avgHits)
            : null,
        pUpper:
          benchmark && Number.isFinite(avgHits)
            ? (100 *
                benchmark.means.filter(
                  (x) => x >= avgHits
                ).length) /
              benchmark.means.length
            : null,
        blocks: buildBlockStats(validCases, method),
      };
    }

    const rankBenchmark = monteCarloPositionBenchmark(
      cases,
      1,
      2026
    );

    return {
      firstDate: ordered[0]?.d || "",
      lastDate: ordered[ordered.length - 1]?.d || "",
      totalDraws: ordered.length,
      verifiedDraws: cases.length,
      validSizes,
      methodSummary,
      rankBenchmark,
    };
  }, [sourceDraws]);

  const panel = {
    background: T.card,
    border: `1px solid ${T.edge}`,
    borderRadius: 14,
    padding: 14,
    marginBottom: 14,
  };

  const pct = (v) =>
    Number.isFinite(v) ? `${v.toFixed(1)}%` : "—";

  const num = (v, digits = 2) =>
    Number.isFinite(v) ? v.toFixed(digits) : "—";

  const pval = (v) =>
    Number.isFinite(v) ? `${v.toFixed(1)}%` : "—";

  return (
    <div>
      <div style={panel}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 800,
            letterSpacing: 1.2,
            textTransform: "uppercase",
            color: T.ink,
          }}
        >
          Verifica 2.0 — walk-forward
        </div>

        <div
          style={{
            fontSize: 11.5,
            color: T.dim,
            marginTop: 4,
            lineHeight: 1.5,
          }}
        >
          Ogni estrazione viene valutata usando esclusivamente
          le estrazioni precedenti. Il benchmark casuale usa
          lo stesso numero di casi del metodo confrontato.
        </div>

        <div
          style={{
            display: "flex",
            gap: 8,
            flexWrap: "wrap",
            marginTop: 10,
          }}
        >
          <span style={{ color: T.dim, fontSize: 11.5 }}>
            storico:{" "}
            <b style={{ color: T.ink }}>
              {fmtDate(result.firstDate)} →{" "}
              {fmtDate(result.lastDate)}
            </b>
          </span>

          <span style={{ color: T.dim, fontSize: 11.5 }}>
            casi verificati:{" "}
            <b style={{ color: T.ink }}>
              {result.verifiedDraws}
            </b>
          </span>
        </div>
      </div>

      <div style={panel}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 800,
            color: T.ink,
            marginBottom: 8,
          }}
        >
          Cosa viene testato
        </div>

        <div
          style={{
            fontSize: 12.5,
            color: T.dim,
            lineHeight: 1.6,
          }}
        >
          <div>
            <b style={{ color: T.ink }}>Frequency</b> —
            frequenza del numero nel prefisso storico.
          </div>
          <div>
            <b style={{ color: T.ink }}>Return</b> — hazard
            empirica del gap corrente, calcolata sui ritorni
            già osservati.
          </div>
          <div>
            <b style={{ color: T.ink }}>Nucleus</b> — numero
            presente nei tre mesi precedenti e non ancora uscito
            nel mese target.
          </div>
          <div>
            <b style={{ color: T.ink }}>Combo</b> — media delle
            componenti disponibili.
          </div>
        </div>

        <div
          style={{
            marginTop: 9,
            padding: 9,
            borderRadius: 9,
            background: "#101830",
            border: `1px solid ${T.edge}`,
            fontSize: 11.5,
            color: T.dim,
            lineHeight: 1.5,
          }}
        >
          <b style={{ color: T.ink }}>Leakage:</b> qui non
          vengono usati <code>RAW.freq</code> o{" "}
          <code>RAW.prof</code>. Le statistiche vengono
          ricostruite dal prefisso storico prima di ogni draw.
        </div>
      </div>

      <div style={panel}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 800,
            color: T.ink,
            marginBottom: 8,
          }}
        >
          Rank del numero realmente estratto
        </div>

        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              borderCollapse: "collapse",
              width: "100%",
              fontSize: 11.5,
              fontFamily: "ui-monospace, monospace",
            }}
          >
            <thead>
              <tr style={{ color: T.dim }}>
                <th
                  style={{
                    textAlign: "left",
                    padding: "4px",
                  }}
                >
                  metodo
                </th>
                {POS_LABELS.map((l, p) => (
                  <th
                    key={l}
                    style={{
                      padding: "4px",
                      color: POS_COLORS[p],
                    }}
                  >
                    {l}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody>
              {METHODS.map((method) => (
                <tr
                  key={method}
                  style={{
                    borderTop: "1px solid #1b2340",
                  }}
                >
                  <td
                    style={{
                      padding: "5px 4px",
                      color: T.ink,
                      fontWeight: 800,
                    }}
                  >
                    {METHOD_LABEL[method]}
                  </td>

                  {result.methodSummary[method].position.map(
                    (s, p) => (
                      <td
                        key={p}
                        style={{
                          padding: "5px 4px",
                          textAlign: "center",
                          color:
                            s.top5 >= s.baselineTop5
                              ? T.ok
                              : T.dim,
                        }}
                      >
                        {pct(s.top5)}
                      </td>
                    )
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div
          style={{
            fontSize: 10.5,
            color: T.dim,
            marginTop: 7,
            lineHeight: 1.5,
          }}
        >
          Le percentuali sono confrontabili con il benchmark
          casuale top-5 del 13,9% per posizione (5 candidati su
          36).
        </div>
      </div>

      <div style={panel}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 800,
            color: T.ink,
            marginBottom: 8,
          }}
        >
          Test pratico — cinquina greedy
        </div>

        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              borderCollapse: "collapse",
              width: "100%",
              fontSize: 11.5,
              fontFamily: "ui-monospace, monospace",
            }}
          >
            <thead>
              <tr style={{ color: T.dim }}>
                <th
                  style={{
                    textAlign: "left",
                    padding: "4px",
                  }}
                >
                  metodo
                </th>
                <th style={{ padding: "4px" }}>
                  media hit
                </th>
                <th style={{ padding: "4px" }}>
                  ≥1 hit
                </th>
                <th style={{ padding: "4px" }}>
                  casi
                </th>
              </tr>
            </thead>

            <tbody>
              {METHODS.map((method) => {
                const m = result.methodSummary[method];

                return (
                  <tr
                    key={method}
                    style={{
                      borderTop: "1px solid #1b2340",
                    }}
                  >
                    <td
                      style={{
                        padding: "5px 4px",
                        color: T.ink,
                        fontWeight: 800,
                      }}
                    >
                      {m.label}
                    </td>
                    <td
                      style={{
                        padding: "5px 4px",
                        textAlign: "center",
                        color: T.amber,
                        fontWeight: 800,
                      }}
                    >
                      {num(m.avgHits)}
                    </td>
                    <td
                      style={{
                        padding: "5px 4px",
                        textAlign: "center",
                        color: T.ink,
                      }}
                    >
                      {pct(m.topHitRate)}
                    </td>
                    <td
                      style={{
                        padding: "5px 4px",
                        textAlign: "center",
                        color: T.dim,
                      }}
                    >
                      {m.ticketCases}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div style={panel}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 800,
            color: T.ink,
            marginBottom: 8,
          }}
        >
          Benchmark casuale comparabile
        </div>

        <div
          style={{
            fontSize: 11.5,
            color: T.dim,
            lineHeight: 1.5,
            marginBottom: 9,
          }}
        >
          Monte Carlo deterministico: 4.000 repliche di cinquine
          casuali 5/40 sugli stessi casi storici del metodo.
          Questo rende il confronto della media hit direttamente
          leggibile. Il valore teorico resta 0,625 hit.
        </div>

        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              borderCollapse: "collapse",
              width: "100%",
              fontSize: 11.5,
              fontFamily: "ui-monospace, monospace",
            }}
          >
            <thead>
              <tr style={{ color: T.dim }}>
                <th
                  style={{
                    textAlign: "left",
                    padding: "4px",
                  }}
                >
                  metodo
                </th>
                <th style={{ padding: "4px" }}>
                  osservato
                </th>
                <th style={{ padding: "4px" }}>
                  random medio
                </th>
                <th style={{ padding: "4px" }}>
                  IC 95% random
                </th>
                <th style={{ padding: "4px" }}>
                  percentile
                </th>
                <th style={{ padding: "4px" }}>
                  p superiore
                </th>
              </tr>
            </thead>

            <tbody>
              {METHODS.map((method) => {
                const m = result.methodSummary[method];
                const b = m.benchmark;

                return (
                  <tr
                    key={method}
                    style={{
                      borderTop: "1px solid #1b2340",
                    }}
                  >
                    <td
                      style={{
                        padding: "5px 4px",
                        color: T.ink,
                        fontWeight: 800,
                      }}
                    >
                      {m.label}
                    </td>
                    <td
                      style={{
                        padding: "5px 4px",
                        textAlign: "center",
                        color: T.amber,
                      }}
                    >
                      {num(m.avgHits)}
                    </td>
                    <td
                      style={{
                        padding: "5px 4px",
                        textAlign: "center",
                        color: T.dim,
                      }}
                    >
                      {num(b?.mean)}
                    </td>
                    <td
                      style={{
                        padding: "5px 4px",
                        textAlign: "center",
                        color: T.dim,
                      }}
                    >
                      {b
                        ? `${num(b.low95)}–${num(
                            b.high95
                          )}`
                        : "—"}
                    </td>
                    <td
                      style={{
                        padding: "5px 4px",
                        textAlign: "center",
                        color:
                          m.percentile >= 95
                            ? T.ok
                            : T.ink,
                        fontWeight:
                          m.percentile >= 95 ? 800 : 400,
                      }}
                    >
                      {pval(m.percentile)}
                    </td>
                    <td
                      style={{
                        padding: "5px 4px",
                        textAlign: "center",
                        color: T.dim,
                      }}
                    >
                      {pval(m.pUpper)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div
          style={{
            marginTop: 8,
            padding: 9,
            borderRadius: 9,
            background: "#101830",
            border: `1px solid ${T.edge}`,
            fontSize: 11,
            color: T.dim,
            lineHeight: 1.5,
          }}
        >
          <b style={{ color: T.ink }}>Come leggerlo:</b>{" "}
          “percentile 97%” significa che il risultato osservato
          è sopra circa il 97% delle repliche casuali. “p
          superiore 3%” indica la quota di repliche casuali che
          hanno ottenuto una media almeno pari a quella osservata.
          È un confronto storico, non una prova di predittività
          futura.
        </div>
      </div>

      <div style={panel}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 800,
            color: T.ink,
            marginBottom: 8,
          }}
        >
          Stabilità nel tempo — media hit per mese
        </div>

        <div
          style={{
            fontSize: 11.5,
            color: T.dim,
            lineHeight: 1.5,
            marginBottom: 8,
          }}
        >
          Il risultato complessivo può nascondere periodi molto
          diversi. Qui vediamo la stessa metrica separata per
          mese.
        </div>

        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              borderCollapse: "collapse",
              width: "100%",
              fontSize: 11.5,
              fontFamily: "ui-monospace, monospace",
            }}
          >
            <thead>
              <tr style={{ color: T.dim }}>
                <th
                  style={{
                    textAlign: "left",
                    padding: "4px",
                  }}
                >
                  mese
                </th>
                {METHODS.map((method) => (
                  <th key={method} style={{ padding: "4px" }}>
                    {METHOD_LABEL[method]}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody>
              {[
                ...new Set(
                  METHODS.flatMap(
                    (method) =>
                      result.methodSummary[method].blocks.map(
                        (b) => b.month
                      )
                  )
                ),
              ]
                .sort()
                .map((month) => (
                  <tr
                    key={month}
                    style={{
                      borderTop: "1px solid #1b2340",
                    }}
                  >
                    <td
                      style={{
                        padding: "5px 4px",
                        color: T.ink,
                        fontWeight: 800,
                      }}
                    >
                      {month}
                    </td>

                    {METHODS.map((method) => {
                      const block =
                        result.methodSummary[
                          method
                        ].blocks.find(
                          (b) => b.month === month
                        );

                      return (
                        <td
                          key={method}
                          style={{
                            padding: "5px 4px",
                            textAlign: "center",
                            color: block
                              ? T.ink
                              : T.dim,
                          }}
                        >
                          {block
                            ? `${num(block.avg)} (${pct(
                                block.oneHit
                              )})`
                            : "—"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        <div
          style={{
            fontSize: 10.5,
            color: T.dim,
            marginTop: 7,
          }}
        >
          Formato: media hit (percentuale di casi con almeno
          1 hit). Nucleus compare solo quando sono disponibili
          tutti i tre mesi precedenti.
        </div>
      </div>

      <div style={panel}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 800,
            color: T.ink,
            marginBottom: 8,
          }}
        >
          Benchmark del rank
        </div>

        <div
          style={{
            fontSize: 11.5,
            color: T.dim,
            lineHeight: 1.5,
          }}
        >
          Per una classifica casuale di 36 candidati, la
          probabilità teorica che il numero estratto sia nel
          top-5 è 5/36 = 13,9% per posizione. I valori sopra
          questo livello descrivono il comportamento del test
          storico; non costituiscono una previsione.
        </div>
      </div>

      <div
        style={{
          padding: 10,
          borderRadius: 10,
          background: "#101830",
          border: `1px solid ${T.edge}`,
          color: T.dim,
          fontSize: 11.5,
          lineHeight: 1.5,
        }}
      >
        <b style={{ color: T.ink }}>Conclusione metodologica:</b>{" "}
        il nuovo benchmark ci permette di distinguere un risultato
        semplicemente sopra 0,625 da un risultato che, nel test
        storico, si colloca nella coda alta delle simulazioni
        casuali. Non dimostra però che il metodo abbia capacità
        predittiva sulle estrazioni future.
      </div>
    </div>
  );
}
