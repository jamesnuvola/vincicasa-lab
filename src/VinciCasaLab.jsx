import { useState, useMemo, useEffect } from "react";
import RAW from "./data.json";
import Verifica2 from "./Verifica2";
import TrendEngine from "./TrendEngine";
import TrendMemoryProjectionRank from "./TrendMemoryProjection_Rank";

/* ============ COSTANTI ============ */
const POS_COLORS = ["#ff4d6d", "#4fc46a", "#6a8bff", "#ffa040", "#c07ef5"];
const POS_LABELS = ["P1", "P2", "P3", "P4", "P5"];
const VALID_LO = [1, 2, 3, 4, 5];
const VALID_HI = [36, 37, 38, 39, 40];
const SMORFIA = [1, 8, 13, 17, 25, 33];
const T = {
  bg: "#0b1020", card: "#141b2e", edge: "#26304c", ink: "#e9edf7",
  dim: "#8f97b0", amber: "#f5b942", ok: "#49d18a", warn: "#ff6b6b",
};

/* ============ HELPERS PURI ============ */
const mk = (d) => d.slice(0, 7);
const prevMonth = (m) => {
  const [y, mo] = m.split("-").map(Number);
  const nm = mo === 1 ? [y - 1, 12] : [y, mo - 1];
  return nm[0] + "-" + String(nm[1]).padStart(2, "0");
};
const nextDate = (d) => {
  const dt = new Date(d + "T12:00:00");
  dt.setDate(dt.getDate() + 1);
  return dt.toISOString().slice(0, 10);
};
const fmtD = (d) => d.slice(8, 10) + "/" + String(Number(d.slice(5, 7)));

function isCrowded(c) {
  const s = [...c].sort((a, b) => a - b);
  if (s.every((n) => n <= 31)) return "tutti ≤31 (date)";
  const diffs = s.slice(1).map((v, i) => v - s[i]);
  let run = 1, mx = 1;
  for (const d of diffs) { run = d === 1 ? run + 1 : 1; mx = Math.max(mx, run); }
  if (mx >= 4) return "sequenza consecutiva";
  if (new Set(diffs).size === 1) return "progressione aritmetica";
  if (s.every((n) => n % 5 === 0)) return "tutti multipli di 5";
  if (s.filter((n) => SMORFIA.includes(n)).length >= 3) return "≥3 numeri smorfia";
  return null;
}

function ritornoPremio(p, n, k) {
  const prof = RAW.prof[p][n];
  if (!prof || k < 1 || k > prof.w) return 0;
  const w = prof.w;
  const intensity = 15 * (3 / Math.max(w, 3));
  const base = w > 1 ? (intensity * (w - k)) / (w - 1) : k === 1 ? intensity : 0;
  return base + (prof.h.includes(k) ? 3 : 0);
}

/* ============ SONAR DECISION ENGINE ============ */
function overlapCount(a, b) {
  const sb = new Set(b);
  return a.reduce((n, x) => n + (sb.has(x) ? 1 : 0), 0);
}

function sonarTransitionProfile(draws, current) {
  const last = draws.length - 1;
  const recent = draws.slice(Math.max(0, last - 4), last + 1);
  const freq = {};
  for (const d of recent) for (const n of d.n) freq[n] = (freq[n] || 0) + 1;

  const transition = {};
  for (let i = 0; i < draws.length - 1; i++) {
    const a = new Set(draws[i].n);
    const b = new Set(draws[i + 1].n);
    for (const n of a) {
      if (!transition[n]) transition[n] = { stay: 0, out: 0, next: {} };
      if (b.has(n)) transition[n].stay += 1;
      else transition[n].out += 1;
    }
    for (const n of b) {
      if (!transition[n]) transition[n] = { stay: 0, out: 0, next: {} };
      transition[n].next[n] = (transition[n].next[n] || 0) + 1;
    }
  }

  const rows = Array.from({ length: 40 }, (_, i) => i + 1).map((n) => {
    const t = transition[n] || { stay: 0, out: 0 };
    const total = t.stay + t.out;
    const persistence = total ? t.stay / total : 0;
    const recentPresence = freq[n] || 0;
    const inCurrent = current.includes(n);
    return { n, persistence, recentPresence, inCurrent };
  });
  return rows;
}

