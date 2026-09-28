import { useMemo, useState } from "react";

/*
  TrendMemoryProjection.jsx
  Modulo grafico per SONAR / vincicasa-lab.

  Uso:
    import TrendMemoryProjection from "./TrendMemoryProjection";
    <TrendMemoryProjection draws={draws} />

  Il modulo:
  - calcola Trend Top 5;
  - calcola Memory Top 5/8 tramite analoghi storici (overlap >= 2, peso overlap^2);
  - propone alcune combinazioni sperimentali;
  - permette di modificare manualmente le cinquine;
  - mostra la proiezione su griglia 1..40 e per posizione P1..P5.

  Nota metodologica:
  le proposte sono sperimentali/descriptive e non costituiscono una previsione certa
  dell'estrazione successiva.
*/

const VALID = 40;

const C = {
  bg: "#0b1020",
  card: "#141b2e",
  edge: "#26304c",
  ink: "#e9edf7",
  dim: "#8f97b0",
  ok: "#49d18a",
  amber: "#f5b942",
  warn: "#ff6b6b",
  blue: "#6a8bff",
  violet: "#c07ef5",
};

const clamp = (x, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, x));
const mean = a => a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0;

function freqWindow(draws, end, w) {
  const out = Array(VALID + 1).fill(0);
  for (let i = Math.max(0, end - w); i < end; i++)
    for (const n of draws[i].n) out[n]++;
  return out;
}

function trendRank(draws, end) {
  if (end < 21) return Array.from({ length: VALID }, (_, i) => i + 1);

  const f7 = freqWindow(draws, end, 7);
  const f14 = freqWindow(draws, end, 14);
  const f21 = freqWindow(draws, end, 21);
  const rows = [];

  for (let n = 1; n <= VALID; n++) {
    const r7 = f7[n] / 7;
    const r21 = f21[n] / 21;
    const accel = r7 - r21;
    const recent = clamp(0.5 + accel * 2.5);
    const level = clamp(r21 * 8);
    const persistence =
      (r7 > 0 ? 1 : 0) +
      (f14[n] > 0 ? 1 : 0) +
      (r21 > 0 ? 1 : 0);

    const score =
      0.45 * recent +
      0.35 * level +
      0.20 * (persistence / 3);

    rows.push({ n, score, f7: f7[n], f14: f14[n], f21: f21[n], accel });
  }

  return rows
    .sort((a, b) => b.score - a.score || a.n - b.n)
    .map(x => x.n);
}

function memoryRank(draws, end) {
  if (end < 3) return Array.from({ length: VALID }, (_, i) => i + 1);

  const current = draws[end - 1].n;
  const score = Array(VALID + 1).fill(0);
  const support = Array(VALID + 1).fill(0);

  // Ogni stato storico simile (>=2 numeri in comune) vota
  // i numeri apparsi nell'estrazione immediatamente successiva.
  for (let j = 0; j < end - 1; j++) {
    const overlap = current.filter(x => draws[j].n.includes(x)).length;
    if (overlap < 2 || !draws[j + 1]) continue;

    const w = overlap * overlap;
    for (const n of draws[j + 1].n) {
      score[n] += w;
      support[n] += 1;
    }
  }

  return Array.from({ length: VALID }, (_, i) => i + 1)
    .map(n => ({ n, score: score[n], support: support[n] }))
    .sort((a, b) =>
      b.score - a.score ||
      b.support - a.support ||
      a.n - b.n
    )
    .map(x => x.n);
}

function pairSupport(draws, end, w = 14) {
  const current = draws[end - 1].n;
  const out = Array(VALID + 1).fill(0);

  for (let j = Math.max(0, end - w); j < end; j++) {
    const hit = draws[j].n;
    for (const n of hit) {
      if (current.includes(n)) continue;
      out[n]++;
    }
  }

  return out;
}

