import { useMemo, useState } from "react";

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

const POS_COLORS = ["#ff4d6d", "#4fc46a", "#6a8bff", "#ffa040", "#c07ef5"];
const POS_LABELS = ["P1", "P2", "P3", "P4", "P5"];

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

  // Tutte le proposte devono essere vere cinquine:
  // 5 numeri distinti, ordinati.
  const unique5 = xs => {
    const out = [];
    for (const n of xs) {
      if (!out.includes(n) && Number.isInteger(n) && n >= 1 && n <= 40) {
        out.push(n);
        if (out.length === 5) break;
      }
    }
    return out.sort((a, b) => a - b);
  };

  const fill5 = (base, fallback) => {
    const out = unique5(base);
    for (const n of fallback) {
      if (out.length >= 5) break;
      if (!out.includes(n)) out.push(n);
    }
    return out.sort((a, b) => a - b).slice(0, 5);
  };

  return {
    trend: unique5(T.slice(0, 5)),
    memory: unique5(M.slice(0, 5)),
    memory8: unique5(M.slice(0, 8)),
    hybrid2: fill5(
      [...T.slice(0, 2), ...M],
      T
    ),
    hybrid4: fill5(
      [...T.slice(0, 4), ...M],
      T
    ),
    fusion: fill5(
      [T[0], T[1], M[0], M[1], relation[0]],
      [...T, ...M, ...relation]
    ),
  };
}

function sortTicket(ticket) {
  return [...new Set(ticket)]
    .filter(n => Number.isInteger(n) && n >= 1 && n <= 40)
    .sort((a, b) => a - b)
    .slice(0, 5);
}

