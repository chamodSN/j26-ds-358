import { useEffect, useState } from "react";
import "./App.css";

const api = (p, o) =>
  fetch(`/api${p}`, o).then(async r => {
    if (!r.ok) throw new Error((await r.text()).slice(0, 300));
    return r.json();
  });

export default function App() {
  const [text, setText] = useState("");
  const [useLlm, setUseLlm] = useState(false);
  const [out, setOut] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState(null);

  useEffect(() => {
    api("/demo").then(d => setText(JSON.stringify(d.listings, null, 2))).catch(e => setErr(e.message));
    api("/health").then(setInfo).catch(() => {});
  }, []);

  const run = async () => {
    setBusy(true); setErr("");
    try {
      const listings = JSON.parse(text);
      setOut(await api("/resolve", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ listings, use_llm: useLlm }),
      }));
    } catch (e) { setErr(String(e.message || e)); } finally { setBusy(false); }
  };

  return (
    <div className="page">
      <header>
        <h1>Cross-platform entity resolution</h1>
        {info && <span className="chip">schema v{info.schema_version} · {info.schema_attributes} attributes · cutoffs {info.lo} / {info.hi}</span>}
      </header>

      <section className="card">
        <h2>Listings (JSON)</h2>
        <textarea value={text} onChange={e => setText(e.target.value)} spellCheck={false} rows={12} />
        <div className="row">
          <label><input type="checkbox" checked={useLlm} onChange={e => setUseLlm(e.target.checked)} /> Use LLM for uncertain pairs</label>
          <button onClick={run} disabled={busy}>{busy ? "Resolving…" : "Resolve"}</button>
        </div>
        {err && <p className="err">{err}</p>}
      </section>

      {out && (
        <>
          <section className="chips">
            {Object.entries(out.stats).map(([k, v]) => <span className="chip" key={k}>{k}: <b>{String(v)}</b></span>)}
          </section>

          <h2>Entities ({out.clusters.length})</h2>
          <div className="grid">
            {out.clusters.map(c => (
              <article className="card" key={c.entity_id}>
                <h3>{c.entity_id} <small>{c.members.length} listing{c.members.length > 1 ? "s" : ""}</small></h3>
                <ul>{c.members.map(m => <li key={m.id}><b>{m.source}</b> {m.title}{m.unmapped_attributes.length > 0 && <em> · unmapped: {m.unmapped_attributes.join(", ")}</em>}</li>)}</ul>
                <table><tbody>
                  {Object.entries(c.canonical).map(([a, v]) => (
                    <tr key={a} className={v.conflict ? "conflict" : ""}>
                      <td>{a}</td><td>{String(v.value)} {v.unit}</td><td>{v.n_sources}×{v.conflict ? " ⚠ conflict" : ""}</td>
                    </tr>
                  ))}
                </tbody></table>
              </article>
            ))}
          </div>

          <h2>Pair decisions</h2>
          <table className="card wide">
            <thead><tr><th>left</th><th>right</th><th>cosine</th><th>rule</th><th>tier</th><th>decision</th></tr></thead>
            <tbody>{out.decisions.map((d, i) => (
              <tr key={i}><td>{d.left}</td><td>{d.right}</td><td>{d.cosine}</td><td>{d.rule}{d.rule_reason && ` (${d.rule_reason})`}</td>
                <td><span className={`tier ${d.tier}`}>{d.tier}</span></td><td>{d.decision}{d.note && ` (${d.note})`}</td></tr>
            ))}</tbody>
          </table>
        </>
      )}
    </div>
  );
}