function makeProposals(draws) {
  const end = draws.length;
  const T = trendRank(draws, end);
  const M = memoryRank(draws, end);
  const pairs = pairSupport(draws, end, 14);

  const outside = Array.from({ length: VALID }, (_, i) => i + 1)
    .filter(n => !T.slice(0, 8).includes(n));

  const relation = [...outside].sort((a, b) =>
    pairs[b] - pairs[a] || a - b
  );

  const unique = xs => [...new Set(xs)].slice(0, 5);

  return {
    trend: unique(T.slice(0, 5)),
    memory: unique(M.slice(0, 5)),
    memory8: unique(M.slice(0, 8)),
    hybrid2: unique([
      ...T.slice(0, 2),
      ...M.filter(n => !T.slice(0, 2).includes(n))
    ]),
    hybrid4: unique([
      ...T.slice(0, 4),
      ...M.filter(n => !T.slice(0, 4).includes(n))
    ]),
    fusion: unique([
      T[0], T[1],
      M[0], M[1],
      relation[0]
    ]),
  };
}

function sortTicket(ticket) {
  return [...new Set(ticket)]
    .filter(n => Number.isInteger(n) && n >= 1 && n <= 40)
    .sort((a, b) => a - b)
    .slice(0, 5);
}

function ticketPositions(ticket) {
  return sortTicket(ticket);
}

// Rank storico per posizione P1..P5.
// Per la proiezione corrente usa tutte le estrazioni disponibili.
// Per lo storico usa sempre il prefisso precedente alla singola estrazione,
// così il rank della riga non incorpora il proprio risultato.
function positionRankMap(draws, end) {
  const counts = Array.from({ length: 5 }, () => Array(VALID + 1).fill(0));

  for (let i = 0; i < end; i++) {
    const nums = sortTicket(draws[i].n);
    nums.forEach((n, p) => { counts[p][n]++; });
  }

  return counts.map(row => {
    const ordered = Array.from({ length: VALID }, (_, i) => i + 1)
      .sort((a, b) => row[b] - row[a] || a - b);

    const rank = {};
    ordered.forEach((n, i) => { rank[n] = i + 1; });
    return rank;
  });
}

function positionalRanksForTicket(draws, ticket, end = draws.length) {
  const maps = positionRankMap(draws, end);
  const nums = sortTicket(ticket);

  return nums.map((n, p) => ({
    n,
    position: p + 1,
    rank: maps[p][n] ?? VALID,
  }));
}

function historicalPositionalRows(draws, limit = 20) {
  const rows = [];

  // Una riga per estrazione: il rank viene calcolato soltanto con il prefisso
  // precedente, quindi è veramente walk-forward.
  for (let i = 1; i < draws.length; i++) {
    const nums = sortTicket(draws[i].n);
    const ranks = positionalRanksForTicket(draws, nums, i);
    const avg = mean(ranks.map(x => x.rank));

    rows.push({
      i,
      date: draws[i].d,
      nums,
      ranks: ranks.map(x => x.rank),
      avg,
    });
  }

  return rows.slice(-limit).reverse();
}

const card = {
  background: C.card,
  border: `1px solid ${C.edge}`,
  borderRadius: 14,
  padding: 14,
  marginBottom: 14,
};

function Chip({ n, active = false, color = C.amber, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        width: 38,
        height: 38,
        borderRadius: 9,
        margin: 3,
        border: `1px solid ${active ? color : C.edge}`,
        background: active ? "#202b48" : "#101830",
        color: C.ink,
        fontFamily: "ui-monospace, monospace",
        fontWeight: 800,
        cursor: onClick ? "pointer" : "default",
      }}
    >
      {n}
    </button>
  );
}

