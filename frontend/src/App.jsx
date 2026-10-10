import { useRef, useState } from "react";
import { askQuestion, uploadReport } from "./api.js";

const STATUS_LABEL = { low: "कम", normal: "सामान्य", high: "धेरै", unknown: "—" };

function TipList({ title, items }) {
  if (!items?.length) return null;
  return (
    <div className="tips">
      <h4>{title}</h4>
      <ul>
        {items.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </ul>
    </div>
  );
}

function Chat({ reportId }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send(e) {
    e.preventDefault();
    const q = input.trim();
    if (!q || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: q }]);
    setBusy(true);
    try {
      const { answer } = await askQuestion(reportId, q);
      setMessages((m) => [...m, { role: "assistant", content: answer }]);
    } catch (err) {
      setMessages((m) => [...m, { role: "assistant", content: `⚠ ${err.message}` }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h3>प्रश्न सोध्नुहोस् · Ask about your report</h3>
      <div className="chat">
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            {m.content}
          </div>
        ))}
        {busy && <div className="bubble assistant">…</div>}
      </div>
      <form onSubmit={send} className="chat-form">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="जस्तै: कम हिमोग्लोबिन भए के खाने?"
        />
        <button disabled={busy}>पठाउनुहोस्</button>
      </form>
    </section>
  );
}

export default function App() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState(null);
  const fileRef = useRef(null);
  const audioRef = useRef(null);

  async function onFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    setResult(null);
    setPreview(file.type.startsWith("image/") ? URL.createObjectURL(file) : null);
    setLoading(true);
    try {
      setResult(await uploadReport(file));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <main className="app">
      <header>
        <h1>स्वास्थ्य रिडर</h1>
        <p>Swasthya Reader · Lab report → simple Nepali, spoken aloud</p>
      </header>

      <section className="card upload">
        <label className="upload-btn">
          {loading ? "पढ्दै छ… Reading…" : "रिपोर्ट अपलोड गर्नुहोस् · Upload report"}
          <input
            ref={fileRef}
            type="file"
            accept="image/*,application/pdf"
            onChange={onFile}
            disabled={loading}
            hidden
          />
        </label>
        <p className="hint">फोटो वा PDF · Photo or PDF of an English lab report</p>
        {preview && <img className="preview" src={preview} alt="Uploaded report" />}
        {error && <p className="error">⚠ {error}</p>}
      </section>

      {result && (
        <>
          {result.see_doctor_soon && (
            <div className="alert">
              ⚠ केही नतिजा सामान्यभन्दा धेरै फरक छन्। कृपया चाँडै डाक्टरलाई देखाउनुहोस्।
              <br />
              <small>Some results are far outside the normal range. Please see a doctor soon.</small>
            </div>
          )}

          <section className="card">
            <h3>नेपालीमा व्याख्या</h3>
            <p className="summary">{result.summary_ne}</p>
            {result.audio_url ? (
              <>
                <button className="play" onClick={() => audioRef.current?.play()}>
                  ▶ सुन्नुहोस् · Play
                </button>
                <audio ref={audioRef} src={result.audio_url} preload="auto" controls />
              </>
            ) : (
              <p className="hint">Audio unavailable. The text above still works.</p>
            )}
          </section>

          <section className="card">
            <h3>सुझावहरू</h3>
            <TipList title="खानपान" items={result.tips_ne.diet} />
            <TipList title="जीवनशैली" items={result.tips_ne.lifestyle} />
            <TipList title="बानी" items={result.tips_ne.behaviour} />
          </section>

          <section className="card">
            <h3>रिपोर्टका नतिजा · Extracted values</h3>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Test</th>
                    <th>Value</th>
                    <th>Normal range</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {result.tests.map((t, i) => (
                    <tr key={i} className={`row-${t.status}`}>
                      <td>{t.name}</td>
                      <td>
                        {t.value} {t.unit}
                      </td>
                      <td>{t.reference_range || "—"}</td>
                      <td>
                        <span className={`pill ${t.status}`}>{STATUS_LABEL[t.status]}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <Chat reportId={result.report_id} />

          <footer className="disclaimer">
            <p>{result.disclaimer_ne}</p>
            <p>{result.disclaimer_en}</p>
          </footer>
        </>
      )}

      {!result && (
        <footer className="disclaimer">
          <p>यो सहायक उपकरण मात्र हो, डाक्टरको सल्लाहको विकल्प होइन।</p>
          <p>Assistive tool only. Not a substitute for professional medical advice.</p>
        </footer>
      )}
    </main>
  );
}
