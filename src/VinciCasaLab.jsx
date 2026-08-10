import { useState, useMemo, useEffect } from "react";
import RAW from "./data.json";

/* ============ COSTANTI ============ */
const POS_COLORS = ["#ff4d6d", "#4fc46a", "#6a8bff", "#ffa040", "#c07ef5"];
const POS_LABELS = ["P1", "P2", "P3", "P4", "P5"];
const VALID_LO = [1, 2, 3, 4, 5];
const VALID_HI = [36, 37, 38, 39, 40];
const CAP = [10, 15, 15, 15, 10];
const SMORFIA = [1, 8, 13, 17, 25, 33];
const T = {
  bg: "#0b1020", card: "#141b2e", edge: "#26304c", ink: "#e9edf7",
  dim: "#8f97b0", amber: "#f5b942", ok: "#49d18a", warn: "#ff6b6b",
};

/* ============ HELPERS PURI ============ */
const mk = (d) => d.slice(0, 7); // '2026-08'
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

/* ============ COMPONENTE ============ */
export default function VinciCasaLab() {
  const [tab, setTab] = useState("andamento");
  const LS_KEY = "vincicasa-lab-estrazioni";
  const [extra, setExtra] = useState(() => {
    try {
      const s = localStorage.getItem(LS_KEY);
      return s ? JSON.parse(s) : [];
    } catch {
      return [];
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(extra));
    } catch {}
  }, [extra]);
  const [wRit, setWRit] = useState(10);
  const [wAtt, setWAtt] = useState(10);
  const [nucMesi, setNucMesi] = useState(3);
  const [gen, setGen] = useState([]);
  const [inD, setInD] = useState("");
  const [inN, setInN] = useState(["", "", "", "", ""]);
  const [inErr, setInErr] = useState("");

  const draws = useMemo(() => {
    const seen = new Set(RAW.draws.map((x) => x.d));
    const extraOk = extra.filter((x) => !seen.has(x.d)); // se la stessa data arriva dal repo, vince il repo
    return [...RAW.draws, ...extraOk].sort((a, b) => a.d.localeCompare(b.d));
  }, [extra]);

  const lastDraw = draws[draws.length - 1];
  const prevDraw = draws[draws.length - 2];
  const curMonth = mk(lastDraw.d);
  const drawsMese = draws.filter((dr) => mk(dr.d) === curMonth).length;

  /* conteggio uscite nel mese corrente (si azzera da solo al cambio mese) */
  const monthCounts = useMemo(() => {
    const out = Array.from({ length: 5 }, () => ({}));
    for (const dr of draws) {
      if (mk(dr.d) === curMonth) {
        for (let p = 0; p < 5; p++) out[p][dr.n[p]] = (out[p][dr.n[p]] || 0) + 1;
      }
    }
    return out;
  }, [draws, curMonth]);

  /* occorrenze per (posizione, numero) -> lista di indici in draws */
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

  /* nucleo di targetMonth = numeri usciti in TUTTI i k mesi precedenti (se coperti dai dati) */
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

  /* attesi al giorno i (esclusa l'estrazione i): nucleo del mese di i meno gli usciti prima nel mese */
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

  /* score e rank alla vigilia dell'estrazione i (usa solo dati < i) */
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
    [draws, wRit, wAtt, nucMesi] // eslint-disable-line
  );

  /* nucleo & attesi correnti (per il mese in corso) */
  const nucleoNow = useMemo(
    () => Array.from({ length: 5 }, (_, p) => nucleoOf(p, curMonth, nucMesi)),
    [draws, nucMesi] // eslint-disable-line
  );
  const attesiNow = useMemo(
    () => Array.from({ length: 5 }, (_, p) => attesiAt(p, draws.length)),
    [draws, nucMesi] // eslint-disable-line
  );

  /* verifica prospettica: rank del numero uscito, calcolato coi soli dati precedenti */
  const verifica = useMemo(() => {
    const out = [];
    for (let i = 0; i < draws.length; i++) {
      const m = mk(draws[i].d);
      if (nucleoOf(0, m, nucMesi) === null) continue; // servono i mesi precedenti nei dati
      const rk = [];
      for (let p = 0; p < 5; p++) {
        const rows = scoresAt(p, i);
        const hit = rows.find((r) => r.n === draws[i].n[p]);
        rk.push(hit ? hit.rank : null);
      }
      out.push({ d: draws[i].d, n: draws[i].n, rk });
    }
    return out;
  }, [draws, wRit, wAtt, nucMesi]); // eslint-disable-line

  const distrib = useMemo(() => {
    const bands = [[1, 5], [6, 10], [11, 18], [19, 36]];
    return Array.from({ length: 5 }, (_, p) =>
      bands.map(([a, b]) => verifica.filter((v) => v.rk[p] >= a && v.rk[p] <= b).length)
    );
  }, [verifica]);

  /* gioca ora: greedy top-score con vincolo crescente stretto */
  const giocaOra = useMemo(() => {
    const pick = [];
    let prev = 0;
    for (let p = 0; p < 5; p++) {
      const maxAllowed = 40 - (4 - p);
      const cand = ranksNow[p].filter((r) => r.n > prev && r.n <= maxAllowed);
      if (!cand.length) return null;
      pick.push(cand[0]);
      prev = cand[0].n;
    }
    return pick;
  }, [ranksNow]);

  const generaCinquina = () => {
    for (let tent = 0; tent < 80; tent++) {
      const c = [];
      let prev = 0, okAll = true;
      for (let p = 0; p < 5; p++) {
        const maxAllowed = 40 - (4 - p);
        const cand = ranksNow[p].filter((r) => r.n > prev && r.n <= maxAllowed).slice(0, 12);
        if (!cand.length) { okAll = false; break; }
        const ws = cand.map((r) => Math.exp(r.sc / 25));
        const tot = ws.reduce((a, b) => a + b, 0);
        let x = Math.random() * tot, idx = 0;
        for (; idx < ws.length - 1 && x > ws[idx]; idx++) x -= ws[idx];
        c.push(cand[idx].n);
        prev = cand[idx].n;
      }
      if (!okAll) continue;
      if (isCrowded(c)) continue;
      const key = c.join("-");
      if (gen.some((g) => g.join("-") === key)) continue;
      if (draws.slice(-90).some((dr) => dr.n.join("-") === key)) continue;
      setGen((g) => [c, ...g].slice(0, 8));
      return;
    }
  };

  /* aggiungi estrazione */
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

  /* grafico: ultime 15 */
  const last15 = draws.slice(-15);
  const W = 740, H = 330, PADX = 26, PADT = 26, PADB = 40;
  const x = (i) => PADX + (i * (W - 2 * PADX)) / 14;
  const y = (v) => PADT + ((40 - v) * (H - PADT - PADB)) / 40;

  /* fascia/spostamento */
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
    <span
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        minWidth: 30, height: 30, borderRadius: 8, margin: 3, padding: "0 5px",
        background: dim ? "transparent" : "#1c2540",
        border: "1px solid " + (ring ? T.amber : T.edge),
        color: color || T.ink, fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
        fontSize: 14, fontWeight: 600, opacity: dim ? 0.35 : 1,
        boxShadow: ring ? "0 0 0 1px " + T.amber : "none",
      }}
    >
      {n}
      {badge > 0 && (
        <span style={{ fontSize: 9, marginLeft: 3, color: T.ok, fontWeight: 800 }}>×{badge}</span>
      )}
    </span>
  );

  const TabBtn = ({ id, label }) => (
    <button
      onClick={() => setTab(id)}
      style={{
        flex: 1, padding: "10px 2px", background: tab === id ? "#1d2745" : "transparent",
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

  /* etichette grafico: sopra il punto, sotto se un altro valore è vicino e maggiore */
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
      {/* header */}
      <div style={{ padding: "18px 16px 10px" }}>
        <div style={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: 20, fontWeight: 800, letterSpacing: 3 }}>
          VINCICASA<span style={{ color: T.amber }}> · LAB</span>
        </div>
        <div style={{ fontSize: 11.5, color: T.dim, marginTop: 2 }}>
          strategia nucleo di Jimmy · ultima estrazione {fmtD(lastDraw.d)} · storico {RAW.histN + extra.length} estrazioni
        </div>
      </div>

      {/* aggiungi estrazione */}
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
              <span style={{ fontSize: 12, color: T.dim }}>
                {extra.length} estrazioni aggiunte a mano su questo dispositivo
              </span>
              <button
                onClick={() => setExtra([])}
                style={{ background: "transparent", color: T.warn, border: "1px solid " + T.edge, borderRadius: 8, padding: "5px 10px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}
              >
                Rimuovi
              </button>
            </div>
          )}
        </Card>
      </div>

      {/* tabs */}
      <div style={{ display: "flex", position: "sticky", top: 0, background: T.bg, zIndex: 5, borderBottom: "1px solid " + T.edge, margin: "0 0 14px" }}>
        <TabBtn id="andamento" label="ANDAMENTO" />
        <TabBtn id="nucleo" label="NUCLEO" />
        <TabBtn id="rank" label="RANK" />
        <TabBtn id="gioca" label="GIOCA" />
        <TabBtn id="verifica" label="VERIFICA" />
      </div>

      <div style={{ padding: "0 16px" }}>
        {/* ============ ANDAMENTO ============ */}
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
                      <polyline
                        fill="none" stroke={POS_COLORS[p]} strokeWidth="1.6" strokeDasharray="5 4"
                        points={last15.map((dr, i) => x(i) + "," + y(dr.n[p])).join(" ")}
                      />
                      {last15.map((dr, i) => (
                        <g key={i}>
                          <circle cx={x(i)} cy={y(dr.n[p])} r="3.4" fill={POS_COLORS[p]} />
                          <text
                            x={x(i)} y={y(dr.n[p]) + labelDy(i, p)} textAnchor="middle"
                            fontSize="10.5" fontWeight="700" fill={POS_COLORS[p]}
                            fontFamily="ui-monospace, monospace"
                          >
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
                {POS_LABELS.map((l, p) => (
                  <span key={p} style={{ fontSize: 11, color: POS_COLORS[p], fontWeight: 700 }}>● {l}</span>
                ))}
              </div>
            </Card>

            <Card title="Spostamento vs estrazione precedente" sub={fmtD(prevDraw.d) + " → " + fmtD(lastDraw.d) + " · delta per posizione"}>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {Array.from({ length: 5 }, (_, p) => {
                  const dv = lastDraw.n[p] - prevDraw.n[p];
                  return (
                    <div key={p} style={{ flex: "1 1 110px", background: "#101830", border: "1px solid " + T.edge, borderRadius: 10, padding: 10 }}>
                      <div style={{ fontSize: 11, color: POS_COLORS[p], fontWeight: 800 }}>{POS_LABELS[p]}</div>
                      <div style={{ fontFamily: "ui-monospace, monospace", fontSize: 20, fontWeight: 800 }}>
                        {prevDraw.n[p]} → {lastDraw.n[p]}
                      </div>
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
                  return (
                    <div key={p} style={{ fontSize: 12.5 }}>
                      <span style={{ color: POS_COLORS[p], fontWeight: 800 }}>{POS_LABELS[p]}={lastDraw.n[p]}</span>{" "}
                      <span style={{ color: col, fontWeight: 700 }}>{lbl}</span>
                    </div>
                  );
                })}
              </div>
            </Card>
          </>
        )}

        {/* ============ NUCLEO ============ */}
        {tab === "nucleo" && (
          <>
            <Card
              title={"Nucleo (" + nucMesi + " mesi) — mese " + curMonth}
              sub={drawsMese + " estrazioni nel mese · ×n = uscite del mese (conteggio azzerato a inizio mese) · bordo ambra = atteso"}
            >
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
                    {(nucleoNow[p] || []).map((n) => (
                      <Chip key={n} n={n} color={POS_COLORS[p]} ring={attesiNow[p] && attesiNow[p].has(n)} badge={monthCounts[p][n] || 0} />
                    ))}
                    {nucleoNow[p] === null && <span style={{ fontSize: 12, color: T.dim }}>servono più mesi di dati</span>}
                  </div>
                  {(() => {
                    const fuori = Object.keys(monthCounts[p]).map(Number).filter((x) => !(nucleoNow[p] || []).includes(x)).sort((a, b) => a - b);
                    return fuori.length > 0 ? (
                      <div style={{ fontSize: 11.5, color: T.dim, marginTop: 2 }}>
                        fuori nucleo questo mese: {fuori.map((x) => x + "\u00d7" + monthCounts[p][x]).join(", ")}
                      </div>
                    ) : null;
                  })()}
                </div>
              ))}
            </Card>
            <Card title="Attesi — timing" sub="dal backtest su 105 mesi">
              <div style={{ fontSize: 13, lineHeight: 1.55, color: T.ink }}>
                Il pool degli attesi rende di più nei <b style={{ color: T.amber }}>primi 5–10 giorni del mese</b> (efficienza 0,055 → 0,044 a fine mese).
                Nell'ultima settimana i mancanti escono a 0,85–0,95x del loro ritmo: il pool ridotto contiene i deboli del mese, non gli imminenti.
              </div>
            </Card>
          </>
        )}

        {/* ============ RANK ============ */}
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

        {/* ============ GIOCA ============ */}
        {tab === "gioca" && (
          <>
            <Card title="Gioca ora" sub={"top rank per posizione, con vincolo d'ordine · pesi correnti · " + curMonth}>
              {giocaOra && (
                <>
                  <div style={{ textAlign: "center", margin: "6px 0 10px" }}>
                    {giocaOra.map((r, p) => (
                      <Chip key={p} n={r.n} color={POS_COLORS[p]} ring={r.at} />
                    ))}
                  </div>
                  <div style={{ fontSize: 12, color: T.dim, textAlign: "center" }}>
                    {isCrowded(giocaOra.map((r) => r.n)) ? "⚠ pattern affollato: " + isCrowded(giocaOra.map((r) => r.n)) : "✓ combinazione fuori dai pattern affollati"}
                    {" · bordo ambra = numero atteso"}
                  </div>
                </>
              )}
            </Card>
            <Card title="Crea cinquina" sub="campiona dai rank (top 12 per posizione), scarta pattern affollati e duplicati recenti">
              <button onClick={generaCinquina}
                style={{ background: T.amber, color: "#1a1405", border: "none", borderRadius: 10, padding: "10px 16px", fontWeight: 800, fontSize: 14, cursor: "pointer", width: "100%" }}>
                Genera
              </button>
              {gen.map((c, i) => (
                <div key={i} style={{ textAlign: "center", marginTop: 8, opacity: i === 0 ? 1 : 0.7 }}>
                  {c.map((n, p) => <Chip key={p} n={n} color={POS_COLORS[p]} />)}
                </div>
              ))}
            </Card>
          </>
        )}

        {/* ============ VERIFICA ============ */}
        {tab === "verifica" && (
          <>
            <Card title="Verifica prospettica" sub="rank che il numero uscito aveva PRIMA dell'estrazione, con i pesi correnti e i soli dati precedenti">
              <div style={{ overflowX: "auto" }}>
                <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 12.5, fontFamily: "ui-monospace, monospace" }}>
                  <thead>
                    <tr style={{ color: T.dim }}>
                      <th style={{ textAlign: "left", padding: "4px 6px" }}>data</th>
                      {POS_LABELS.map((l, p) => (
                        <th key={p} style={{ padding: "4px 6px", color: POS_COLORS[p] }}>{l}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[...verifica].reverse().map((v, i) => (
                      <tr key={i} style={{ borderTop: "1px solid #1b2340" }}>
                        <td style={{ padding: "4px 6px", color: T.dim }}>{fmtD(v.d)}</td>
                        {v.rk.map((r, p) => (
                          <td key={p} style={{ padding: "4px 6px", textAlign: "center" }}>
                            <span style={{
                              fontWeight: 800,
                              color: r <= 5 ? T.ok : r <= 10 ? T.amber : T.dim,
                            }}>
                              {v.n[p]}<span style={{ fontSize: 10, opacity: 0.8 }}> r{r}</span>
                            </span>
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
            <Card title="Distribuzione dei rank" sub="per posizione, caso per caso — quante estrazioni in ciascuna fascia">
              {Array.from({ length: 5 }, (_, p) => (
                <div key={p} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, fontSize: 12.5 }}>
                  <span style={{ width: 26, fontWeight: 800, color: POS_COLORS[p] }}>{POS_LABELS[p]}</span>
                  {["r1–5", "r6–10", "r11–18", "r19+"].map((b, bi) => (
                    <span key={bi} style={{ flex: 1, textAlign: "center", background: "#101830", borderRadius: 6, padding: "5px 0", border: "1px solid " + T.edge }}>
                      <span style={{ color: bi === 0 ? T.ok : bi === 1 ? T.amber : T.dim, fontWeight: 800, fontFamily: "ui-monospace, monospace" }}>
                        {distrib[p][bi]}
                      </span>
                      <div style={{ fontSize: 9.5, color: T.dim }}>{b}</div>
                    </span>
                  ))}
                </div>
              ))}
              <div style={{ fontSize: 11.5, color: T.dim, marginTop: 4 }}>
                Verifica disponibile dalle estrazioni con {nucMesi} mesi precedenti nei dati (da luglio 2026).
              </div>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
