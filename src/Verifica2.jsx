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

const monthKey = (d) => d.slice(0, 7);

function prevMonth(m) {
  const [y, mo] = m.split("-").map(Number);
  return mo === 1
    ? `${y - 1}-12`
    : `${y}-${String(mo - 1).padStart(2, "0")}`;
}

function fmtDate(d) {
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

/*
 * Costruisce tutte le statistiche usando esclusivamente draws[0..beforeIndex-1].
 * Non viene mai letto RAW.freq / RAW.prof per la verifica: sono statistiche
 * costruite sull'intero storico e quindi non adatte a un walk-forward puro.
 */
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

/*
 * Return score:
 * per ogni numero, si osservano nel prefisso le distanze tra occorrenze
 * consecutive. Per il gap attuale g si misura la hazard empirica:
 *
 *   intervalli esposti a g che terminano proprio a g
 *   ------------------------------------------------
 *   intervalli che arrivano almeno a g
 *
 * È una misura puramente storica e viene ricostruita prima di ogni estrazione.
 */
function returnHazard(occurrences, p, n, currentGap, beforeIndex) {
  if (currentGap < 1) return 0;

  const hist = occurrences[p][n] || [];
  if (hist.length < 2) return 0;

  const gaps = [];
  for (let j = 1; j < hist.length; j++) {
    const g = hist[j] - hist[j - 1];
    if (hist[j] < beforeIndex) gaps.push(g);
  }

  if (!gaps.length) return 0;

  let numerator = 0;
  let denominator = 0;

  for (const g of gaps) {
    if (g >= currentGap) denominator++;
    if (g === currentGap) numerator++;
  }

  if (denominator > 0) return (100 * numerator) / denominator;

  /*
   * Se il gap attuale è oltre il massimo storico, usiamo il massimo gap
   * osservato come riferimento, senza introdurre dati futuri.
   */
  const maxGap = Math.max(...gaps);
  if (currentGap > maxGap) return 0;

  return 0;
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

  /*
   * "Atteso" = ancora non uscito nel mese target prima della draw da verificare.
   */
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

function methodStats(rankCases, method, validSizes) {
  const perPosition = [];

  for (let p = 0; p < 5; p++) {
    const ranks = rankCases
      .map((x) => x[method][p])
      .filter((x) => Number.isFinite(x));

    const n = ranks.length || 1;

    const rate = (k) =>
      (100 * ranks.filter((r) => r <= k).length) / n;

    perPosition.push({
      mean: ranks.length
        ? ranks.reduce((a, b) => a + b, 0) / ranks.length
        : null,
      median: median(ranks),
      top1: rate(1),
      top3: rate(3),
      top5: rate(5),
      top10: rate(10),
      baselineTop1: 100 / validSizes[p],
      baselineTop3: (100 * Math.min(3, validSizes[p])) / validSizes[p],
      baselineTop5: (100 * Math.min(5, validSizes[p])) / validSizes[p],
      baselineTop10: (100 * Math.min(10, validSizes[p])) / validSizes[p],
    });
  }

  return perPosition;
}

export default function Verifica2({ draws }) {
  const sourceDraws = draws && draws.length ? draws : RAW.draws;

  const result = useMemo(() => {
    const ordered = [...sourceDraws].sort((a, b) =>
      a.d.localeCompare(b.d)
    );

    const validSizes = Array.from({ length: 5 }, (_, p) => validNumbers(p).length);

    const rankCases = [];
    const ticketHits = {
      frequency: [],
      return: [],
      nucleus: [],
      combo: [],
    };

    const firstDate = ordered[0]?.d || "";
    const lastDate = ordered[ordered.length - 1]?.d || "";

    /*
     * Servono tre mesi precedenti per il metodo Nucleus.
     * I casi senza tre mesi completi vengono comunque usati dagli altri
     * metodi; il Nucleus in quei casi vale null e non viene contato.
     */
    for (let i = 1; i < ordered.length; i++) {
      const target = ordered[i];
      const stats = buildPrefixStats(ordered, i);
      const targetMonth = monthKey(target.d);
      const nucleus = nucleusFor(ordered, i, 0, targetMonth);

      const nucleusByPosition = Array.from({ length: 5 }, (_, p) =>
        nucleusFor(ordered, i, p, targetMonth)
      );

      const ranked = {
        frequency: [],
        return: [],
        nucleus: [],
        combo: [],
      };

      const actualRanks = {
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

        const lo = VALID_LO[p];
        const hi = VALID_HI[p];

        for (let n = lo; n <= hi; n++) {
          const freq = stats.counts[p][n] || 0;
          freqScores[n] = (100 * freq) / stats.maxCount[p];

          const last = lastOccurrence(stats.occurrences, p, n);
          const gap = last >= 0 ? i - last : 0;

          returnScores[n] =
            last >= 0
              ? returnHazard(stats.occurrences, p, n, gap, i)
              : 0;

          const inNucleus =
            nucleusByPosition[p] !== null &&
            nucleusByPosition[p].has(n);

          nucleusScores[n] = inNucleus ? 100 : 0;

          /*
           * Combo: media semplice delle tre componenti.
           * Se il Nucleus non è disponibile, la media usa Frequency + Return.
           */
          const components = [
            freqScores[n],
            returnScores[n],
          ];

          if (nucleusByPosition[p] !== null) {
            components.push(nucleusScores[n]);
          }

          comboScores[n] =
            components.reduce((a, b) => a + b, 0) / components.length;
        }

        ranked.frequency[p] = rankRows(freqScores, p);
        ranked.return[p] = rankRows(returnScores, p);
        ranked.nucleus[p] =
          nucleusByPosition[p] === null
            ? []
            : rankRows(nucleusScores, p);
        ranked.combo[p] = rankRows(comboScores, p);

        for (const method of ["frequency", "return", "nucleus", "combo"]) {
          if (!ranked[method][p].length) {
            actualRanks[method][p] = null;
            continue;
          }

          const hit = ranked[method][p].find(
            (r) => r.n === target.n[p]
          );

          actualRanks[method][p] = hit ? hit.rank : null;
        }
      }

      rankCases.push(actualRanks);

      for (const method of ["frequency", "return", "nucleus", "combo"]) {
        const ticket = greedyTicket(ranked[method]);

        if (ticket) {
          const actual = new Set(target.n);
          const hits = ticket.filter((n) => actual.has(n)).length;
          ticketHits[method].push(hits);
        }
      }
    }

    const methodNames = {
      frequency: "Frequency",
      return: "Return",
      nucleus: "Nucleus",
      combo: "Combo",
    };

    const methodSummary = {};

    for (const method of Object.keys(methodNames)) {
      const validCases =
        method === "nucleus"
          ? rankCases.filter((x) => x.nucleus.every((r) => r != null))
          : rankCases;

      const stats = methodStats(
        validCases,
        method,
        validSizes
      );

      const hits = ticketHits[method];

      methodSummary[method] = {
        label: methodNames[method],
        cases: validCases.length,
        position: stats,
        avgHits: hits.length
          ? hits.reduce((a, b) => a + b, 0) / hits.length
          : null,
        topHitRate: hits.length
          ? (100 * hits.filter((x) => x >= 1).length) / hits.length
          : null,
        ticketCases: hits.length,
      };
    }

    return {
      firstDate,
      lastDate,
      totalDraws: ordered.length,
      verifiedDraws: rankCases.length,
      randomHits: 0.625,
      validSizes,
      methodSummary,
    };
  }, [sourceDraws]);

  const panel = {
    background: T.card,
    border: `1px solid ${T.edge}`,
    borderRadius: 14,
    padding: 14,
    marginBottom: 14,
  };

  const methodOrder = ["frequency", "return", "nucleus", "combo"];

  const pct = (v) =>
    Number.isFinite(v) ? `${v.toFixed(1)}%` : "—";

  const num = (v) =>
    Number.isFinite(v) ? v.toFixed(2) : "—";

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
          Verifica leakage-free: per ogni estrazione i punteggi sono
          ricostruiti usando esclusivamente le estrazioni precedenti.
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
              {fmtDate(result.firstDate)} → {fmtDate(result.lastDate)}
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

        <div style={{ fontSize: 12.5, color: T.dim, lineHeight: 1.6 }}>
          <div>
            <b style={{ color: T.ink }}>Frequency</b> — frequenza del
            numero nel prefisso storico.
          </div>
          <div>
            <b style={{ color: T.ink }}>Return</b> — hazard empirica
            del gap corrente, calcolata sui ritorni già osservati.
          </div>
          <div>
            <b style={{ color: T.ink }}>Nucleus</b> — numero presente
            nei tre mesi precedenti e non ancora uscito nel mese target.
          </div>
          <div>
            <b style={{ color: T.ink }}>Combo</b> — media delle tre
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
          Importante: qui non vengono usati <code>RAW.freq</code> o{" "}
          <code>RAW.prof</code>, perché sono statistiche calcolate
          sull'intero storico. Usarle avrebbe introdotto leakage.
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
                <th style={{ textAlign: "left", padding: "4px" }}>
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
              {methodOrder.map((method) => (
                <tr
                  key={method}
                  style={{ borderTop: "1px solid #1b2340" }}
                >
                  <td
                    style={{
                      padding: "5px 4px",
                      color: T.ink,
                      fontWeight: 800,
                    }}
                  >
                    {result.methodSummary[method].label}
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
          }}
        >
          Celle = percentuale di volte in cui il numero realmente
          estratto era nel top-5 della classifica di quella posizione.
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
          Dettaglio per metodo
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
                <th style={{ textAlign: "left", padding: "4px" }}>
                  metodo
                </th>
                <th style={{ padding: "4px" }}>casi</th>
                <th style={{ padding: "4px" }}>P1 top5</th>
                <th style={{ padding: "4px" }}>P2 top5</th>
                <th style={{ padding: "4px" }}>P3 top5</th>
                <th style={{ padding: "4px" }}>P4 top5</th>
                <th style={{ padding: "4px" }}>P5 top5</th>
                <th style={{ padding: "4px" }}>media rank</th>
              </tr>
            </thead>

            <tbody>
              {methodOrder.map((method) => {
                const m = result.methodSummary[method];

                return (
                  <tr
                    key={method}
                    style={{ borderTop: "1px solid #1b2340" }}
                  >
                    <td
                      style={{
                        padding: "5px 4px",
                        fontWeight: 800,
                        color: T.ink,
                      }}
                    >
                      {m.label}
                    </td>

                    <td
                      style={{
                        padding: "5px 4px",
                        textAlign: "center",
                        color: T.dim,
                      }}
                    >
                      {m.cases}
                    </td>

                    {m.position.map((s, p) => (
                      <td
                        key={p}
                        style={{
                          padding: "5px 4px",
                          textAlign: "center",
                          color: T.ink,
                        }}
                      >
                        {pct(s.top5)}
                      </td>
                    ))}

                    <td
                      style={{
                        padding: "5px 4px",
                        textAlign: "center",
                        color: T.amber,
                        fontWeight: 800,
                      }}
                    >
                      {num(
                        m.position.reduce(
                          (a, s) => a + (s.mean || 0),
                          0
                        ) / 5
                      )}
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
          Test pratico: cinquina greedy
        </div>

        <div
          style={{
            fontSize: 11.5,
            color: T.dim,
            lineHeight: 1.5,
            marginBottom: 8,
          }}
        >
          Per ogni metodo viene costruita una cinquina scegliendo il
          miglior candidato disponibile in ciascuna posizione, mantenendo
          l'ordine crescente. È un test euristico della procedura di
          selezione, non una dimostrazione di capacità predittiva.
        </div>

        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              borderCollapse: "collapse",
              width: "100%",
              fontSize: 12,
              fontFamily: "ui-monospace, monospace",
            }}
          >
            <thead>
              <tr style={{ color: T.dim }}>
                <th style={{ textAlign: "left", padding: "4px" }}>
                  metodo
                </th>
                <th style={{ padding: "4px" }}>media hit</th>
                <th style={{ padding: "4px" }}>≥1 hit</th>
                <th style={{ padding: "4px" }}>casi</th>
              </tr>
            </thead>

            <tbody>
              {methodOrder.map((method) => {
                const m = result.methodSummary[method];

                return (
                  <tr
                    key={method}
                    style={{ borderTop: "1px solid #1b2340" }}
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

              <tr style={{ borderTop: `1px solid ${T.edge}` }}>
                <td
                  style={{
                    padding: "5px 4px",
                    color: T.dim,
                    fontWeight: 800,
                  }}
                >
                  Random 5/40
                </td>
                <td
                  style={{
                    padding: "5px 4px",
                    textAlign: "center",
                    color: T.dim,
                  }}
                >
                  {result.randomHits.toFixed(3)}
                </td>
                <td
                  style={{
                    padding: "5px 4px",
                    textAlign: "center",
                    color: T.dim,
                  }}
                >
                  —
                </td>
                <td
                  style={{
                    padding: "5px 4px",
                    textAlign: "center",
                    color: T.dim,
                  }}
                >
                  —
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div
          style={{
            marginTop: 8,
            fontSize: 11,
            color: T.dim,
            lineHeight: 1.5,
          }}
        >
          Il benchmark 0,625 è il numero medio teorico di coincidenze
          tra una cinquina casuale di 5 numeri su 40 e l'estrazione.
          Non è un benchmark diretto della classifica per posizione.
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
        <b style={{ color: T.ink }}>Lettura corretta:</b> un risultato
        superiore al benchmark descrive soltanto il comportamento del
        test storico. Non implica che il metodo abbia capacità
        predittiva sulle estrazioni future. La verifica 2.0 serve
        soprattutto a impedire che il futuro entri accidentalmente nel
        calcolo del punteggio.
      </div>
    </div>
  );
}
