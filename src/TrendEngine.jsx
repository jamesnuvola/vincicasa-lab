import { useMemo, useState } from "react";

const T = {
  bg: "#0b1020", card: "#141b2e", edge: "#26304c", ink: "#e9edf7",
  dim: "#8f97b0", amber: "#f5b942", ok: "#49d18a", warn: "#ff6b6b",
};
const VALID = 40;
const WINDOWS = [7, 14, 21, 30];
const HORIZONS = [1, 3, 5, 7, 10, 14, 21, 30];
const TREND_THRESHOLD = 0.58;

const clamp = (x, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, x));
const mean = (a) => a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0;
const fmtDate = (d) => d ? d.split("-").reverse().join("/") : "—";

function freqWindow(draws, end, w) {
  const out = Array(VALID + 1).fill(0);
  const from = Math.max(0, end - w);
  for (let i = from; i < end; i++) for (const n of draws[i].n) out[n]++;
  return out;
}

function scoreFromFreq(f7, f21) {
  const r7 = f7 / 7;
  const r21 = f21 / 21;
  const accel = r7 - r21;
  const recent = clamp(0.5 + accel * 2.5);
  const level = clamp(r21 * 8);
  return 0.55 * recent + 0.45 * level;
}

function scoreAt(draws, end, n) {
  if (end < 21) return 0;
  return scoreFromFreq(
    freqWindow(draws, end, 7)[n],
    freqWindow(draws, end, 21)[n]
  );
}

function rankAt(draws, end, k = 12) {
  return Array.from({ length: VALID }, (_, i) => i + 1)
    .map(n => ({ n, score: scoreAt(draws, end, n) }))
    .sort((a, b) => b.score - a.score || a.n - b.n)
    .slice(0, k);
}

function pairFreq(draws, end, w) {
  const out = new Map();
  const from = Math.max(0, end - w);
  for (let i = from; i < end; i++) {
    const a = [...draws[i].n].sort((x, y) => x - y);
    for (let x = 0; x < a.length; x++) {
      for (let y = x + 1; y < a.length; y++) {
        const k = a[x] + "-" + a[y];
        out.set(k, (out.get(k) || 0) + 1);
      }
    }
  }
  return out;
}

function regime(draws, end, w = 21) {
  const ds = draws.slice(Math.max(0, end - w), end);
  if (!ds.length) return null;
  const sums = ds.map(d => d.n.reduce((a, b) => a + b, 0));
  const odds = ds.map(d => d.n.filter(n => n % 2).length);
  const highs = ds.map(d => d.n.filter(n => n >= 21).length);
  const repeats = ds.slice(1).map((d, j) =>
    d.n.filter(n => ds[j].n.includes(n)).length
  );
  return {
    sum: mean(sums), odd: mean(odds), high: mean(highs), repeat: mean(repeats)
  };
}

function trendState(score) {
  if (score >= 0.72) return ["HOT", T.ok];
  if (score >= TREND_THRESHOLD) return ["CALDO", T.amber];
  if (score <= 0.28) return ["FREDDO", T.warn];
  return ["NEUTRO", T.dim];
}

const cardStyle = {
  background: T.card,
  border: "1px solid " + T.edge,
  borderRadius: 14,
  padding: 14,
  marginBottom: 14
};

function pct(x, digits = 1) {
  return (x * 100).toFixed(digits) + "%";
}