function sonarAnalogCore(draws) {
  if (draws.length < 8) return {
    regime: "DATI INSUFFICIENTI",
    current: draws[draws.length - 1]?.n || [],
    analogs: [], core: [], completion: [], ticket: [], trajectory: [],
  };

  const current = draws[draws.length - 1].n;
  const candidates = [];
  for (let i = 0; i < draws.length - 1; i++) {
    const ov = overlapCount(current, draws[i].n);
    if (ov >= 3) {
      const successor = draws[i + 1];
      candidates.push({
        index: i,
        date: draws[i].d,
        overlap: ov,
        successor: successor.n,
        successorDate: successor.d,
        weight: Math.pow(ov, 3),
      });
    }
  }

  const votes = {};
  for (const a of candidates) {
    for (const n of a.successor) {
      votes[n] = (votes[n] || 0) + a.weight;
    }
  }
  const analogRank = Object.keys(votes).map(Number).sort((a, b) => votes[b] - votes[a] || a - b);
  const maxOverlap = candidates.length ? Math.max(...candidates.map((x) => x.overlap)) : 0;
  const best = candidates.filter((x) => x.overlap === maxOverlap).slice(-6).reverse();

  const trajectory = sonarTransitionProfile(draws, current);
  const trajMap = Object.fromEntries(trajectory.map((x) => [x.n, x]));

  // CORE: preserve the strongest successor signal from historical 3+ overlap analogs.
  const core = analogRank
    .slice(0, 12)
    .sort((a, b) => {
      const va = votes[a] * (1 + 0.15 * trajMap[a].recentPresence);
      const vb = votes[b] * (1 + 0.15 * trajMap[b].recentPresence);
      return vb - va || a - b;
    })
    .slice(0, 3);

  // Completion layers: independent signals, used only after the analog core.
  const recent14 = draws.slice(-14);
  const rel = {};
  for (const d of recent14) for (const n of d.n) rel[n] = (rel[n] || 0) + 1;
  const completionPool = Array.from({ length: 40 }, (_, i) => i + 1)
    .filter((n) => !core.includes(n))
    .map((n) => ({
      n,
      analog: votes[n] || 0,
      relation: rel[n] || 0,
      persistence: trajMap[n].persistence,
      recent: trajMap[n].recentPresence,
    }))
    .sort((a, b) => {
      const sa = 0.55 * a.analog + 1.8 * a.relation + 2.2 * a.persistence + 0.7 * a.recent;
      const sb = 0.55 * b.analog + 1.8 * b.relation + 2.2 * b.persistence + 0.7 * b.recent;
      return sb - sa || a.n - b.n;
    });

  const completion = completionPool.slice(0, 2).map((x) => x.n);
  let ticket = [...core, ...completion].sort((a, b) => a - b);

  // Keep the ticket structurally distinct: if completion duplicates a very strong
  // analog successor, replace only the weaker completion slot with the next candidate.
  if (new Set(ticket).size < 5) {
    for (const x of completionPool) {
      if (!ticket.includes(x.n)) { ticket.push(x.n); ticket = [...new Set(ticket)].sort((a, b) => a - b); }
      if (ticket.length === 5) break;
    }
  }

  const regime = maxOverlap >= 3 && candidates.length >= 1
    ? (maxOverlap >= 4 ? "ANALOG CORE · FORTE" : "ANALOG CORE · ATTIVO")
    : "MIXED / COMPLETION";

  return {
    regime,
    current,
    analogs: best,
    core,
    completion,
    ticket: ticket.slice(0, 5),
    trajectory: trajectory.filter((x) => x.inCurrent).sort((a, b) => b.recentPresence - a.recentPresence),
    votes,
    maxOverlap,
    candidateCount: candidates.length,
  };
}

function SonarOverlayGraph({ draws, ticket }) {
  const rows = draws.slice(-15);
  const selected = [...new Set(ticket || [])].filter((n) => Number.isInteger(n)).sort((a, b) => a - b);
  if (!rows.length || selected.length !== 5) return null;

  const W = 820, H = 380, PADL = 34, PADR = 34, PADT = 28, PADB = 52;
  const plotW = W - PADL - PADR;
  const plotH = H - PADT - PADB;
  const totalPoints = rows.length + 1;
  const x = (i) => PADL + (i * plotW) / (totalPoints - 1);
  const y = (v) => PADT + ((40 - v) * plotH) / 40;
  const labelDy = (i, p) => {
    const v = rows[i].n[p];
    for (let q = 0; q < 5; q++) {
      if (q !== p && rows[i].n[q] > v && rows[i].n[q] - v <= 3) return 15;
    }
    return -8;
  };
  const projectionPath = (p) => {
    const x0 = x(rows.length - 1);
    const x1 = x(rows.length);
    const y0 = y(rows[rows.length - 1].n[p]);
    const y1 = y(selected[p]);
    const xm = (x0 + x1) / 2;
    const yc = y0 + (y1 - y0) * 0.50;
    return `M ${x0} ${y0} Q ${xm} ${yc} ${x1} ${y1}`;
  };

  return (
    <Card title="Andamento + onda di proiezione" sub="15 estrazioni reali · tratto finale = cinquina SONAR proposta">
      <div style={{ overflowX: "auto" }}>
        <svg viewBox={`0 0 ${W} ${H}`} style={{ minWidth: 620, width: "100%", display: "block" }}>
          {[5, 10, 20, 30, 40].map((g) => (
            <g key={g}>
              <line x1={PADL} x2={W - PADR} y1={y(g)} y2={y(g)} stroke="#1b2340" strokeWidth="1" />
              <text x={7} y={y(g) + 3} fontSize="9" fill={T.dim}>{g}</text>
            </g>
          ))}

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
                  <circle cx={x(i)} cy={y(dr.n[p])} r="3.1" fill={POS_COLORS[p]} opacity="0.88" />
                  <text x={x(i)} y={y(dr.n[p]) + labelDy(i, p)} textAnchor="middle" fontSize="9.5" fontWeight="700" fill={POS_COLORS[p]} fontFamily="ui-monospace, monospace">
                    {dr.n[p]}
                  </text>
                </g>
              ))}

              <path d={projectionPath(p)} fill="none" stroke={POS_COLORS[p]} strokeWidth="3" strokeDasharray="7 5" opacity="0.98" />
              <circle cx={x(rows.length)} cy={y(selected[p])} r="5" fill={POS_COLORS[p]} />
              <text x={x(rows.length)} y={y(selected[p]) - 10} textAnchor="middle" fontSize="11" fontWeight="900" fill={POS_COLORS[p]} fontFamily="ui-monospace, monospace">
                {selected[p]}
              </text>
            </g>
          ))}

          {rows.map((dr, i) => (
            <text key={i} x={x(i)} y={H - 10} textAnchor="middle" fontSize="8.5" fill={T.dim}
              transform={`rotate(-45 ${x(i)} ${H - 10})`}>
              {fmtD(dr.d)}
            </text>
          ))}
          <text x={x(rows.length)} y={H - 10} textAnchor="middle" fontSize="9" fontWeight="800" fill={T.amber}
            transform={`rotate(-45 ${x(rows.length)} ${H - 10})`}>
            {fmtD(nextDate(rows[rows.length - 1].d))}
          </text>
        </svg>
      </div>
      <div style={{ display: "flex", gap: 12, marginTop: 5, flexWrap: "wrap" }}>
        {POS_LABELS.map((l, p) => <span key={p} style={{ fontSize: 11, color: POS_COLORS[p], fontWeight: 700 }}>● {l} → {selected[p]}</span>)}
      </div>
    </Card>
  );
}