export default function TrendMemoryProjection({ draws = [] }) {
  const proposals = useMemo(
    () => draws.length ? makeProposals(draws) : null,
    [draws]
  );

  const [tickets, setTickets] = useState([]);
  const [activeTicket, setActiveTicket] = useState(0);

  const currentTickets = tickets.length ? tickets : (
    proposals ? [proposals.trend] : []
  );

  const addProposal = (ticket, label) => {
    const clean = sortTicket(ticket);
    if (clean.length !== 5) return;
    setTickets(prev => [...prev, { label, nums: clean }]);
    setActiveTicket(tickets.length);
  };

  const addManual = () => {
    setTickets(prev => [...prev, {
      label: `CINQUINA ${prev.length + 1}`,
      nums: [],
    }]);
    setActiveTicket(tickets.length);
  };

  const updateTicket = (idx, nums) => {
    setTickets(prev => prev.map((t, i) =>
      i === idx ? { ...t, nums: sortTicket(nums) } : t
    ));
  };

  const toggleNumber = n => {
    if (!tickets.length) addManual();

    const idx = Math.min(activeTicket, tickets.length - 1);
    if (tickets.length === 0) return;

    const t = tickets[idx];
    const exists = t.nums.includes(n);
    if (exists) {
      updateTicket(idx, t.nums.filter(x => x !== n));
    } else if (t.nums.length < 5) {
      updateTicket(idx, [...t.nums, n]);
    }
  };

  const reset = () => {
    setTickets([]);
    setActiveTicket(0);
  };

  const graphTickets = currentTickets.filter(t => {
    const nums = Array.isArray(t) ? t : t.nums;
    return sortTicket(nums).length;
  });

  const selected = graphTickets.flatMap(t =>
    Array.isArray(t) ? t : t.nums
  );

  const selectedSet = new Set(selected);

  const currentTrend = proposals?.trend || [];
  const currentMemory = proposals?.memory8 || [];

  const currentPositionRanks = useMemo(() => {
    if (!draws.length) return {};
    const maps = positionRankMap(draws, draws.length);
    return {
      trend: positionalRanksForTicket(draws, currentTrend),
      memory: positionalRanksForTicket(draws, proposals?.memory || [], draws.length),
      hybrid2: positionalRanksForTicket(draws, proposals?.hybrid2 || [], draws.length),
      hybrid4: positionalRanksForTicket(draws, proposals?.hybrid4 || [], draws.length),
      fusion: positionalRanksForTicket(draws, proposals?.fusion || [], draws.length),
      maps,
    };
  }, [draws, currentTrend.join(","), currentMemory.join(","), proposals]);

  const historyRows = useMemo(
    () => historicalPositionalRows(draws, 20),
    [draws]
  );

  const titleDate = draws.length ? draws[draws.length - 1].d : "—";

  return (
    <div style={{ color: C.ink, fontFamily: "system-ui, sans-serif" }}>

      <div style={card}>
        <div style={{ fontSize: 13, fontWeight: 900, letterSpacing: 1.1 }}>
          SONAR · TREND + MEMORY · PROIEZIONE CINQUINE
        </div>
        <div style={{ color: C.dim, fontSize: 11.5, marginTop: 4 }}>
          Stato dati: {titleDate} · {draws.length} estrazioni
        </div>

        {proposals && (
          <>
            <div style={{ marginTop: 12, fontSize: 11, color: C.dim }}>
              PROPOSTE CALCOLATE DALLO STATO ATTUALE
            </div>

            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 7 }}>
              {[
                ["TREND", proposals.trend],
                ["MEMORY", proposals.memory],
                ["2T + 3M", proposals.hybrid2],
                ["4T + 1M", proposals.hybrid4],
                ["FUSION", proposals.fusion],
              ].map(([label, nums]) => (
                <button
                  key={label}
                  onClick={() => addProposal(nums, label)}
                  style={{
                    border: `1px solid ${C.edge}`,
                    borderRadius: 9,
                    background: "#101830",
                    color: C.ink,
                    padding: "7px 9px",
                    cursor: "pointer",
                    fontSize: 10.5,
                    fontWeight: 800,
                  }}
                >
                  + {label}: {nums.join(" · ")}
                </button>
              ))}
            </div>

            <div style={{ marginTop: 9, fontSize: 10.5, color: C.dim }}>
              TREND Top5: {currentTrend.join(" · ")} · MEMORY Top8: {currentMemory.join(" · ")}
            </div>
          </>
        )}
      </div>

      <div style={card}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 900 }}>
              CINQUINE SELEZIONATE
            </div>
            <div style={{ color: C.dim, fontSize: 10.5, marginTop: 3 }}>
              Aggiungi una proposta oppure crea una cinquina manuale.
            </div>
          </div>

          <button
            onClick={addManual}
            style={{
              background: "#1e6b42",
              color: C.ink,
              border: `1px solid ${C.ok}`,
              borderRadius: 8,
              padding: "7px 9px",
              fontWeight: 800,
              fontSize: 10.5,
            }}
          >
            + MANUALE
          </button>
        </div>

        {!tickets.length && (
          <div style={{ marginTop: 12, color: C.dim, fontSize: 11 }}>
            Nessuna cinquina selezionata: usa uno dei pulsanti sopra.
          </div>
        )}

        {tickets.map((t, i) => (
          <div
            key={i}
            style={{
              marginTop: 9,
              padding: 9,
              borderRadius: 10,
              border: `1px solid ${activeTicket === i ? C.amber : C.edge}`,
              background: "#101830",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <button
                onClick={() => setActiveTicket(i)}
                style={{
                  border: 0,
                  background: "transparent",
                  color: activeTicket === i ? C.amber : C.ink,
                  fontWeight: 900,
                  cursor: "pointer",
                }}
              >
                {t.label}
              </button>

              <button
                onClick={() => setTickets(prev => prev.filter((_, j) => j !== i))}
                style={{
                  border: 0,
                  background: "transparent",
                  color: C.warn,
                  cursor: "pointer",
                  fontSize: 10,
                }}
              >
                elimina
              </button>
            </div>

            <div style={{ marginTop: 5 }}>
              {Array.from({ length: 5 }, (_, j) => (
                <Chip
                  key={j}
                  n={t.nums[j] ?? "—"}
                  color={activeTicket === i ? C.amber : C.blue}
                  active={!!t.nums[j]}
                  onClick={undefined}
                />
              ))}
            </div>
          </div>
        ))}

        {tickets.length > 0 && (
          <button
            onClick={reset}
            style={{
              marginTop: 9,
              border: `1px solid ${C.edge}`,
              background: "#101830",
              color: C.dim,
              borderRadius: 8,
              padding: "6px 9px",
              fontSize: 10.5,
            }}
          >
            azzera selezione
          </button>
        )}
      </div>

      <div style={card}>
        <div style={{ fontSize: 13, fontWeight: 900 }}>
          EDITOR RAPIDO · CINQUINA ATTIVA
        </div>
        <div style={{ color: C.dim, fontSize: 10.5, margin: "4px 0 9px" }}>
          Seleziona fino a 5 numeri. Il grafico sotto si aggiorna immediatamente.
        </div>

        {tickets.length === 0 ? (
          <div style={{ color: C.dim, fontSize: 11 }}>
            Prima crea una cinquina.
          </div>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap" }}>
            {Array.from({ length: 40 }, (_, i) => i + 1).map(n => (
              <Chip
                key={n}
                n={n}
                active={tickets[activeTicket]?.nums.includes(n)}
                color={C.amber}
                onClick={() => toggleNumber(n)}
              />
            ))}
          </div>
        )}
      </div>

      <div style={card}>
        <div style={{ fontSize: 13, fontWeight: 900 }}>
          NUMERO + RANK PER POSIZIONE
        </div>
        <div style={{ color: C.dim, fontSize: 10.5, margin: "4px 0 11px" }}>
          Per ogni cinquina vedi il numero nella posizione P1→P5 e il suo rank
          storico specifico di quella posizione. Rank 1 = posizione più frequente.
          Il rank medio riassume la cinquina.
        </div>

        {!proposals ? (
          <div style={{ color: C.dim, fontSize: 11 }}>Dati insufficienti.</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left", padding: 6 }}>proposta</th>
                  {Array.from({ length: 5 }, (_, p) => (
                    <th key={p} style={{ padding: 6 }}>P{p + 1}</th>
                  ))}
                  <th style={{ padding: 6 }}>rank medio</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ["TREND", currentPositionRanks.trend],
                  ["MEMORY", currentPositionRanks.memory],
                  ["2T + 3M", currentPositionRanks.hybrid2],
                  ["4T + 1M", currentPositionRanks.hybrid4],
                  ["FUSION", currentPositionRanks.fusion],
                ].map(([label, data]) => {
                  const rs = data || [];
                  const avg = rs.length ? mean(rs.map(x => x.rank)) : 0;

                  return (
                    <tr key={label} style={{ borderTop: `1px solid ${C.edge}` }}>
                      <td style={{ padding: 7, fontWeight: 900, whiteSpace: "nowrap" }}>
                        {label}
                      </td>
                      {Array.from({ length: 5 }, (_, p) => {
                        const x = rs[p];
                        return (
                          <td key={p} style={{ textAlign: "center", padding: 6 }}>
                            {x ? (
                              <>
                                <div style={{
                                  fontFamily: "ui-monospace, monospace",
                                  fontWeight: 900,
                                  fontSize: 14
                                }}>
                                  {x.n}
                                </div>
                                <div style={{ color: x.rank <= 8 ? C.ok : C.dim, fontSize: 9.5 }}>
                                  rank {x.rank}
                                </div>
                              </>
                            ) : "—"}
                          </td>
                        );
                      })}
                      <td style={{
                        textAlign: "center",
                        fontWeight: 900,
                        color: avg <= 12 ? C.ok : C.amber
                      }}>
                        {avg ? avg.toFixed(1) : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div style={{
          marginTop: 10,
          padding: 9,
          borderRadius: 9,
          background: "#101830",
          color: C.dim,
          fontSize: 10.5
        }}>
          Il rank è calcolato separatamente per P1, P2, P3, P4 e P5.
          Non è il rank Trend globale del numero.
        </div>
      </div>

      <div style={card}>
        <div style={{ fontSize: 13, fontWeight: 900 }}>
          STORICO RANK PER POSIZIONE
        </div>
        <div style={{ color: C.dim, fontSize: 10.5, margin: "4px 0 10px" }}>
          Ultime 20 estrazioni. Sotto ogni numero compare il rank che quel numero
          aveva nella propria posizione, calcolato usando solo le estrazioni precedenti.
          A destra il rank medio della cinquina.
        </div>

        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 10.5 }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", padding: 5 }}>data</th>
                {Array.from({ length: 5 }, (_, p) => (
                  <th key={p} style={{ padding: 5 }}>P{p + 1}</th>
                ))}
                <th style={{ padding: 5 }}>media</th>
              </tr>
            </thead>
            <tbody>
              {historyRows.map(r => (
                <tr key={r.i} style={{ borderTop: `1px solid ${C.edge}` }}>
                  <td style={{ padding: 5, whiteSpace: "nowrap", color: C.dim }}>
                    {r.date.split("-").reverse().join("/")}
                  </td>

                  {r.nums.map((n, p) => (
                    <td key={p} style={{ textAlign: "center", padding: 5 }}>
                      <div style={{
                        fontFamily: "ui-monospace, monospace",
                        fontWeight: 900,
                        fontSize: 13
                      }}>
                        {n}
                      </div>
                      <div style={{
                        fontSize: 9,
                        color: r.ranks[p] <= 8 ? C.ok : C.dim
                      }}>
                        {r.ranks[p]}
                      </div>
                    </td>
                  ))}

                  <td style={{
                    textAlign: "center",
                    fontWeight: 900,
                    color: r.avg <= 12 ? C.ok : C.amber
                  }}>
                    {r.avg.toFixed(1)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={{ marginTop: 9, color: C.dim, fontSize: 10 }}>
          Esempio di lettura: <b style={{ color: C.ink }}>16 / 7</b> significa
          numero 16 nella posizione indicata e rank storico 7 per quella posizione.
          Un rank basso indica una presenza storica più alta in quella specifica posizione.
        </div>
      </div>

      <div style={card}>
        <div style={{ fontSize: 13, fontWeight: 900 }}>
          PROIEZIONE GRAFICA · 1 → 40
        </div>
        <div style={{ color: C.dim, fontSize: 10.5, margin: "4px 0 12px" }}>
          Ogni riga rappresenta una cinquina selezionata. La posizione orizzontale
          corrisponde al numero.
        </div>

        {!graphTickets.length ? (
          <div style={{ color: C.dim, fontSize: 11 }}>
            Seleziona almeno una cinquina.
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <div style={{ minWidth: 760 }}>
              <div style={{
                display: "grid",
                gridTemplateColumns: "100px repeat(40, 1fr)",
                gap: 2,
                marginBottom: 5,
              }}>
                <div />
                {Array.from({ length: 40 }, (_, i) => (
                  <div key={i} style={{
                    textAlign: "center",
                    fontSize: 8,
                    color: C.dim,
                  }}>
                    {i + 1}
                  </div>
                ))}
              </div>

              {graphTickets.map((ticket, row) => {
                const nums = sortTicket(Array.isArray(ticket) ? ticket : ticket.nums);
                const label = Array.isArray(ticket)
                  ? `CINQUINA ${row + 1}`
                  : ticket.label;

                return (
                  <div
                    key={row}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "100px repeat(40, 1fr)",
                      gap: 2,
                      marginBottom: 6,
                      alignItems: "center",
                    }}
                  >
                    <div style={{
                      fontSize: 9.5,
                      color: C.ink,
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}>
                      {label}
                    </div>

                    {Array.from({ length: 40 }, (_, i) => {
                      const n = i + 1;
                      const hit = nums.includes(n);

                      return (
                        <div
                          key={n}
                          style={{
                            height: 24,
                            borderRadius: 4,
                            background: hit ? C.amber : "#0f1526",
                            border: `1px solid ${hit ? C.amber : "#1b2340"}`,
                            boxSizing: "border-box",
                          }}
                        />
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {selectedSet.size > 0 && (
          <div style={{ marginTop: 12, fontSize: 11 }}>
            <span style={{ color: C.dim }}>Numeri coperti dall'insieme selezionato:</span>
            <b style={{ marginLeft: 6 }}>
              {[...selectedSet].sort((a, b) => a - b).join(" · ")}
            </b>
            <span style={{ color: C.dim, marginLeft: 8 }}>
              ({selectedSet.size} distinti)
            </span>
          </div>
        )}
      </div>

      <div style={card}>
        <div style={{ fontSize: 13, fontWeight: 900 }}>
          PROIEZIONE PER POSIZIONE P1 → P5
        </div>
        <div style={{ color: C.dim, fontSize: 10.5, margin: "4px 0 10px" }}>
          Le cinquine vengono ordinate numericamente: P1 è il minimo, P5 il massimo.
          Non sono posizioni fisiche indipendenti.
        </div>

        {!graphTickets.length ? (
          <div style={{ color: C.dim, fontSize: 11 }}>Nessuna cinquina.</div>
        ) : (
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(5, 1fr)",
            gap: 8,
          }}>
            {Array.from({ length: 5 }, (_, p) => (
              <div
                key={p}
                style={{
                  background: "#101830",
                  border: `1px solid ${C.edge}`,
                  borderRadius: 10,
                  padding: 9,
                }}
              >
                <div style={{ color: C.dim, fontSize: 10 }}>P{p + 1}</div>

                {graphTickets.map((ticket, i) => {
                  const nums = sortTicket(Array.isArray(ticket) ? ticket : ticket.nums);
                  return (
                    <div
                      key={i}
                      style={{
                        marginTop: 6,
                        fontFamily: "ui-monospace, monospace",
                        fontWeight: 800,
                        fontSize: 13,
                      }}
                    >
                      {nums[p] ?? "—"}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{
        ...card,
        borderColor: C.edge,
        fontSize: 10.5,
        color: C.dim,
      }}>
        <b style={{ color: C.ink }}>Nota metodologica.</b>{" "}
        Trend e Memory sono rappresentazioni sperimentali dello stato storico.
        La proiezione grafica serve a confrontare e organizzare le cinquine scelte;
        non attribuisce una probabilità individuale ai numeri e non implica che
        una cinquina sia "più probabile" in senso matematico.
      </div>
    </div>
  );
}