function positionRankMap(draws, end) {
  const counts = Array.from({ length: 5 }, () => Array(VALID + 1).fill(0));

  for (let i = 0; i < end; i++) {
    const nums = sortTicket(draws[i].n);
    nums.forEach((n, p) => { counts[p][n]++; });
  }

  return counts.map((row, p) => {
    const lo = p + 1;
    const hi = 36 + p;

    const ordered = Array.from(
      { length: hi - lo + 1 },
      (_, i) => lo + i
    ).sort((a, b) => row[b] - row[a] || a - b);

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

function repeatStats(draws, p, w) {
  if (draws.length < 2) return { same: 0, total: 0, rate: 0 };

  const start = Math.max(1, draws.length - w);
  let same = 0;

  for (let i = start; i < draws.length; i++) {
    if (draws[i].n[p] === draws[i - 1].n[p]) same++;
  }

  const total = Math.max(0, draws.length - start);
  return { same, total, rate: total ? same / total : 0 };
}

function candidateRun(draws, p, n) {
  let run = 0;
  for (let i = draws.length - 1; i >= 0; i--) {
    if (draws[i].n[p] !== n) break;
    run++;
  }
  return run;
}

function persistenceState(draws, p) {
  const r30 = repeatStats(draws, p, 30).rate;
  const r60 = repeatStats(draws, p, 60).rate;
  const r90 = repeatStats(draws, p, 90).rate;
  const threshold = 0.02;

  if (r30 > r60 + threshold && r30 > r90 + threshold) {
    return "PERSISTENTE";
  }

  if (r30 < r60 - threshold && r30 < r90 - threshold) {
    return "IN ESAURIMENTO";
  }

  return "NORMALE";
}

function projectionPersistence(draws, ticket) {
  const nums = sortTicket(ticket);

  return nums.map((n, p) => {
    const r30 = repeatStats(draws, p, 30);
    const r60 = repeatStats(draws, p, 60);
    const r90 = repeatStats(draws, p, 90);
    const run = candidateRun(draws, p, n);

    return {
      p,
      n,
      run,
      r30,
      r60,
      r90,
      state: persistenceState(draws, p),
    };
  });
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

function OverlayGraph({ draws, ticket }) {
  const rows = draws.slice(-15);
  const selected = sortTicket(ticket);

  if (!rows.length) return null;

  const W = 820, H = 380, PADL = 34, PADR = 34, PADT = 28, PADB = 52;
  const plotW = W - PADL - PADR;
  const plotH = H - PADT - PADB;

  // L'ultima estrazione reale è il punto di partenza.
  // Il punto successivo è la data futura e contiene la cinquina selezionata.
  const totalPoints = rows.length + (selected.length === 5 ? 1 : 0);
  const x = i => totalPoints <= 1
    ? W / 2
    : PADL + (i * plotW) / (totalPoints - 1);
  const y = v => PADT + ((40 - v) * plotH) / 40;

  const labelDy = (i, p) => {
    const v = rows[i].n[p];
    for (let q = 0; q < 5; q++) {
      if (q !== p && rows[i].n[q] > v && rows[i].n[q] - v <= 3) return 15;
    }
    return -8;
  };

  // Curva di transizione finale: collega l'ultimo dato reale
  // al nuovo numero senza introdurre un punto "falso".
  const projectionPath = (p) => {
    if (selected.length !== 5) return "";
    const x0 = x(rows.length - 1);
    const x1 = x(rows.length);
    const y0 = y(rows[rows.length - 1].n[p]);
    const y1 = y(selected[p]);

    // Controllo centrale: produce una piccola "onda" visiva,
    // mantenendo però esattamente i due valori osservato -> previsto.
    const xm = (x0 + x1) / 2;
    const delta = y1 - y0;
    const yc = y0 + delta * 0.50;

    return `M ${x0} ${y0} Q ${xm} ${yc} ${x1} ${y1}`;
  };

  return (
    <div style={card}>
      <div style={{ fontSize: 13, fontWeight: 900 }}>
        ANDAMENTO + ONDA DI PROIEZIONE
      </div>
      <div style={{ color: C.dim, fontSize: 10.5, margin: "4px 0 10px" }}>
        Storico reale fino all'ultima estrazione · tratto finale = passaggio verso la prossima data
      </div>

      <div style={{ overflowX: "auto" }}>
        <svg viewBox={`0 0 ${W} ${H}`} style={{ minWidth: 620, width: "100%", display: "block" }}>
          {[5, 10, 20, 30, 40].map(g => (
            <g key={g}>
              <line
                x1={PADL}
                x2={W - PADR}
                y1={y(g)}
                y2={y(g)}
                stroke="#1b2340"
                strokeWidth="1"
              />
              <text x={7} y={y(g) + 3} fontSize="9" fill={C.dim}>{g}</text>
            </g>
          ))}

          {/* Storico reale */}
          {Array.from({ length: 5 }, (_, p) => (
            <g key={p}>
              <polyline
                fill="none"
                stroke={POS_COLORS[p]}
                strokeWidth="1.8"
                opacity="0.72"
                points={rows.map((dr, i) => `${x(i)},${y(dr.n[p])}`).join(" ")}
              />

              {rows.map((dr, i) => (
                <g key={i}>
                  <circle
                    cx={x(i)}
                    cy={y(dr.n[p])}
                    r="3.1"
                    fill={POS_COLORS[p]}
                    opacity="0.88"
                  />
                  <text
                    x={x(i)}
                    y={y(dr.n[p]) + labelDy(i, p)}
                    textAnchor="middle"
                    fontSize="9.5"
                    fontWeight="700"
                    fill={POS_COLORS[p]}
                    fontFamily="ui-monospace, monospace"
                  >
                    {dr.n[p]}
                  </text>
                </g>
              ))}

              {/* Onda: ultimo valore reale -> valore previsto */}
              {selected.length === 5 && (
                <path
                  d={projectionPath(p)}
                  fill="none"
                  stroke={POS_COLORS[p]}
                  strokeWidth="3"
                  strokeDasharray="8 5"
                  strokeLinecap="round"
                  opacity="1"
                />
              )}
            </g>
          ))}

          {/* Separatore tra reale e futuro */}
          {selected.length === 5 && (
            <line
              x1={x(rows.length - 1)}
              x2={x(rows.length - 1)}
              y1={PADT}
              y2={H - PADB}
              stroke="#59627d"
              strokeWidth="1"
              strokeDasharray="3 5"
              opacity="0.65"
            />
          )}

          {/* Punto previsto sulla data successiva */}
          {selected.length === 5 && selected.map((n, p) => (
            <g key={`projection-${p}`}>
              <circle
                cx={x(rows.length)}
                cy={y(n)}
                r="6"
                fill={POS_COLORS[p]}
                stroke={C.ink}
                strokeWidth="1.5"
              />
              <text
                x={x(rows.length) - 8}
                y={y(n) - 9}
                textAnchor="end"
                fontSize="10.5"
                fontWeight="900"
                fill={POS_COLORS[p]}
                fontFamily="ui-monospace, monospace"
              >
                {POS_LABELS[p]} = {n}
              </text>
            </g>
          ))}

          {/* Etichette date */}
          {rows.map((dr, i) => (
            <text
              key={i}
              x={x(i)}
              y={H - 9}
              textAnchor="middle"
              fontSize="9"
              fill={C.dim}
              transform={`rotate(-45 ${x(i)} ${H - 9})`}
            >
              {dr.d.split("-").slice(1).reverse().join("/")}
            </text>
          ))}

          {selected.length === 5 && (
            <text
              x={x(rows.length)}
              y={H - 9}
              textAnchor="middle"
              fontSize="9.5"
              fontWeight="900"
              fill={C.ink}
            >
              PROSSIMA
            </text>
          )}
        </svg>
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 7 }}>
        {POS_LABELS.map((label, p) => (
          <span key={label} style={{ fontSize: 10.5, color: POS_COLORS[p], fontWeight: 800 }}>
            ● {label}{selected[p] ? ` ${rows.length ? `${rows[rows.length - 1].n[p]} → ${selected[p]}` : `= ${selected[p]}`}` : ""}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function TrendMemoryProjection({ draws = [] }) {
  const proposals = useMemo(
    () => draws.length ? makeProposals(draws) : null,
    [draws]
  );

  const [tickets, setTickets] = useState([]);
  const [activeTicket, setActiveTicket] = useState(0);

  const currentTickets = tickets.length
    ? tickets
    : (proposals ? [{ label: "TREND", nums: proposals.trend }] : []);

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
    if (!tickets.length) {
      addManual();
      return;
    }

    const idx = Math.min(activeTicket, tickets.length - 1);
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

  const selectedTicket = currentTickets[activeTicket] || currentTickets[0] || { nums: [] };
  const selectedNums = sortTicket(Array.isArray(selectedTicket) ? selectedTicket : selectedTicket.nums);

  const currentTrend = proposals?.trend || [];
  const currentMemory = proposals?.memory8 || [];

  const currentPositionRanks = useMemo(() => {
    if (!draws.length) return {};
    return {
      trend: positionalRanksForTicket(draws, currentTrend),
      memory: positionalRanksForTicket(draws, proposals?.memory || [], draws.length),
      hybrid2: positionalRanksForTicket(draws, proposals?.hybrid2 || [], draws.length),
      hybrid4: positionalRanksForTicket(draws, proposals?.hybrid4 || [], draws.length),
      fusion: positionalRanksForTicket(draws, proposals?.fusion || [], draws.length),
    };
  }, [draws, currentTrend.join(","), currentMemory.join(","), proposals]);

  const historyRows = useMemo(
    () => historicalPositionalRows(draws, 20),
    [draws]
  );

  const persistenceRows = useMemo(
    () => projectionPersistence(draws, selectedNums),
    [draws, selectedNums.join(",")]
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
            <div style={{ fontSize: 13, fontWeight: 900 }}>CINQUINE SELEZIONATE</div>
            <div style={{ color: C.dim, fontSize: 10.5, marginTop: 3 }}>
              La cinquina attiva viene usata nel grafico e nella diagnostica P1→P5.
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
            Nessuna cinquina manuale: il grafico usa la TREND come cinquina attiva.
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
                onClick={() => {
                  setTickets(prev => prev.filter((_, j) => j !== i));
                  setActiveTicket(Math.max(0, Math.min(activeTicket, tickets.length - 2)));
                }}
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
          Seleziona fino a 5 numeri. Il grafico si aggiorna immediatamente.
        </div>

        <div style={{ display: "flex", flexWrap: "wrap" }}>
          {Array.from({ length: 40 }, (_, i) => i + 1).map(n => (
            <Chip
              key={n}
              n={n}
              active={selectedNums.includes(n)}
              color={C.amber}
              onClick={() => toggleNumber(n)}
            />
          ))}
        </div>
      </div>

      <OverlayGraph draws={draws} ticket={selectedNums} />

      <div style={card}>
        <div style={{ fontSize: 13, fontWeight: 900 }}>
          PERSISTENZA PER POSIZIONE · DIAGNOSTICA
        </div>
        <div style={{ color: C.dim, fontSize: 10.5, margin: "4px 0 10px" }}>
          RUN = quante estrazioni consecutive hanno mantenuto lo stesso numero
          nella posizione. Il dato è diagnostico: non esclude automaticamente il candidato.
        </div>

        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 10.5 }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", padding: 6 }}>pos.</th>
                <th style={{ padding: 6 }}>n.</th>
                <th style={{ padding: 6 }}>RUN</th>
                <th style={{ padding: 6 }}>30g</th>
                <th style={{ padding: 6 }}>60g</th>
                <th style={{ padding: 6 }}>90g</th>
                <th style={{ padding: 6 }}>stato</th>
              </tr>
            </thead>
            <tbody>
              {persistenceRows.map(r => {
                const stateColor =
                  r.state === "PERSISTENTE" ? C.amber :
                  r.state === "IN ESAURIMENTO" ? C.ok :
                  C.dim;

                return (
                  <tr key={r.p} style={{ borderTop: `1px solid ${C.edge}` }}>
                    <td style={{ padding: 7, color: POS_COLORS[r.p], fontWeight: 900 }}>
                      {POS_LABELS[r.p]}
                    </td>
                    <td style={{ textAlign: "center", padding: 7, fontWeight: 900 }}>
                      {r.n ?? "—"}
                    </td>
                    <td style={{ textAlign: "center", padding: 7, fontWeight: 900 }}>
                      {r.run}
                    </td>
                    <td style={{ textAlign: "center", padding: 7 }}>
                      {(r.r30.rate * 100).toFixed(1)}%
                    </td>
                    <td style={{ textAlign: "center", padding: 7 }}>
                      {(r.r60.rate * 100).toFixed(1)}%
                    </td>
                    <td style={{ textAlign: "center", padding: 7 }}>
                      {(r.r90.rate * 100).toFixed(1)}%
                    </td>
                    <td style={{ textAlign: "center", padding: 7, color: stateColor, fontWeight: 900 }}>
                      {r.state}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div style={card}>
        <div style={{ fontSize: 13, fontWeight: 900 }}>
          NUMERO + RANK PER POSIZIONE
        </div>
        <div style={{ color: C.dim, fontSize: 10.5, margin: "4px 0 11px" }}>
          Rank storico specifico della posizione. Il dominio è corretto per P1→P5:
          P1 1–36, P2 2–37, P3 3–38, P4 4–39, P5 5–40.
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
      </div>

      <div style={card}>
        <div style={{ fontSize: 13, fontWeight: 900 }}>
          STORICO RANK PER POSIZIONE
        </div>
        <div style={{ color: C.dim, fontSize: 10.5, margin: "4px 0 10px" }}>
          Ultime 20 estrazioni, con rank calcolato usando solo il prefisso precedente.
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
      </div>

      <div style={{
        ...card,
        borderColor: C.edge,
        fontSize: 10.5,
        color: C.dim,
      }}>
        <b style={{ color: C.ink }}>Nota metodologica.</b>{" "}
        Trend e Memory sono rappresentazioni sperimentali dello stato storico.
        Il grafico confronta visivamente la cinquina selezionata con l'andamento
        reale; la diagnostica RUN/persistenza non costituisce un'esclusione automatica.
      </div>
    </div>
  );
}