export default function TrendEngine({ draws }) {
  const end = draws.length;
  const [ledgerK, setLedgerK] = useState(12);

  const analysis = useMemo(() => {
    const f = {};
    for (const w of WINDOWS) f[w] = freqWindow(draws, end, w);

    const rows = Array.from({ length: VALID }, (_, i) => {
      const n = i + 1;
      const r7 = f[7][n] / Math.min(7, end);
      const r14 = f[14][n] / Math.min(14, end);
      const r21 = f[21][n] / Math.min(21, end);
      const r30 = f[30][n] / Math.min(30, end);
      const accel = r7 - r21;
      const persistence =
        (r7 > 0 ? 1 : 0) + (r14 > 0 ? 1 : 0) + (r21 > 0 ? 1 : 0);
      const recent = clamp(0.5 + accel * 2.5);
      const level = clamp(r21 * 8);
      const persist = persistence / 3;
      const score = 0.45 * recent + 0.35 * level + 0.20 * persist;
      return {
        n, f7: f[7][n], f14: f[14][n], f21: f[21][n], f30: f[30][n],
        r7, r14, r21, r30, accel, persistence, score
      };
    }).sort((a, b) => b.score - a.score || a.n - b.n);

    const pairs7 = pairFreq(draws, end, 7);
    const pairs14 = pairFreq(draws, end, 14);
    const pairRows = [...new Set([...pairs7.keys(), ...pairs14.keys()])]
      .map(k => ({
        k,
        f7: pairs7.get(k) || 0,
        f14: pairs14.get(k) || 0,
        accel: (pairs7.get(k) || 0) / 7 - (pairs14.get(k) || 0) / 14
      }))
      .sort((a, b) => (b.f7 * 2 + b.f14) - (a.f7 * 2 + a.f14));

    const current = regime(draws, end, 21);
    const previous = regime(draws, Math.max(0, end - 7), 21);
    const regDelta = current && previous ? {
      sum: current.sum - previous.sum,
      odd: current.odd - previous.odd,
      high: current.high - previous.high,
      repeat: current.repeat - previous.repeat
    } : null;

    return { rows, pairRows, current, previous, regDelta };
  }, [draws, end]);

  // Trend 2.0: ricostruzione leakage-free del ciclo di vita di ogni numero.
  const lifecycle = useMemo(() => {
    const events = [];
    const current = [];

    for (let n = 1; n <= VALID; n++) {
      let active = false;
      let start = -1;
      let peak = -Infinity;
      let peakIndex = -1;
      let hits = 0;
      let consecutive = 0;
      let maxConsecutive = 0;

      for (let i = 21; i <= draws.length; i++) {
        const s = scoreAt(draws, i, n);
        const isOn = s >= TREND_THRESHOLD;

        if (isOn && !active) {
          active = true;
          start = i;
          peak = s;
          peakIndex = i;
          hits = 0;
          consecutive = 0;
          maxConsecutive = 0;
        }

        if (active) {
          if (s > peak) { peak = s; peakIndex = i; }

          // L'estrazione i è il risultato successivo alla previsione fatta
          // usando il prefisso [0, i). A i=draws.length non esiste un target.
          if (i < draws.length && draws[i].n.includes(n)) {
            hits++;
            consecutive++;
          } else {
            consecutive = 0;
          }
          maxConsecutive = Math.max(maxConsecutive, consecutive);
        }

        if (!isOn && active) {
          events.push({
            n, start, end: i - 1, len: i - start,
            peak, peakIndex, hits, maxConsecutive
          });
          active = false;
          start = -1;
        }
      }

      if (active) {
        events.push({
          n, start, end: draws.length, len: draws.length - start,
          peak, peakIndex, hits, maxConsecutive
        });
      }

      const latest =
        [...events].reverse().find(e => e.n === n && e.end === draws.length)
        || [...events].reverse().find(e => e.n === n && e.end >= draws.length - 1);

      let realStreak = 0;
      for (let i = draws.length - 1; i >= 0 && draws[i].n.includes(n); i--) realStreak++;

      const gaps = [];
      let prev = -1;
      for (let i = 0; i < draws.length; i++) {
        if (draws[i].n.includes(n)) {
          if (prev >= 0) gaps.push(i - prev);
          prev = i;
        }
      }

      current.push({
        n,
        active: !!latest,
        age: latest ? Math.max(1, draws.length - latest.start) : 0,
        start: latest ? latest.start : -1,
        peak: latest ? latest.peak : 0,
        peakAge: latest ? Math.max(0, draws.length - latest.peakIndex) : null,
        hits: latest ? latest.hits : 0,
        maxConsecutive: latest ? latest.maxConsecutive : 0,
        realStreak,
        avgGap: mean(gaps),
        lastGap: gaps.length ? gaps[gaps.length - 1] : null,
        score: scoreAt(draws, draws.length, n)
      });
    }

    return {
      events,
      current: current.sort((a, b) => b.score - a.score || a.n - b.n)
    };
  }, [draws]);

  const durationSummary = useMemo(() => {
    const ev = lifecycle.events;
    const lens = ev.map(x => x.len).sort((a, b) => a - b);
    const countLE = (x) => ev.length ? ev.filter(e => e.len <= x).length / ev.length : 0;
    const crossMonth = ev.filter(e => {
      const a = draws[e.start]?.d;
      const b = draws[Math.min(e.end, draws.length - 1)]?.d;
      return a && b && a.slice(0, 7) !== b.slice(0, 7);
    }).length;

    return {
      count: ev.length,
      avg: mean(lens),
      median: lens.length ? lens[Math.floor(lens.length / 2)] : 0,
      max: lens.length ? lens[lens.length - 1] : 0,
      le7: countLE(7), le10: countLE(10), le14: countLE(14), le21: countLE(21),
      crossMonth
    };
  }, [lifecycle, draws]);

  // Walk-forward: ogni previsione vede solo il prefisso precedente.
  const wfSummary = useMemo(() => {
    return HORIZONS.map(h => {
      const perCase = [];

      for (let i = 21; i + h <= draws.length; i++) {
        const top = rankAt(draws, i, 5).map(x => x.n);
        let totalHits = 0;

        for (let j = i; j < i + h; j++) {
          totalHits += top.filter(n => draws[j].n.includes(n)).length;
        }

        perCase.push(totalHits / h);
      }

      return {
        h,
        cases: perCase.length,
        avg: mean(perCase),
        delta: mean(perCase) - 0.625,
        ge1: perCase.filter(x => x > 0).length / perCase.length
      };
    });
  }, [draws]);

  // Registro sperimentale: la previsione viene costruita prima del target.
  const ledger = useMemo(() => {
    const rows = [];

    for (let i = 21; i < draws.length; i++) {
      const top = rankAt(draws, i, 12).map(x => x.n);
      const target = new Set(draws[i].n);

      rows.push({
        i,
        d: draws[i].d,
        n: draws[i].n,
        h5: top.slice(0, 5).filter(n => target.has(n)).length,
        h8: top.slice(0, 8).filter(n => target.has(n)).length,
        h12: top.slice(0, 12).filter(n => target.has(n)).length,
        top
      });
    }

    return rows;
  }, [draws]);

  const currentTop = analysis.rows.slice(0, 5).map(x => x.n);
  const currentTop8 = analysis.rows.slice(0, 8).map(x => x.n);
  const latestLedger = ledger[ledger.length - 1];
  const selectedLedger = ledger.slice(-12).reverse();

  const Chip = ({ n, small = false }) => (
    <span style={{
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      minWidth: small ? 30 : 38, height: small ? 30 : 38, borderRadius: 9,
      margin: 3, background: "#1c2540", border: "1px solid " + T.amber,
      color: T.ink, fontFamily: "ui-monospace, monospace",
      fontSize: small ? 13 : 16, fontWeight: 800
    }}>{n}</span>
  );

  const Bar = ({ v, color }) => (
    <div style={{ height: 7, background: "#0f1526", borderRadius: 4, overflow: "hidden" }}>
      <div style={{ width: (clamp(v) * 100) + "%", height: "100%", background: color }} />
    </div>
  );

  return (
    <div>
      <div style={cardStyle}>
        <div style={{ fontSize: 13, fontWeight: 800, letterSpacing: 1.2 }}>TREND ENGINE 2.0</div>
        <div style={{ fontSize: 11.5, color: T.dim, marginTop: 3 }}>
          7/14/21/30 · accelerazione · persistenza · ciclo di vita · walk-forward · registro
        </div>

        <div style={{ marginTop: 12, textAlign: "center" }}>
          {currentTop.map(n => <Chip key={n} n={n} />)}
        </div>

        <div style={{ fontSize: 11, color: T.dim, textAlign: "center", marginTop: 5 }}>
          top 5 reale del ranking trend — ora non viene più alterato dall'ordinamento numerico
        </div>

        <div style={{ marginTop: 10, display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "center" }}>
          <span style={{ color: T.ok, fontSize: 11 }}>TOP 5: {currentTop.join(" · ")}</span>
          <span style={{ color: T.dim, fontSize: 11 }}>| TOP 8: {currentTop8.join(" · ")}</span>
        </div>
      </div>

      <div style={cardStyle}>
        <div style={{ fontSize: 13, fontWeight: 800 }}>NUMERI IN MOVIMENTO</div>
        <div style={{ fontSize: 11.5, color: T.dim, marginBottom: 10 }}>
          Score descrittivo: accelerazione recente + livello + persistenza.
        </div>

        {analysis.rows.slice(0, 12).map((r, i) => {
          const [label, color] = trendState(r.score);

          return (
            <div key={r.n} style={{
              display: "grid", gridTemplateColumns: "28px 38px 1fr 58px",
              gap: 7, alignItems: "center", marginBottom: 7
            }}>
              <span style={{ color: T.dim, fontSize: 11 }}>{i + 1}</span>
              <b style={{ color: i < 5 ? T.ok : T.ink }}>{r.n}</b>
              <Bar v={r.score} color={color} />
              <span style={{ color, fontSize: 10.5, fontWeight: 800 }}>{label}</span>
            </div>
          );
        })}
      </div>

      <div style={cardStyle}>
        <div style={{ fontSize: 13, fontWeight: 800 }}>TREND 2.0 · CICLO DI VITA</div>
        <div style={{ fontSize: 11.5, color: T.dim, margin: "4px 0 10px" }}>
          Nascita → accelerazione → consolidamento → esaurimento. La presenza reale può essere consecutiva oppure intermittente.
        </div>

        {lifecycle.current.slice(0, 10).map(r => {
          const [label, color] = trendState(r.score);

          return (
            <div key={r.n} style={{ borderTop: "1px solid #1b2340", padding: "8px 0" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <b>{r.n}</b>
                <span style={{ color, fontSize: 10.5, fontWeight: 800 }}>
                  {label} · score {r.score.toFixed(3)}
                </span>
              </div>

              <div style={{ fontSize: 11, color: T.dim, marginTop: 3 }}>
                {r.active ? (
                  <>
                    attivo da {fmtDate(draws[r.start]?.d)} · età {r.age} estr. ·
                    picco -{r.peakAge} · hit nell'episodio {r.hits} ·
                    consecutivi max {r.maxConsecutive}
                  </>
                ) : (
                  <>nessun episodio attivo nell'ultima fase · gap medio {r.avgGap ? r.avgGap.toFixed(1) : "—"} estr.</>
                )}
              </div>

              <div style={{ fontSize: 10.5, color: T.dim, marginTop: 2 }}>
                gap reale medio {r.avgGap ? r.avgGap.toFixed(1) : "—"} ·
                ultimo gap {r.lastGap ?? "—"} · streak reale attuale {r.realStreak}
              </div>
            </div>
          );
        })}
      </div>

      <div style={cardStyle}>
        <div style={{ fontSize: 13, fontWeight: 800 }}>DURATA DEI TREND</div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 9 }}>
          {[
            ["episodi", durationSummary.count],
            ["media", durationSummary.avg.toFixed(1) + " estr."],
            ["mediana", durationSummary.median + " estr."],
            ["max", durationSummary.max + " estr."],
            ["≤7", pct(durationSummary.le7)],
            ["≤10", pct(durationSummary.le10)],
            ["≤14", pct(durationSummary.le14)],
            ["≤21", pct(durationSummary.le21)],
            ["attraversano mese", durationSummary.count ? pct(durationSummary.crossMonth / durationSummary.count) : "—"]
          ].map(([k, v]) => (
            <div key={k} style={{ background: "#101830", padding: 9, borderRadius: 9 }}>
              <div style={{ fontSize: 10.5, color: T.dim }}>{k}</div>
              <b>{v}</b>
            </div>
          ))}
        </div>

        <div style={{ fontSize: 10.5, color: T.dim, marginTop: 9 }}>
          Nota: la durata dipende dalla soglia 0,58 e dalla definizione del nostro score; non va letta come una durata "naturale" del fenomeno.
        </div>
      </div>

      <div style={cardStyle}>
        <div style={{ fontSize: 13, fontWeight: 800 }}>COPPIE IN TREND</div>
        <div style={{ fontSize: 11.5, color: T.dim, marginBottom: 8 }}>
          Co-movimento recente; descrittivo, non causale.
        </div>

        {analysis.pairRows.slice(0, 10).map((r, i) => (
          <div key={r.k} style={{
            display: "flex", justifyContent: "space-between",
            padding: "5px 0", borderTop: "1px solid #1b2340", fontSize: 12
          }}>
            <span><b>{i + 1}.</b> {r.k}</span>
            <span style={{ color: r.accel >= 0 ? T.ok : T.warn }}>
              7g {r.f7} · 14g {r.f14}
            </span>
          </div>
        ))}
      </div>

      <div style={cardStyle}>
        <div style={{ fontSize: 13, fontWeight: 800 }}>REGIME RECENTE</div>

        {analysis.current && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 8, marginTop: 8 }}>
            {[
              ["Somma media", analysis.current.sum, analysis.regDelta?.sum],
              ["Dispari medi", analysis.current.odd, analysis.regDelta?.odd],
              ["≥21 medi", analysis.current.high, analysis.regDelta?.high],
              ["Ripetizioni", analysis.current.repeat, analysis.regDelta?.repeat]
            ].map(([label, value, delta]) => (
              <div key={label} style={{
                background: "#101830", border: "1px solid " + T.edge,
                borderRadius: 9, padding: 9
              }}>
                <div style={{ fontSize: 10.5, color: T.dim }}>{label}</div>
                <b>{value.toFixed(2)}</b>
                {delta !== undefined && (
                  <span style={{
                    fontSize: 10, color: delta >= 0 ? T.ok : T.warn, marginLeft: 6
                  }}>
                    {delta >= 0 ? "+" : ""}{delta.toFixed(2)}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={cardStyle}>
        <div style={{ fontSize: 13, fontWeight: 800 }}>VALIDAZIONE WALK-FORWARD · ORIZZONTI</div>
        <div style={{ fontSize: 11.5, color: T.dim, margin: "4px 0 10px" }}>
          Il TOP 5 viene fissato alla data di previsione e poi testato per h estrazioni successive. Nessun dato futuro entra nello score.
        </div>

        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11.5 }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left", padding: 5 }}>orizzonte</th>
              <th>casi</th><th>hit/estr.</th><th>Δ vs 0,625</th><th>≥1 hit</th>
            </tr>
          </thead>
          <tbody>
            {wfSummary.map(x => (
              <tr key={x.h} style={{ borderTop: "1px solid #1b2340" }}>
                <td style={{ padding: 5 }}>{x.h} estr.</td>
                <td style={{ textAlign: "center" }}>{x.cases}</td>
                <td style={{ textAlign: "center" }}>{x.avg.toFixed(3)}</td>
                <td style={{ textAlign: "center", color: x.delta >= 0 ? T.ok : T.warn }}>
                  {x.delta >= 0 ? "+" : ""}{x.delta.toFixed(3)}
                </td>
                <td style={{ textAlign: "center" }}>{pct(x.ge1)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div style={{ fontSize: 10.5, color: T.dim, marginTop: 8 }}>
          Baseline teorico: 0,625 hit per estrazione per un insieme casuale di 5 numeri. Gli orizzonti sono sovrapposti: il test è descrittivo e non costituisce una prova di indipendenza.
        </div>
      </div>

      <div style={cardStyle}>
        <div style={{ fontSize: 13, fontWeight: 800 }}>REGISTRO SPERIMENTALE · OUT-OF-SAMPLE</div>
        <div style={{ fontSize: 11.5, color: T.dim, margin: "4px 0 10px" }}>
          Ogni riga è una previsione costruita prima dell'estrazione target. Serve per non confondere il risultato osservato con una regola costruita dopo.
        </div>

        <div style={{ display: "flex", gap: 6, marginBottom: 9 }}>
          {[5, 8, 12].map(k => (
            <button key={k} onClick={() => setLedgerK(k)} style={{
              background: ledgerK === k ? "#1e6b42" : "#101830",
              color: T.ink, border: "1px solid " + T.edge,
              borderRadius: 8, padding: "6px 9px", fontSize: 11, fontWeight: 800
            }}>
              TOP {k}
            </button>
          ))}
        </div>

        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", padding: 5 }}>target</th>
                <th>hit</th>
                <th>numeri estratti</th>
                <th>previsione</th>
              </tr>
            </thead>

            <tbody>
              {selectedLedger.map(r => {
                const hit = ledgerK === 5 ? r.h5 : ledgerK === 8 ? r.h8 : r.h12;

                return (
                  <tr key={r.i} style={{ borderTop: "1px solid #1b2340" }}>
                    <td style={{ padding: 5, whiteSpace: "nowrap" }}>{fmtDate(r.d)}</td>
                    <td style={{
                      textAlign: "center", fontWeight: 800,
                      color: hit >= 2 ? T.ok : T.ink
                    }}>
                      {hit}/5
                    </td>
                    <td style={{
                      textAlign: "center", fontFamily: "ui-monospace, monospace"
                    }}>
                      {r.n.join(" · ")}
                    </td>
                    <td style={{
                      padding: 5, fontFamily: "ui-monospace, monospace"
                    }}>
                      {r.top.slice(0, ledgerK).join(" · ")}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {latestLedger && (
          <div style={{ marginTop: 10, padding: 10, background: "#101830", borderRadius: 9 }}>
            <div style={{ fontSize: 10.5, color: T.dim }}>ULTIMA VERIFICA OOS</div>
            <b>
              {fmtDate(latestLedger.d)} · TOP 5 {latestLedger.h5}/5 ·
              TOP 8 {latestLedger.h8}/5 · TOP 12 {latestLedger.h12}/5
            </b>
            <div style={{ fontSize: 10.5, color: T.dim, marginTop: 3 }}>
              Previsione: {latestLedger.top.slice(0, 12).join(" · ")} ·
              target: {latestLedger.n.join(" · ")}
            </div>
          </div>
        )}
      </div>

      <div style={cardStyle}>
        <div style={{ fontSize: 13, fontWeight: 800 }}>DETTAGLIO DELLE PRIME 8</div>

        {analysis.rows.slice(0, 8).map(r => (
          <div key={r.n} style={{ borderTop: "1px solid #1b2340", padding: "8px 0" }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <b>{r.n}</b>
              <span style={{
                color: r.accel >= 0 ? T.ok : T.warn,
                fontSize: 11
              }}>
                accelerazione {(r.accel * 100).toFixed(1)} pp
              </span>
            </div>

            <div style={{ fontSize: 11, color: T.dim, marginTop: 3 }}>
              7g {r.f7} · 14g {r.f14} · 21g {r.f21} ·
              30g {r.f30} · persistenza {r.persistence}/3
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