/* ============ COMPONENTE ============ */
export default function VinciCasaLab() {
  const [tab, setTab] = useState("andamento");
  const LS_KEY = "vincicasa-lab-estrazioni";
  const [extra, setExtra] = useState(() => {
    try { const s = localStorage.getItem(LS_KEY); return s ? JSON.parse(s) : []; } catch { return []; }
  });
  useEffect(() => { try { localStorage.setItem(LS_KEY, JSON.stringify(extra)); } catch {} }, [extra]);
  const [wRit, setWRit] = useState(10);
  const [wAtt, setWAtt] = useState(10);
  const [nucMesi, setNucMesi] = useState(3);
  const [inD, setInD] = useState("");
  const [inN, setInN] = useState(["", "", "", "", ""]);
  const [inErr, setInErr] = useState("");

  const draws = useMemo(() => {
    const seen = new Set(RAW.draws.map((x) => x.d));
    const extraOk = extra.filter((x) => !seen.has(x.d));
    return [...RAW.draws, ...extraOk].sort((a, b) => a.d.localeCompare(b.d));
  }, [extra]);

  const lastDraw = draws[draws.length - 1];
  const prevDraw = draws[draws.length - 2];
  const curMonth = mk(lastDraw.d);
  const drawsMese = draws.filter((dr) => mk(dr.d) === curMonth).length;

  const monthCounts = useMemo(() => {
    const out = Array.from({ length: 5 }, () => ({}));
    for (const dr of draws) {
      if (mk(dr.d) === curMonth) {
        for (let p = 0; p < 5; p++) out[p][dr.n[p]] = (out[p][dr.n[p]] || 0) + 1;
      }
    }
    return out;
  }, [draws, curMonth]);

  const occ = useMemo(() => {
    const o = Array.from({ length: 5 }, () => ({}));
    draws.forEach((dr, i) => {
      for (let p = 0; p < 5; p++) {
        const n = dr.n[p];
        (o[p][n] = o[p][n] || []).push(i);
      }
    });
    return o;
  }, [draws]);

  const lastBefore = (p, n, i) => {
    const L = occ[p][n];
    if (!L) return -1;
    let r = -1;
    for (const x of L) { if (x < i) r = x; else break; }
    return r;
  };

  const monthsAvailable = useMemo(() => new Set(draws.map((d) => mk(d.d))), [draws]);
  const firstMonth = mk(draws[0].d);
  const nucleoOf = (p, targetMonth, k) => {
    const ms = [];
    let m = targetMonth;
    for (let j = 0; j < k; j++) { m = prevMonth(m); ms.push(m); }
    if (ms.some((m2) => !monthsAvailable.has(m2) || m2 < firstMonth)) return null;
    const lo = VALID_LO[p], hi = VALID_HI[p];
    const out = [];
    for (let n = lo; n <= hi; n++) {
      const ok = ms.every((m2) => draws.some((dr) => mk(dr.d) === m2 && dr.n[p] === n));
      if (ok) out.push(n);
    }
    return out;
  };

  const attesiAt = (p, i) => {
    const ref = i < draws.length ? draws[i] : draws[draws.length - 1];
    const m = mk(ref.d);
    const nuc = nucleoOf(p, m, nucMesi);
    if (!nuc) return null;
    const out = new Set(nuc);
    for (let j = 0; j < i; j++) {
      if (mk(draws[j].d) === m) out.delete(draws[j].n[p]);
    }
    return out;
  };

  const maxFreq = useMemo(
    () => Array.from({ length: 5 }, (_, p) => Math.max(...Object.values(RAW.freq[p]))),
    []
  );
  const scoresAt = (p, i) => {
    const att = attesiAt(p, i);
    const lo = VALID_LO[p], hi = VALID_HI[p];
    const rows = [];
    for (let n = lo; n <= hi; n++) {
      const fl = (100 * RAW.freq[p][n]) / maxFreq[p];
      const lb = lastBefore(p, n, i);
      const rit = lb >= 0 ? ritornoPremio(p, n, i - lb) : 0;
      const at = att && att.has(n);
      const sc = fl + (wRit / 10) * rit + (at ? wAtt : 0);
      rows.push({ n, sc, fl, rit, at: !!at });
    }
    rows.sort((a, b) => b.sc - a.sc);
    rows.forEach((r, idx) => (r.rank = idx + 1));
    return rows;
  };

  const ranksNow = useMemo(
    () => Array.from({ length: 5 }, (_, p) => scoresAt(p, draws.length)),
    [draws, wRit, wAtt, nucMesi]
  );

  const rankLookup = useMemo(
    () => ranksNow.map((rowsP) => {
      const m = {};
      rowsP.forEach((r) => (m[r.n] = r.rank));
      return m;
    }),
    [ranksNow]
  );

  const nucleoNow = useMemo(
    () => Array.from({ length: 5 }, (_, p) => nucleoOf(p, curMonth, nucMesi)),
    [draws, nucMesi]
  );
  const attesiNow = useMemo(
    () => Array.from({ length: 5 }, (_, p) => attesiAt(p, draws.length)),
    [draws, nucMesi]
  );

  const [sonarTick, setSonarTick] = useState(0);
  const sonar = useMemo(() => sonarAnalogCore(draws), [draws, sonarTick]);

  const addDraw = () => {
    setInErr("");
    const d = inD || nextDate(lastDraw.d);
    const nums = inN.map((x) => parseInt(x, 10));
    if (nums.some((x) => !Number.isInteger(x))) return setInErr("Inserisci 5 numeri.");
    for (let i = 0; i < 5; i++) {
      if (nums[i] < 1 || nums[i] > 40) return setInErr("Numeri tra 1 e 40.");
      if (i > 0 && nums[i] <= nums[i - 1]) return setInErr("Numeri in ordine crescente stretto.");
    }
    if (draws.some((dr) => dr.d === d)) return setInErr("Data già presente.");
    setExtra((e) => [...e, { d, n: nums }]);
    setInN(["", "", "", "", ""]);
    setInD("");
  };

  const last15 = draws.slice(-15);
  const W = 740, H = 330, PADX = 26, PADT = 26, PADB = 40;
  const x = (i) => PADX + (i * (W - 2 * PADX)) / 14;
  const y = (v) => PADT + ((40 - v) * (H - PADT - PADB)) / 40;

  const fascia = (p, v) => {
    const idx = Object.keys(RAW.freq[p])
      .map(Number)
      .sort((a, b) => RAW.freq[p][b] - RAW.freq[p][a])
      .indexOf(v);
    if (idx >= 0 && idx < 3) return ["zona forte", T.ok];
    if (idx < 8) return ["zona media", T.amber];
    return ["fuori zona", T.warn];
  };

  const Chip = ({ n, color, ring, dim, badge }) => (
    <span style={{
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      minWidth: 30, height: 30, borderRadius: 8, margin: 3, padding: "0 5px",
      background: dim ? "transparent" : "#1c2540",
      border: "1px solid " + (ring ? T.amber : T.edge),
      color: color || T.ink, fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
      fontSize: 14, fontWeight: 600, opacity: dim ? 0.35 : 1,
      boxShadow: ring ? "0 0 0 1px " + T.amber : "none",
    }}>
      {n}
      {badge > 0 && <span style={{ fontSize: 9, marginLeft: 3, color: T.ok, fontWeight: 800 }}>×{badge}</span>}
    </span>
  );

  const TabBtn = ({ id, label }) => (
    <button
      onClick={() => setTab(id)}
      style={{
        flex: "1 0 auto", minWidth: 62, padding: "10px 6px", background: tab === id ? "#1d2745" : "transparent",
        color: tab === id ? T.ink : T.dim, border: "none",
        borderBottom: tab === id ? "2px solid " + T.amber : "2px solid transparent",
        fontSize: 12, fontWeight: 700, letterSpacing: 0.4, cursor: "pointer",
      }}
    >
      {label}
    </button>
  );

  const Card = ({ title, children, sub }) => (
    <div style={{ background: T.card, border: "1px solid " + T.edge, borderRadius: 14, padding: 14, marginBottom: 14 }}>
      {title && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 13, fontWeight: 800, letterSpacing: 1.2, textTransform: "uppercase", color: T.ink }}>{title}</div>
          {sub && <div style={{ fontSize: 11.5, color: T.dim, marginTop: 2 }}>{sub}</div>}
        </div>
      )}
      {children}
    </div>
  );

  const labelDy = (col, p) => {
    const v = last15[col].n[p];
    for (let q = 0; q < 5; q++) {
      if (q !== p) {
        const u = last15[col].n[q];
        if (u > v && u - v <= 3) return 15;
      }
    }
    return -8;
  };

  return (
    <div style={{ minHeight: "100vh", background: T.bg, color: T.ink, fontFamily: "-apple-system, system-ui, sans-serif", paddingBottom: 40 }}>
      <div style={{ padding: "18px 16px 10px" }}>
        <div style={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: 20, fontWeight: 800, letterSpacing: 3 }}>
          VINCICASA<span style={{ color: T.amber }}> · LAB</span>
        </div>
        <div style={{ fontSize: 11.5, color: T.dim, marginTop: 2 }}>
          strategia nucleo di Jimmy · ultima estrazione {fmtD(lastDraw.d)} · storico {RAW.histN + extra.length} estrazioni
        </div>
      </div>

      <div style={{ padding: "0 16px" }}>
        <Card title="Aggiungi estrazione" sub="di norma ci pensa l'aggiornamento automatico; qui puoi inserirla a mano se serve">
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
            <input
              type="date" value={inD} onChange={(e) => setInD(e.target.value)}
              placeholder={nextDate(lastDraw.d)}
              style={{ background: "#0f1526", border: "1px solid " + T.edge, color: T.ink, borderRadius: 8, padding: "8px 8px", fontSize: 13 }}
            />
            {inN.map((v, i) => (
              <input
                key={i} inputMode="numeric" value={v}
                onChange={(e) => setInN((a) => a.map((x, j) => (j === i ? e.target.value.replace(/\D/g, "").slice(0, 2) : x)))}
                placeholder={POS_LABELS[i]}
                style={{ width: 44, background: "#0f1526", border: "1px solid " + T.edge, color: POS_COLORS[i], borderRadius: 8, padding: "8px 4px", fontSize: 14, textAlign: "center", fontFamily: "ui-monospace, monospace", fontWeight: 700 }}
              />
            ))}
            <button onClick={addDraw} style={{ background: T.amber, color: "#1a1405", border: "none", borderRadius: 8, padding: "9px 14px", fontWeight: 800, fontSize: 13, cursor: "pointer" }}>
              Aggiungi
            </button>
          </div>
          {inErr && <div style={{ color: T.warn, fontSize: 12, marginTop: 6 }}>{inErr}</div>}
          {extra.length > 0 && (
            <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <span style={{ fontSize: 12, color: T.dim }}>{extra.length} estrazioni aggiunte a mano su questo dispositivo</span>
              <button onClick={() => setExtra([])} style={{ background: "transparent", color: T.warn, border: "1px solid " + T.edge, borderRadius: 8, padding: "5px 10px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>Rimuovi</button>
            </div>
          )}
        </Card>
      </div>

      <div style={{ display: "flex", position: "sticky", top: 0, background: T.bg, zIndex: 5, borderBottom: "1px solid " + T.edge, margin: "0 0 14px", overflowX: "auto" }}>
        <TabBtn id="andamento" label="ANDAMENTO" />
        <TabBtn id="nucleo" label="NUCLEO" />
        <TabBtn id="rank" label="RANK" />
        <TabBtn id="gioca" label="SONAR" />
        <TabBtn id="verifica" label="VERIFICA 2.0" />
        <TabBtn id="trend" label="TREND" />
        <TabBtn id="proiezione" label="PROIEZIONE" />
        <TabBtn id="matrice" label="GRIGLIA" />
      </div>

      <div style={{ padding: "0 16px" }}>
        {tab === "andamento" && (
          <>
            <Card title="Ultime 15 estrazioni" sub="una linea per posizione, numero estratto su ogni punto">
              <div style={{ overflowX: "auto" }}>
                <svg viewBox={"0 0 " + W + " " + H} style={{ minWidth: 560, width: "100%" }}>
                  {[10, 20, 30, 40].map((g) => (
                    <g key={g}>
                      <line x1={PADX} x2={W - PADX} y1={y(g)} y2={y(g)} stroke="#1b2340" strokeWidth="1" />
                      <text x={6} y={y(g) + 3} fontSize="9" fill={T.dim}>{g}</text>
                    </g>
                  ))}
                  {Array.from({ length: 5 }, (_, p) => (
                    <g key={p}>
                      <polyline fill="none" stroke={POS_COLORS[p]} strokeWidth="1.6" strokeDasharray="5 4"
                        points={last15.map((dr, i) => x(i) + "," + y(dr.n[p])).join(" ")} />
                      {last15.map((dr, i) => (
                        <g key={i}>
                          <circle cx={x(i)} cy={y(dr.n[p])} r="3.4" fill={POS_COLORS[p]} />
                          <text x={x(i)} y={y(dr.n[p]) + labelDy(i, p)} textAnchor="middle"
                            fontSize="10.5" fontWeight="700" fill={POS_COLORS[p]} fontFamily="ui-monospace, monospace">
                            {dr.n[p]}
                          </text>
                        </g>
                      ))}
                    </g>
                  ))}
                  {last15.map((dr, i) => (
                    <text key={i} x={x(i)} y={H - 8} textAnchor="middle" fontSize="9" fill={T.dim}
                      transform={"rotate(-45 " + x(i) + " " + (H - 8) + ")"}>
                      {fmtD(dr.d)}
                    </text>
                  ))}
                </svg>
              </div>
              <div style={{ display: "flex", gap: 12, marginTop: 6, flexWrap: "wrap" }}>
                {POS_LABELS.map((l, p) => <span key={p} style={{ fontSize: 11, color: POS_COLORS[p], fontWeight: 700 }}>● {l}</span>)}
              </div>
            </Card>
            <Card title="Spostamento vs estrazione precedente" sub={fmtD(prevDraw.d) + " → " + fmtD(lastDraw.d) + " · delta per posizione"}>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {Array.from({ length: 5 }, (_, p) => {
                  const dv = lastDraw.n[p] - prevDraw.n[p];
                  return (
                    <div key={p} style={{ flex: "1 1 110px", background: "#101830", border: "1px solid " + T.edge, borderRadius: 10, padding: 10 }}>
                      <div style={{ fontSize: 11, color: POS_COLORS[p], fontWeight: 800 }}>{POS_LABELS[p]}</div>
                      <div style={{ fontFamily: "ui-monospace, monospace", fontSize: 20, fontWeight: 800 }}>{prevDraw.n[p]} → {lastDraw.n[p]}</div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: dv > 0 ? T.ok : dv < 0 ? T.warn : T.dim }}>
                        {dv > 0 ? "▲ +" + dv : dv < 0 ? "▼ " + dv : "= 0"}
                      </div>
                    </div>
                  );
                })}
              </div>
              <div style={{ marginTop: 10, fontSize: 12.5, color: T.dim }}>
                Posizioni salite: <b style={{ color: T.ok }}>{lastDraw.n.filter((v, p) => v > prevDraw.n[p]).length}</b> ·
                scese: <b style={{ color: T.warn }}> {lastDraw.n.filter((v, p) => v < prevDraw.n[p]).length}</b>
              </div>
              <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}>
                {[0, 4].map((p) => {
                  const [lbl, col] = fascia(p, lastDraw.n[p]);
                  return <div key={p} style={{ fontSize: 12.5 }}>
                    <span style={{ color: POS_COLORS[p], fontWeight: 800 }}>{POS_LABELS[p]}={lastDraw.n[p]}</span>{" "}
                    <span style={{ color: col, fontWeight: 700 }}>{lbl}</span>
                  </div>;
                })}
              </div>
            </Card>
          </>
        )}

        {tab === "nucleo" && (
          <>
            <Card title={"Nucleo (" + nucMesi + " mesi) — mese " + curMonth}
              sub={drawsMese + " estrazioni nel mese · ×n = uscite del mese (conteggio azzerato a inizio mese) · bordo ambra = atteso"}>
              <div style={{ marginBottom: 10 }}>
                {[2, 3].map((k) => (
                  <button key={k} onClick={() => setNucMesi(k)}
                    style={{ marginRight: 8, padding: "6px 12px", borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: "pointer",
                      background: nucMesi === k ? T.amber : "#101830", color: nucMesi === k ? "#1a1405" : T.dim, border: "1px solid " + T.edge }}>
                    {k} mesi
                  </button>
                ))}
              </div>
              {Array.from({ length: 5 }, (_, p) => (
                <div key={p} style={{ marginBottom: 8 }}>
                  <div style={{ fontSize: 12, fontWeight: 800, color: POS_COLORS[p], marginBottom: 2 }}>{POS_LABELS[p]}</div>
                  <div>
                    {(nucleoNow[p] || []).map((n) => <Chip key={n} n={n} color={POS_COLORS[p]} ring={attesiNow[p] && attesiNow[p].has(n)} badge={monthCounts[p][n] || 0} />)}
                    {nucleoNow[p] === null && <span style={{ fontSize: 12, color: T.dim }}>servono più mesi di dati</span>}
                  </div>
                  {(() => {
                    const fuori = Object.keys(monthCounts[p]).map(Number).filter((x) => !(nucleoNow[p] || []).includes(x)).sort((a, b) => a - b);
                    return fuori.length > 0 ? <div style={{ fontSize: 11.5, color: T.dim, marginTop: 2 }}>
                      fuori nucleo questo mese: {fuori.map((x) => x + "×" + monthCounts[p][x]).join(", ")}
                    </div> : null;
                  })()}
                </div>
              ))}
            </Card>
            <Card title="Attesi — timing" sub="nota storica del vecchio modello">
              <div style={{ fontSize: 13, lineHeight: 1.55, color: T.ink }}>
                Questa nota appartiene al modello precedente. Per le verifiche metodologiche usare la scheda <b style={{ color: T.amber }}>VERIFICA 2.0</b>, che ricostruisce i punteggi senza usare statistiche future.
              </div>
            </Card>
          </>
        )}

        {tab === "rank" && (
          <>
            <Card title="Pesi degli indicatori" sub="pavimento (0–100 per posizione) + ritorno + bonus attesi">
              <div style={{ fontSize: 12.5, marginBottom: 6 }}>
                Ritorno ×{(wRit / 10).toFixed(1)}
                <input type="range" min="0" max="30" value={wRit} onChange={(e) => setWRit(+e.target.value)} style={{ width: "100%" }} />
              </div>
              <div style={{ fontSize: 12.5 }}>
                Bonus atteso +{wAtt}
                <input type="range" min="0" max="30" value={wAtt} onChange={(e) => setWAtt(+e.target.value)} style={{ width: "100%" }} />
              </div>
            </Card>
            {Array.from({ length: 5 }, (_, p) => (
              <Card key={p} title={POS_LABELS[p] + " — top 10"} sub="badge: A = atteso · R = ritorno attivo">
                {ranksNow[p].slice(0, 10).map((r) => (
                  <div key={r.n} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                    <span style={{ width: 22, fontSize: 11, color: T.dim, fontFamily: "ui-monospace, monospace" }}>{r.rank}</span>
                    <span style={{ width: 30, textAlign: "center", fontFamily: "ui-monospace, monospace", fontWeight: 800, fontSize: 15, color: POS_COLORS[p] }}>{r.n}</span>
                    <div style={{ flex: 1, height: 8, background: "#0f1526", borderRadius: 4, overflow: "hidden" }}>
                      <div style={{ width: Math.min(100, r.sc) + "%", height: "100%", background: POS_COLORS[p], opacity: 0.85 }} />
                    </div>
                    <span style={{ width: 40, fontSize: 11, color: T.dim, textAlign: "right", fontFamily: "ui-monospace, monospace" }}>{r.sc.toFixed(0)}</span>
                    <span style={{ width: 34, fontSize: 10, fontWeight: 800 }}>
                      {r.at && <span style={{ color: T.amber }}>A </span>}
                      {r.rit > 0 && <span style={{ color: T.ok }}>R</span>}
                    </span>
                  </div>
                ))}
              </Card>
            ))}
          </>
        )}

        {tab === "gioca" && (
          <>
            <Card title="SONAR — Decision Engine" sub="Analog Core → traiettoria → completamento · calcolo deterministico">
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 10 }}>
                <span style={{ fontSize: 11, color: T.dim }}>REGIME</span>
                <span style={{ fontSize: 12, fontWeight: 800, color: T.amber }}>{sonar.regime}</span>
                <span style={{ fontSize: 11, color: T.dim }}>· analoghi ≥3: {sonar.candidateCount || 0}</span>
                <span style={{ fontSize: 11, color: T.dim }}>· overlap max: {sonar.maxOverlap || 0}</span>
              </div>
              <div style={{ textAlign: "center", margin: "8px 0 12px" }}>
                {sonar.ticket.map((n) => <Chip key={n} n={n} color={T.amber} />)}
              </div>
              <div style={{ textAlign: "center", fontSize: 11.5, color: T.dim, lineHeight: 1.45 }}>
                Cinquina SONAR calcolata senza casualità. Il blocco CORE viene dall'analogia storica; i numeri di completamento entrano solo dopo il CORE.
              </div>
              <button onClick={() => setSonarTick((x) => x + 1)}
                style={{ marginTop: 10, background: T.amber, color: "#1a1405", border: "none", borderRadius: 9, padding: "8px 14px", fontWeight: 800, fontSize: 12, cursor: "pointer", width: "100%" }}>
                Ricalcola SONAR
              </button>
            </Card>

            <SonarOverlayGraph draws={draws} ticket={sonar.ticket} />

            <Card title="Analog Core" sub="successori dei precedenti con sovrapposizione ≥3; peso = overlap³">
              {sonar.analogs.length === 0 ? (
                <div style={{ color: T.dim, fontSize: 12.5 }}>Nessun analogo storico con sovrapposizione sufficiente.</div>
              ) : sonar.analogs.map((a, i) => (
                <div key={a.index} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 7 }}>
                  <span style={{ width: 18, color: T.dim, fontSize: 11 }}>{i + 1}</span>
                  <span style={{ width: 70, fontSize: 11, color: T.dim }}>{fmtD(a.date)}</span>
                  <span style={{ width: 38, fontSize: 11, fontWeight: 800, color: T.amber }}>ov{a.overlap}</span>
                  <span style={{ flex: 1, fontFamily: "ui-monospace, monospace", fontSize: 12 }}>{a.successor.join(" · ")}</span>
                  <span style={{ fontSize: 10, color: T.dim }}>{fmtD(a.successorDate)}</span>
                </div>
              ))}
              <div style={{ marginTop: 9, fontSize: 12, color: T.dim }}>
                <b style={{ color: T.ink }}>CORE:</b>{" "}{sonar.core.join(" · ") || "—"}
              </div>
            </Card>

            <Card title="Traiettoria" sub="lettura della persistenza recente dei numeri dell'ultima estrazione">
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {sonar.trajectory.map((r) => (
                  <div key={r.n} style={{ background: "#101830", border: "1px solid " + T.edge, borderRadius: 9, padding: "7px 9px", minWidth: 70, textAlign: "center" }}>
                    <div style={{ fontSize: 17, fontWeight: 800, fontFamily: "ui-monospace, monospace" }}>{r.n}</div>
                    <div style={{ fontSize: 10, color: T.dim }}>{r.recentPresence}/5 recenti</div>
                    <div style={{ fontSize: 10, color: r.persistence >= 0.5 ? T.ok : T.warn }}>stay {(100 * r.persistence).toFixed(0)}%</div>
                  </div>
                ))}
              </div>
            </Card>

            <Card title="Completamento" sub="Relation + persistenza + segnale analogico, applicati solo dopo il CORE">
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {sonar.completion.map((n) => <Chip key={n} n={n} color={T.ok} />)}
              </div>
            </Card>

            <Card title="Nota metodologica" sub="uso corretto del motore">
              <div style={{ fontSize: 12.5, color: T.dim, lineHeight: 1.55 }}>
                SONAR tratta l'analogia storica come segnale principale quando esiste un precedente con almeno 3 numeri in comune. Trend, relazione e persistenza non possono sostituire il CORE: servono a completare la cinquina. Il risultato è esplorativo e non costituisce una previsione garantita dell'estrazione successiva.
              </div>
            </Card>
          </>
        )}

        {tab === "verifica" && <Verifica2 draws={draws} />}

        {tab === "trend" && <TrendEngine draws={draws} />}

        {tab === "proiezione" && <TrendMemoryProjectionRank draws={draws} />}

        {tab === "matrice" && (() => {
          const rankBg = (r) => (r <= 3 ? "#12512b" : r <= 8 ? "#16412a" : r <= 12 ? "#1a2a2a" : r <= 18 ? "#1a2138" : "#12172a");
          const rankInk = (r) => (r <= 8 ? "#c9ffd8" : r <= 18 ? T.ink : T.dim);
          return (
            <>
              <Card title="Griglia rank" sub={"numero in verticale, posizione in orizzontale · pesi correnti · mese " + curMonth}>
                <div style={{ display: "flex", gap: 12, flexWrap: "wrap", fontSize: 11, color: T.dim, marginBottom: 8 }}>
                  <span><span style={{ display: "inline-block", width: 10, height: 10, background: "#12512b", borderRadius: 2, marginRight: 4, verticalAlign: "middle" }} />rank basso = forte</span>
                  <span><span style={{ display: "inline-block", width: 10, height: 10, border: "1px solid " + T.amber, borderRadius: 2, marginRight: 4, verticalAlign: "middle" }} />atteso</span>
                  <span><span style={{ display: "inline-block", width: 8, height: 8, background: T.ok, borderRadius: 8, marginRight: 4, verticalAlign: "middle" }} />gia' uscito nel mese</span>
                  <span>–  impossibile</span>
                </div>
                <div style={{ overflowX: "auto" }}>
                  <table style={{ borderCollapse: "collapse", fontFamily: "ui-monospace, monospace", fontSize: 12 }}>
                    <thead>
                      <tr>
                        <th style={{ position: "sticky", left: 0, background: T.bg, padding: "4px 6px", color: T.dim, fontSize: 11 }}>n</th>
                        {POS_LABELS.map((l, p) => <th key={p} style={{ padding: "4px 8px", color: POS_COLORS[p], fontSize: 12 }}>{l}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {Array.from({ length: 40 }, (_, ni) => {
                        const n = ni + 1;
                        return (
                          <tr key={n}>
                            <td style={{ position: "sticky", left: 0, background: T.bg, padding: "3px 6px", color: T.dim, fontWeight: 700, textAlign: "right" }}>{n}</td>
                            {Array.from({ length: 5 }, (_, p) => {
                              if (n < VALID_LO[p] || n > VALID_HI[p]) {
                                return <td key={p} style={{ background: "#0a0e18", color: "#2c3350", textAlign: "center", padding: "3px 8px", border: "1px solid #0c1120" }}>–</td>;
                              }
                              const rank = rankLookup[p][n];
                              const at = attesiNow[p] && attesiNow[p].has(n);
                              const cnt = monthCounts[p][n] || 0;
                              return (
                                <td key={p} style={{ position: "relative", background: rankBg(rank), color: rankInk(rank), textAlign: "center", padding: "3px 8px", minWidth: 30, border: at ? "1px solid " + T.amber : "1px solid #0e1526", fontWeight: rank <= 8 ? 700 : 400 }}>
                                  {rank}
                                  {cnt > 0 && <span style={{ position: "absolute", top: 1, right: 2, width: 6, height: 6, borderRadius: 6, background: T.ok }} title={"uscito " + cnt + "x"} />}
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div style={{ fontSize: 11, color: T.dim, marginTop: 8 }}>
                  Il rank combina pavimento + ritorno + bonus attesi (regolabili nella scheda RANK). Un pallino verde con piu' presenze indica un numero gia' uscito piu' volte nel mese.
                </div>
              </Card>
            </>
          );
        })()}
      </div>
    </div>
  );
}
