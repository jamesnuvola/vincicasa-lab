import { useMemo } from "react";

const T = {
  bg: "#0b1020", card: "#141b2e", edge: "#26304c", ink: "#e9edf7",
  dim: "#8f97b0", amber: "#f5b942", ok: "#49d18a", warn: "#ff6b6b",
};
const VALID = 40;
const WINDOWS = [7, 14, 21, 30];

const clamp = (x, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, x));
const mean = (a) => a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0;

function freqWindow(draws, end, w) {
  const out = Array(VALID + 1).fill(0);
  const from = Math.max(0, end - w);
  for (let i = from; i < end; i++) for (const n of draws[i].n) out[n]++;
  return out;
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
    sum: mean(sums),
    odd: mean(odds),
    high: mean(highs),
    repeat: mean(repeats),
  };
}

function trendState(score) {
  if (score >= 0.72) return ["HOT", T.ok];
  if (score >= 0.58) return ["CALDO", T.amber];
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

export default function TrendEngine({ draws }) {
  const end = draws.length;

  const analysis = useMemo(() => {
    const f = {};
    for (const w of WINDOWS) f[w] = freqWindow(draws, end, w);

    const rows = Array.from({ length: VALID }, (_, i) => {
      const n = i + 1;

      const r7 = f[7][n] / Math.min(7, end);
      const r14 = f[14][n] / Math.min(14, end);
      const r21 = f[21][n] / Math.min(21, end);
      const r30 = f[30][n] / Math.min(30, end);

      // Accelerazione: differenza tra velocità recente e media delle ultime 3 settimane.
      const accel = r7 - r21;

      // Persistenza: presenza in tutte le finestre.
      const persistence =
        (r7 > 0 ? 1 : 0) +
        (r14 > 0 ? 1 : 0) +
        (r21 > 0 ? 1 : 0);

      const recent = clamp(0.5 + accel * 2.5);
      const level = clamp(r21 * 8);
      const persist = persistence / 3;

      const score =
        0.45 * recent +
        0.35 * level +
        0.20 * persist;

      return {
        n,
        f7: f[7][n],
        f14: f[14][n],
        f21: f[21][n],
        f30: f[30][n],
        r7,
        r14,
        r21,
        r30,
        accel,
        persistence,
        score
      };
    }).sort((a, b) => b.score - a.score);

    const pairs7 = pairFreq(draws, end, 7);
    const pairs14 = pairFreq(draws, end, 14);

    const pairRows = [
      ...new Set([...pairs7.keys(), ...pairs14.keys()])
    ].map(k => ({
      k,
      f7: pairs7.get(k) || 0,
      f14: pairs14.get(k) || 0,
      accel:
        (pairs7.get(k) || 0) / 7 -
        (pairs14.get(k) || 0) / 14
    })).sort(
      (a, b) => (b.f7 * 2 + b.f14) - (a.f7 * 2 + a.f14)
    );

    const current = regime(draws, end, 21);
    const previous = regime(draws, Math.max(0, end - 7), 21);

    const regDelta = current && previous ? {
      sum: current.sum - previous.sum,
      odd: current.odd - previous.odd,
      high: current.high - previous.high,
      repeat: current.repeat - previous.repeat
    } : null;

    return {
      rows,
      pairRows,
      current,
      previous,
      regDelta
    };
  }, [draws, end]);

  /*
   * WALK-FORWARD:
   * ad ogni data i usiamo esclusivamente le estrazioni precedenti.
   * Selezioniamo i 5 numeri più frequenti e controlliamo quanti
   * vengono centrati nell'estrazione successiva.
   */
  const wfSummary = useMemo(() => {
    const result = [];

    for (const w of [7, 14, 21]) {
      const hits = [];

      for (let i = Math.max(30, w); i < draws.length; i++) {
        const f = freqWindow(draws, i, w);

        const top = Array.from({ length: VALID }, (_, j) => j + 1)
          .sort((a, b) => f[b] - f[a] || a - b)
          .slice(0, 5);

        hits.push(
          top.filter(n => draws[i].n.includes(n)).length
        );
      }

      result.push({
        w,
        n: hits.length,
        avg: mean(hits),
        one: hits.filter(x => x >= 1).length / hits.length,
        three: hits.filter(x => x >= 3).length / hits.length
      });
    }

    return result;
  }, [draws]);

  /*
   * DURATA DEI TREND:
   * definiamo un episodio come una sequenza consecutiva in cui
   * il nostro Trend Score resta >= 0.58.
   *
   * È una misura descrittiva: NON significa che il trend sia
   * statisticamente predittivo.
   */
  const duration = useMemo(() => {
    const threshold = 0.58;
    const events = [];

    for (let n = 1; n <= VALID; n++) {
      let run = 0;
      let start = null;

      for (let i = 21; i <= draws.length; i++) {
        const f7 = freqWindow(draws, i, 7)[n] / 7;
        const f21 = freqWindow(draws, i, 21)[n] / 21;

        const recent = clamp(0.5 + (f7 - f21) * 2.5);
        const level = clamp(f21 * 8);

        const score =
          recent * 0.55 +
          level * 0.45;

        const hot = score >= threshold;

        if (hot && run === 0) start = i;
        if (hot) {
          run++;
        } else if (run > 0) {
          events.push({
            n,
            start,
            end: i - 1,
            len: run
          });
          run = 0;
        }
      }

      if (run > 0) {
        events.push({
          n,
          start,
          end: draws.length,
          len: run
        });
      }
    }

    const valid = events.filter(e => e.len > 0);
    const sorted = [...valid].sort((a, b) => a.len - b.len);

    return {
      events: valid,
      avg: mean(valid.map(e => e.len)),
      median: sorted.length
        ? sorted[Math.floor(sorted.length / 2)].len
        : 0,
      max: valid.length
        ? Math.max(...valid.map(e => e.len))
        : 0
    };
  }, [draws]);

  /*
   * Cinquina descrittiva del trend:
   * prendiamo i 12 migliori score e scegliamo i 5 numeri più forti.
   *
   * ATTENZIONE: questa NON è ancora la cinquina finale del Decision Engine.
   */
  const trendTicket = useMemo(() => {
    return analysis.rows
      .slice(0, 12)
      .sort((a, b) => a.n - b.n)
      .slice(0, 5)
      .map(x => x.n);
  }, [analysis.rows]);

  const Chip = ({ n }) => (
    <span style={{
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      minWidth: 38,
      height: 38,
      borderRadius: 9,
      margin: 3,
      background: "#1c2540",
      border: "1px solid " + T.amber,
      color: T.ink,
      fontFamily: "ui-monospace, monospace",
      fontSize: 16,
      fontWeight: 800
    }}>
      {n}
    </span>
  );

  const Bar = ({ v, color }) => (
    <div style={{
      height: 7,
      background: "#0f1526",
      borderRadius: 4,
      overflow: "hidden"
    }}>
      <div style={{
        width: (clamp(v) * 100) + "%",
        height: "100%",
        background: color
      }} />
    </div>
  );

  return (
    <div>
      <div style={cardStyle}>
        <div style={{
          fontSize: 13,
          fontWeight: 800,
          letterSpacing: 1.2
        }}>
          TREND ENGINE
        </div>

        <div style={{
          fontSize: 11.5,
          color: T.dim,
          marginTop: 3
        }}>
          Finestre 7/14/21/30 · momentum · persistenza · coppie ·
          regime · walk-forward
        </div>

        <div style={{
          marginTop: 12,
          textAlign: "center"
        }}>
          {trendTicket.map(n => (
            <Chip key={n} n={n} />
          ))}
        </div>

        <div style={{
          fontSize: 11,
          color: T.dim,
          textAlign: "center",
          marginTop: 5
        }}>
          cinquina descrittiva del trend corrente — non un vantaggio dimostrato
        </div>
      </div>

      <div style={cardStyle}>
        <div style={{
          fontSize: 13,
          fontWeight: 800
        }}>
          NUMERI IN MOVIMENTO
        </div>

        <div style={{
          fontSize: 11.5,
          color: T.dim,
          marginBottom: 10
        }}>
          Il punteggio premia accelerazione recente, livello e persistenza.
        </div>

        {analysis.rows.slice(0, 12).map((r, i) => {
          const [label, color] = trendState(r.score);

          return (
            <div
              key={r.n}
              style={{
                display: "grid",
                gridTemplateColumns: "28px 38px 1fr 58px",
                gap: 7,
                alignItems: "center",
                marginBottom: 7
              }}
            >
              <span style={{
                color: T.dim,
                fontSize: 11
              }}>
                {i + 1}
              </span>

              <b style={{
                color: i < 5 ? T.ok : T.ink
              }}>
                {r.n}
              </b>

              <Bar v={r.score} color={color} />

              <span style={{
                color,
                fontSize: 10.5,
                fontWeight: 800
              }}>
                {label}
              </span>
            </div>
          );
        })}
      </div>

      <div style={cardStyle}>
        <div style={{
          fontSize: 13,
          fontWeight: 800
        }}>
          DETTAGLIO DELLE PRIME 8
        </div>

        {analysis.rows.slice(0, 8).map(r => (
          <div
            key={r.n}
            style={{
              borderTop: "1px solid #1b2340",
              padding: "8px 0"
            }}
          >
            <div style={{
              display: "flex",
              justifyContent: "space-between"
            }}>
              <b>{r.n}</b>

              <span style={{
                color: r.accel >= 0 ? T.ok : T.warn,
                fontSize: 11
              }}>
                accelerazione {(r.accel * 100).toFixed(1)} pp
              </span>
            </div>

            <div style={{
              fontSize: 11,
              color: T.dim,
              marginTop: 3
            }}>
              7g {r.f7} · 14g {r.f14} · 21g {r.f21} ·
              30g {r.f30} · persistenza {r.persistence}/3
            </div>
          </div>
        ))}
      </div>

      <div style={cardStyle}>
        <div style={{
          fontSize: 13,
          fontWeight: 800
        }}>
          COPPIE IN TREND
        </div>

        <div style={{
          fontSize: 11.5,
          color: T.dim,
          marginBottom: 8
        }}>
          Frequenza recente; utile per descrivere co-movimenti,
          non prova di causalità.
        </div>

        {analysis.pairRows.slice(0, 10).map((r, i) => (
          <div
            key={r.k}
            style={{
              display: "flex",
              justifyContent: "space-between",
              padding: "5px 0",
              borderTop: "1px solid #1b2340",
              fontSize: 12
            }}
          >
            <span>
              <b>{i + 1}.</b> {r.k}
            </span>

            <span style={{
              color: r.accel >= 0 ? T.ok : T.warn
            }}>
              7g {r.f7} · 14g {r.f14}
            </span>
          </div>
        ))}
      </div>

      <div style={cardStyle}>
        <div style={{
          fontSize: 13,
          fontWeight: 800
        }}>
          REGIME RECENTE
        </div>

        {analysis.current && (
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(2,1fr)",
            gap: 8,
            marginTop: 8
          }}>
            {[
              ["Somma media", analysis.current.sum, analysis.regDelta?.sum],
              ["Dispari medi", analysis.current.odd, analysis.regDelta?.odd],
              ["≥21 medi", analysis.current.high, analysis.regDelta?.high],
              ["Ripetizioni", analysis.current.repeat, analysis.regDelta?.repeat]
            ].map(([label, value, delta]) => (
              <div
                key={label}
                style={{
                  background: "#101830",
                  border: "1px solid " + T.edge,
                  borderRadius: 9,
                  padding: 9
                }}
              >
                <div style={{
                  fontSize: 10.5,
                  color: T.dim
                }}>
                  {label}
                </div>

                <b>{value.toFixed(2)}</b>

                {delta !== undefined && (
                  <span style={{
                    fontSize: 10,
                    color: delta >= 0 ? T.ok : T.warn,
                    marginLeft: 6
                  }}>
                    {delta >= 0 ? "+" : ""}
                    {delta.toFixed(2)}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={cardStyle}>
        <div style={{
          fontSize: 13,
          fontWeight: 800
        }}>
          QUANTO DURA UN TREND?
        </div>

        <div style={{
          fontSize: 11.5,
          color: T.dim,
          margin: "4px 0 10px"
        }}>
          Episodi storici classificati come trend dal nostro stesso
          punteggio, ricostruiti solo con dati disponibili in quel momento.
        </div>

        <div style={{
          display: "flex",
          gap: 8,
          flexWrap: "wrap"
        }}>
          <div style={{
            background: "#101830",
            padding: 9,
            borderRadius: 9
          }}>
            episodi <b>{duration.events.length}</b>
          </div>

          <div style={{
            background: "#101830",
            padding: 9,
            borderRadius: 9
          }}>
            durata media <b>{duration.avg.toFixed(1)}</b> estr.
          </div>

          <div style={{
            background: "#101830",
            padding: 9,
            borderRadius: 9
          }}>
            mediana <b>{duration.median}</b>
          </div>

          <div style={{
            background: "#101830",
            padding: 9,
            borderRadius: 9
          }}>
            max <b>{duration.max}</b>
          </div>
        </div>
      </div>

      <div style={cardStyle}>
        <div style={{
          fontSize: 13,
          fontWeight: 800
        }}>
          TEST WALK-FORWARD · “TOP 5 CALDI”
        </div>

        <div style={{
          fontSize: 11.5,
          color: T.dim,
          margin: "4px 0 10px"
        }}>
          Ad ogni estrazione scegliamo i 5 più frequenti nella
          finestra precedente e verifichiamo subito dopo.
        </div>

        <table style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: 12
        }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left", padding: 5 }}>finestra</th>
              <th>casi</th>
              <th>hit medie</th>
              <th>≥1 hit</th>
              <th>≥3 hit</th>
            </tr>
          </thead>

          <tbody>
            {wfSummary.map(x => (
              <tr
                key={x.w}
                style={{
                  borderTop: "1px solid #1b2340"
                }}
              >
                <td style={{ padding: 5 }}>
                  {x.w} estr.
                </td>

                <td style={{ textAlign: "center" }}>
                  {x.n}
                </td>

                <td style={{ textAlign: "center" }}>
                  {x.avg.toFixed(3)}
                </td>

                <td style={{ textAlign: "center" }}>
                  {(x.one * 100).toFixed(1)}%
                </td>

                <td style={{ textAlign: "center" }}>
                  {(x.three * 100).toFixed(1)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div style={{
          fontSize: 11,
          color: T.dim,
          marginTop: 8
        }}>
          Baseline teorico: 0,625 hit per una cinquina casuale.
          Il test serve a capire se il “caldo” sopravvive fuori campione.
        </div>
      </div>
    </div>
  );
}
