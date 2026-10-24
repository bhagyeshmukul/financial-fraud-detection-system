/** Coordinate the four dashboard workspaces and their API-backed state.
 * Report inspection, scoring policy and analyst review remain separate choices.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import MetricsCard, { percent } from "../components/MetricsCard";
import ModelCharts from "../components/ModelCharts";
import ModelPicker from "../components/ModelPicker";
import PredictionResult from "../components/PredictionResult";
import SampleScenarioPanel from "../components/SampleScenarioPanel";
import TransactionForm from "../components/TransactionForm";
import TransactionTable from "../components/TransactionTable";
import api, {
  createSession,
  download,
  errorText,
  fetchLogs,
  fetchOperations,
  fetchProfiles,
  fetchReport,
  fetchSamples,
  predict,
  reviewPrediction,
  scoreCsv,
} from "../services/api";

/** Download a snapshot, then release the temporary browser object URL. */
function saveJson(value, filename) {
  const link = document.createElement("a");
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const tabs = [
  ["analysis", "Analysis"],
  ["demo", "Live demo"],
  ["audit", "Analyst review"],
  ["operations", "Service health"],
];
// HTML inputs hold strings; identifiers stay text while model numbers become numbers.
const numericTransaction = (form) =>
  Object.fromEntries(
    Object.entries(form).map(([key, value]) => [
      key,
      ["customer", "merchant", "category"].includes(key)
        ? value
        : Number(value),
    ]),
  );

/** Hold the selected dataset, user inputs, history, report and replay lifecycle. */
export default function FraudDashboard() {
  // React state drives rendering; refs retain current async identities/timer handles.
  const [profile, setProfile] = useState("banksim");
  const [modelChoice, setModelChoice] = useState("champion");
  const [tab, setTab] = useState("analysis");
  const [profiles, setProfiles] = useState([]);
  const [report, setReport] = useState(null);
  const [inspectedModel, setInspectedModel] = useState("");
  const [samples, setSamples] = useState([]);
  const [form, setForm] = useState({});
  const [result, setResult] = useState(null);
  const [session, setSession] = useState(null);
  const [logs, setLogs] = useState([]);
  const [filter, setFilter] = useState({ risk: "", state: "" });
  const [csv, setCsv] = useState(null);
  const [batch, setBatch] = useState(null);
  const [operations, setOperations] = useState(null);
  const [readiness, setReadiness] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [reportLoading, setReportLoading] = useState(true);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(2);
  const [replayed, setReplayed] = useState(0);
  const [distribution, setDistribution] = useState("");
  const replayActive = useRef(false);
  const replayTimer = useRef(null);
  const sessionRef = useRef(null);
  const logRequest = useRef(0);
  const fileRef = useRef(null);

  // Cancel the next scheduled replay request and update the visible play state.
  const stopReplay = useCallback(() => {
    replayActive.current = false;
    clearTimeout(replayTimer.current);
    setPlaying(false);
  }, []);
  // A generation counter prevents a slower old filter request overwriting newer rows.
  const loadLogs = useCallback(
    async (beforeId = null) => {
      const request = ++logRequest.current;
      const response = await fetchLogs({
        profile,
        ...Object.fromEntries(
          Object.entries(filter).filter(([, value]) => value),
        ),
        ...(beforeId ? { before_id: beforeId } : {}),
      });
      if (request !== logRequest.current) return;
      setLogs((previous) =>
        beforeId ? [...previous, ...response.data] : response.data,
      );
    },
    [profile, filter],
  );

  // A dataset change invalidates its previous report, sample form and demo history.
  useEffect(() => {
    const controller = new AbortController();
    stopReplay();
    sessionRef.current = null;
    setSession(null);
    setReport(null);
    setModelChoice("champion");
    setSamples([]);
    setForm({});
    setResult(null);
    setBatch(null);
    setCsv(null);
    setReplayed(0);
    setError("");
    setReportLoading(true);
    if (fileRef.current) fileRef.current.value = "";
    // Report and examples can fail independently; show real errors, never fake results.
    Promise.allSettled([
      fetchReport(profile, controller.signal),
      fetchSamples(profile, controller.signal),
    ]).then(([evaluation, examples]) => {
      if (controller.signal.aborted) return;
      if (evaluation.status === "fulfilled") {
        setReport(evaluation.value.data);
        setInspectedModel(evaluation.value.data.selected_model);
        setDistribution(
          Object.keys(evaluation.value.data.summary.distributions)[0] || "",
        );
      } else setError(errorText(evaluation.reason));
      if (examples.status === "fulfilled") {
        setSamples(examples.value.data.samples);
        if (examples.value.data.samples.length)
          setForm(examples.value.data.samples[0].payload);
      }
      setReportLoading(false);
    });
    fetchProfiles()
      .then((response) => setProfiles(response.data))
      .catch((failure) => {
        if (!controller.signal.aborted) setError(errorText(failure));
      });
    // Cleanup also handles React StrictMode's development mount/unmount checks.
    return () => {
      controller.abort();
      replayActive.current = false;
      clearTimeout(replayTimer.current);
    };
  }, [profile, stopReplay]);

  // Refresh persisted rows when dataset/filter dependencies change.
  useEffect(() => {
    loadLogs().catch((failure) => setError(errorText(failure)));
  }, [loadLogs]);

  // Query operational counters and dependency readiness without coupling their failures.
  const refreshHealth = useCallback(async () => {
    const [stats, health] = await Promise.allSettled([
      fetchOperations(),
      api.get("/health/ready"),
    ]);
    if (stats.status === "fulfilled") setOperations(stats.value.data);
    else setError(errorText(stats.reason));
    setReadiness(
      health.status === "fulfilled"
        ? health.value.data
        : health.reason?.response?.data || null,
    );
  }, []);
  useEffect(() => {
    if (tab === "operations") refreshHealth();
  }, [tab, refreshHealth]);

  // Reuse one history until the user requests a fresh demo session.
  const ensureSession = async () => {
    if (sessionRef.current) return sessionRef.current;
    const response = await createSession(profile, profile === "banksim");
    sessionRef.current = response.data.id;
    setSession(response.data.id);
    return response.data.id;
  };
  // A new session resets the demonstration and cannot inherit the old history.
  const newSession = async () => {
    stopReplay();
    sessionRef.current = null;
    setSession(null);
    setResult(null);
    setReplayed(0);
    try {
      await ensureSession();
    } catch (failure) {
      setError(errorText(failure));
    }
  };
  // Carry the actual scoring choice to the API and reject stale-session display updates.
  const score = async (transaction) => {
    const id = await ensureSession();
    const response = await predict(
      profile,
      id,
      transaction,
      crypto.randomUUID(),
      modelChoice,
    );
    if (sessionRef.current === id) {
      setResult(response.data);
      await loadLogs();
    }
    return response.data;
  };
  // Prevent browser navigation, score normalized input, and always release the busy state.
  const onSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await score(numericTransaction(form));
    } catch (failure) {
      setError(errorText(failure));
    } finally {
      setLoading(false);
    }
  };
  // Replay serially so a history-dependent request finishes before the next is scheduled.
  const startReplay = async () => {
    if (!samples.length) return;
    setError("");
    setPlaying(true);
    replayActive.current = true;
    let position = replayed >= samples.length ? 0 : replayed;
    // One replay step loads an example, records its result and schedules the next step.
    const next = async () => {
      if (!replayActive.current || position >= samples.length) {
        stopReplay();
        return;
      }
      try {
        const example = samples[position];
        setForm(example.payload);
        await score(example.payload);
        position += 1;
        setReplayed(position);
        if (replayActive.current)
          replayTimer.current = setTimeout(next, 1000 / speed);
      } catch (failure) {
        setError(errorText(failure));
        stopReplay();
      }
    };
    await next();
  };
  // Uploads use fresh unseeded histories; optional labels are reserved for evaluation.
  const onCsv = async (event) => {
    event.preventDefault();
    if (!csv) return;
    if (csv.size > 5 * 1024 * 1024) {
      setError("CSV uploads are limited to 5 MB.");
      return;
    }
    setLoading(true);
    setError("");
    setBatch(null);
    try {
      // Every upload has its own history; labels are used only for evaluation.
      const response = await createSession(profile, false);
      const scored = await scoreCsv(
        profile,
        response.data.id,
        csv,
        modelChoice,
      );
      setBatch(scored.data);
      await loadLogs();
    } catch (failure) {
      setError(errorText(failure));
    } finally {
      setLoading(false);
    }
  };
  // Saving a review changes analyst fields, then reloads the durable record list.
  const onReview = async (id, state, notes) => {
    try {
      await reviewPrediction(id, state, notes);
      await loadLogs();
      return true;
    } catch (failure) {
      setError(errorText(failure));
      return false;
    }
  };
  // Export the current filters and display an error if the server cannot produce a CSV.
  const safeDownload = async () => {
    try {
      await download("/api/v1/predictions/export", "prediction-logs.csv", {
        profile,
        ...Object.fromEntries(
          Object.entries(filter).filter(([, value]) => value),
        ),
      });
    } catch (failure) {
      setError(errorText(failure));
    }
  };
  // This selection controls charts only; modelChoice independently controls prediction.
  const metrics = report?.models[inspectedModel]?.test;
  const cm = metrics?.confusion_matrix;
  const active = profiles.find((entry) => entry.id === profile);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/">
          <span className="brand-mark">F</span>
          <span>
            Fraud Signal<small>Analysis & demonstration</small>
          </span>
        </a>
        <p className="sidebar-label">WORKSPACE</p>
        <nav aria-label="Workspace">
          {/* Render one navigation button per workspace; changing views stops replay. */}
          {tabs.map(([id, name], index) => (
            <button
              key={id}
              className={tab === id ? "nav-item active" : "nav-item"}
              aria-current={tab === id ? "page" : undefined}
              onClick={() => {
                stopReplay();
                setTab(id);
              }}
            >
              <span>0{index + 1}</span>
              {name}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="status-dot" />
          Research data, real scoring
          <p>
            Model results, audit records, and service health stay connected.
          </p>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div>
            <span className="eyebrow">FINANCIAL FRAUD DETECTION SYSTEM</span>
            <h1>{tabs.find(([id]) => id === tab)[1]}</h1>
          </div>
          <label className="profile-picker">
            Dataset profile
            <select
              aria-label="Dataset profile"
              value={profile}
              disabled={loading || playing}
              onChange={(event) => setProfile(event.target.value)}
            >
              <option value="banksim">BankSim · readable payments</option>
              <option value="credit_card">ULB · credit-card benchmark</option>
            </select>
          </label>
        </header>
        <div className="profile-banner">
          <span className={`badge ${active?.available ? "low" : "medium"}`}>
            {active?.available ? "Model loaded" : "Model unavailable"}
          </span>
          <span>
            {profile === "banksim"
              ? "Simulated bank payments · earlier-day behavioural history"
              : "Anonymized card transactions · PCA input features"}
          </span>
        </div>
        {error && (
          <div className="error" role="alert">
            <span>{error}</span>
            <button className="text-button" onClick={() => setError("")}>
              Dismiss
            </button>
          </div>
        )}
        {tab === "analysis" && (
          <>
            <section className="intro">
              <h2>Understand the evidence.</h2>
              <p>
                Compare algorithms, inspect fraud trade-offs, and score your own
                data. These metrics come from the frozen chronological test
                period.
              </p>
            </section>
            {reportLoading ? (
              <div className="card">Loading verified evaluation…</div>
            ) : !report ? (
              <div className="card empty">
                <h3>Evaluation unavailable</h3>
                <p>
                  Import the original dataset, then train this profile. A
                  missing result is never replaced with a sample number.
                </p>
              </div>
            ) : (
              <>
                <section className="card">
                  <div className="section-heading">
                    <h3>Model evaluation</h3>
                    <label>
                      Inspect model
                      <select
                        aria-label="Inspect model"
                        value={inspectedModel}
                        onChange={(event) =>
                          setInspectedModel(event.target.value)
                        }
                      >
                        {/* Inspect all frozen candidates, including the routing experiment. */}
                        {Object.keys(report.models).map((name) => (
                          <option key={name} value={name}>
                            {name}
                            {name === report.selected_model
                              ? " · served model"
                              : ""}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <MetricsCard metrics={metrics} />
                  <div
                    className="button-row"
                    aria-label="Served model quality goals"
                  >
                    {Object.entries(report.quality_goals_met).map(
                      ([name, met]) => (
                        <span
                          key={name}
                          className={`badge ${met ? "low" : "high"}`}
                        >
                          Served {name}: {met ? "goal met" : "goal missed"}
                        </span>
                      ),
                    )}
                  </div>
                  <p className="notice">
                    The always-legitimate baseline scores{" "}
                    {percent(report.always_legitimate_baseline.accuracy)}{" "}
                    accuracy while detecting no fraud. Precision and recall show
                    whether a model is useful.
                  </p>
                  <div className="button-row">
                    <button
                      className="secondary"
                      onClick={() =>
                        saveJson(report, `${profile}-evaluation.json`)
                      }
                    >
                      Download full report
                    </button>
                    <span className="muted">
                      Served model: {report.selected_model}
                    </span>
                  </div>
                </section>
                <div className="two-columns">
                  <section className="card">
                    <h3>Confusion matrix</h3>
                    {cm && (
                      <div className="confusion">
                        <div>
                          <span>Legitimate, allowed</span>
                          <strong>{cm[0][0].toLocaleString()}</strong>
                        </div>
                        <div className="false">
                          <span>False alerts</span>
                          <strong>{cm[0][1].toLocaleString()}</strong>
                        </div>
                        <div className="false">
                          <span>Missed fraud</span>
                          <strong>{cm[1][0].toLocaleString()}</strong>
                        </div>
                        <div>
                          <span>Detected fraud</span>
                          <strong>{cm[1][1].toLocaleString()}</strong>
                        </div>
                      </div>
                    )}
                  </section>
                  <section className="card">
                    <h3>Data and lineage</h3>
                    <dl>
                      <dt>Original rows</dt>
                      <dd>{report.dataset.rows.toLocaleString()}</dd>
                      <dt>Fraud prevalence</dt>
                      <dd>{percent(report.summary.fraud_rate)}</dd>
                      <dt>Dataset</dt>
                      <dd>
                        <a
                          href={report.dataset.source}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Publisher source
                        </a>
                      </dd>
                      <dt>License</dt>
                      <dd>{report.dataset.license}</dd>
                      <dt>Feature version</dt>
                      <dd>{report.feature_version}</dd>
                    </dl>
                    <details>
                      <summary>Model identity and data checksum</summary>
                      <code>{report.model_version}</code>
                      <code>{report.dataset.sha256}</code>
                    </details>
                  </section>
                </div>
                <ModelCharts metrics={metrics} />
                {report.auto_policy && (
                  <section
                    className="card"
                    aria-label="Automatic model selection evaluation"
                  >
                    <h3>Automatic model selection</h3>
                    <p>
                      <strong>
                        {report.auto_policy.router_promoted
                          ? "Learned router activated"
                          : report.auto_policy.available
                            ? "Auto uses the strongest eligible individual"
                            : "Auto unavailable"}
                      </strong>
                    </p>
                    <p>{report.auto_policy.reason}</p>
                    {report.auto_policy.test && (
                      <p>
                        Auto historical test: precision{" "}
                        {percent(report.auto_policy.test.precision)} · fraud
                        recall {percent(report.auto_policy.test.recall)}. Policy
                        was selected on validation, before this evaluation.
                      </p>
                    )}
                    <p className="muted">{report.evaluation_note}</p>
                  </section>
                )}
                <section className="card">
                  <h3>All model comparisons</h3>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Algorithm</th>
                          <th>Resampling</th>
                          <th>Validation AP</th>
                          <th>Test AP</th>
                          <th>Precision</th>
                          <th>Recall</th>
                        </tr>
                      </thead>
                      <tbody>
                        {/* One row per measured candidate; the star identifies the champion. */}
                        {Object.entries(report.models).map(([name, value]) => (
                          <tr key={name}>
                            <td>
                              {name}
                              {name === report.selected_model ? " ★" : ""}
                            </td>
                            <td>{value.resampling}</td>
                            <td>
                              {value.validation.average_precision.toFixed(4)}
                            </td>
                            <td>{value.test.average_precision.toFixed(4)}</td>
                            <td>{percent(value.test.precision)}</td>
                            <td>{percent(value.test.recall)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="muted">
                    {report.selection_rule} AP means average precision; it
                    differs from trapezoidal PR-AUC.
                  </p>
                </section>
                <div className="two-columns">
                  <section className="card">
                    <div className="section-heading">
                      <h3>Feature distribution</h3>
                      <select
                        aria-label="Distribution feature"
                        value={distribution}
                        onChange={(event) =>
                          setDistribution(event.target.value)
                        }
                      >
                        {Object.keys(report.summary.distributions).map(
                          (column) => (
                            <option key={column}>{column}</option>
                          ),
                        )}
                      </select>
                    </div>
                    <div
                      className="histogram"
                      aria-label={`${distribution} histogram`}
                    >
                      {(report.summary.distributions[distribution] || []).map(
                        (point, index, values) => (
                          <div
                            key={point.bin}
                            title={`${point.bin}: ${point.count}`}
                            style={{
                              height: `${Math.max(1, (point.count / Math.max(...values.map((value) => value.count))) * 100)}%`,
                            }}
                          />
                        ),
                      )}
                    </div>
                    <p className="muted">
                      Full dataset distribution; hover over bars for bins and
                      counts.
                    </p>
                  </section>
                  <section className="card">
                    <h3>Global feature importance</h3>
                    {/* These are global validation importances, not per-payment causes. */}
                    {report.feature_importance.slice(0, 7).map((item) => (
                      <div className="importance" key={item.feature}>
                        <span>{item.feature}</span>
                        <strong>{item.importance.toFixed(4)}</strong>
                      </div>
                    ))}
                    <p className="muted">
                      Validation permutation importance of the served model.
                      This does not explain an individual decision.
                    </p>
                  </section>
                </div>
                <section className="card">
                  <h3>Chronological evaluation boundaries</h3>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Partition</th>
                          <th>Rows</th>
                          <th>Frauds</th>
                          <th>Start</th>
                          <th>End</th>
                        </tr>
                      </thead>
                      <tbody>
                        {/* Time-group boundaries explain exactly which rows did each job. */}
                        {Object.entries(report.partitions).map(
                          ([name, value]) => (
                            <tr key={name}>
                              <td>{name}</td>
                              <td>{value.rows.toLocaleString()}</td>
                              <td>{value.frauds}</td>
                              <td>{value.start}</td>
                              <td>{value.end}</td>
                            </tr>
                          ),
                        )}
                      </tbody>
                    </table>
                  </div>
                </section>
              </>
            )}
            <section className="card">
              <h3>Analyse a CSV</h3>
              <p className="muted">
                Up to 5 MB / 5,000 rows. Each upload gets isolated history.
                Optional labels calculate uploaded-data metrics, separate from
                the benchmark.
              </p>
              <details>
                <summary>Required CSV columns</summary>
                <code>
                  {profile === "banksim"
                    ? "step,customer,merchant,category,amount[,fraud]"
                    : "Time,V1,…,V28,Amount[,Class]"}
                </code>
              </details>
              <form onSubmit={onCsv}>
                <ModelPicker
                  label="CSV prediction model"
                  choices={active?.model_choices}
                  value={modelChoice}
                  onChange={setModelChoice}
                  disabled={loading || playing}
                />
                <label>
                  Transaction CSV
                  <input
                    ref={fileRef}
                    aria-label="Transaction CSV"
                    type="file"
                    accept=".csv,text/csv"
                    required
                    onChange={(event) =>
                      setCsv(event.target.files?.[0] || null)
                    }
                  />
                </label>
                <button
                  type="submit"
                  disabled={loading || !csv || !active?.available}
                >
                  {loading ? "Scoring CSV…" : "Score CSV"}
                </button>
              </form>
              {batch && (
                <div aria-live="polite">
                  <p>
                    <strong>{batch.rows.toLocaleString()} rows scored</strong>{" "}
                    in {batch.processing_ms.toFixed(0)} ms.{" "}
                    {batch.evaluation_note}
                  </p>
                  {batch.used_models && (
                    <p>
                      Models used:{" "}
                      {Object.entries(batch.used_models)
                        .map(([name, count]) => `${name}: ${count}`)
                        .join(" · ")}
                    </p>
                  )}
                  {batch.evaluation && (
                    <MetricsCard
                      metrics={batch.evaluation}
                      title="Your uploaded data"
                    />
                  )}
                  <button
                    className="secondary"
                    onClick={() =>
                      saveJson(batch, `${profile}-batch-results.json`)
                    }
                  >
                    Download scored results
                  </button>
                </div>
              )}
            </section>
          </>
        )}
        {tab === "demo" && (
          <>
            <section className="intro">
              <h2>Watch a transaction become a decision.</h2>
              <p>
                Explore genuine dataset rows or change the inputs. Every
                successful prediction creates a persistent audit record.
              </p>
            </section>
            <div className="card">
              <ModelPicker
                choices={active?.model_choices}
                value={modelChoice}
                onChange={setModelChoice}
                disabled={loading || playing}
              />
              <div className="section-heading">
                <h3>Replay controls</h3>
                <button
                  className="secondary"
                  disabled={loading || playing}
                  onClick={newSession}
                >
                  New demo session
                </button>
              </div>
              <div className="button-row">
                <button
                  disabled={!samples.length || loading}
                  onClick={playing ? stopReplay : startReplay}
                >
                  {playing ? "Pause replay" : "Play replay"}
                </button>
                <label>
                  Maximum replay rate
                  <select
                    value={speed}
                    disabled={playing}
                    onChange={(event) => setSpeed(Number(event.target.value))}
                  >
                    <option value={1}>1 transaction / second</option>
                    <option value={2}>2 transactions / second</option>
                    <option value={5}>5 transactions / second</option>
                  </select>
                </label>
                <span>
                  {replayed} / {samples.length} examples
                </span>
              </div>
              <p className="muted">
                Selected validation examples, not representative traffic or a
                new accuracy test. BankSim starts with a fixed earlier-day
                history, then records only this session’s observations.
              </p>
              <code>
                {session
                  ? `Session ${session}`
                  : "A new session starts with the first prediction."}
              </code>
            </div>
            <SampleScenarioPanel
              samples={samples}
              disabled={playing || loading}
              onApplySample={(payload) => {
                setForm(payload);
                setResult(null);
                setError("");
              }}
            />
            <div className="demo-columns">
              <TransactionForm
                profile={profile}
                form={form}
                setForm={setForm}
                onSubmit={onSubmit}
                loading={loading || playing}
              />
              <PredictionResult result={result} />
            </div>
            <section className="card">
              <h3>Recent predictions</h3>
              <TransactionTable logs={logs.slice(0, 10)} onReview={onReview} />
            </section>
          </>
        )}
        {tab === "audit" && (
          <>
            <section className="intro">
              <h2>Review, annotate, and trace.</h2>
              <p>
                Inspect persisted predictions and their model versions. Review
                states never replace verified fraud labels.
              </p>
            </section>
            <section className="card">
              <div className="section-heading">
                <h3>Prediction history</h3>
                <div className="button-row">
                  <button
                    className="secondary"
                    onClick={() =>
                      loadLogs().catch((failure) =>
                        setError(errorText(failure)),
                      )
                    }
                  >
                    Refresh
                  </button>
                  <button onClick={safeDownload}>Export CSV</button>
                </div>
              </div>
              <div className="button-row">
                <label>
                  Risk filter
                  <select
                    aria-label="Risk filter"
                    value={filter.risk}
                    onChange={(event) =>
                      setFilter((previous) => ({
                        ...previous,
                        risk: event.target.value,
                      }))
                    }
                  >
                    <option value="">All risks</option>
                    {["Low", "Medium", "High"].map((risk) => (
                      <option key={risk}>{risk}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Review filter
                  <select
                    aria-label="Review filter"
                    value={filter.state}
                    onChange={(event) =>
                      setFilter((previous) => ({
                        ...previous,
                        state: event.target.value,
                      }))
                    }
                  >
                    <option value="">All review states</option>
                    <option value="open">Open</option>
                    <option value="under_review">Under review</option>
                    <option value="closed">Closed</option>
                  </select>
                </label>
              </div>
              <TransactionTable logs={logs} onReview={onReview} />
              {logs.length >= 50 && (
                <button
                  className="secondary"
                  onClick={() =>
                    loadLogs(logs.at(-1).id).catch((failure) =>
                      setError(errorText(failure)),
                    )
                  }
                >
                  Load older predictions
                </button>
              )}
            </section>
          </>
        )}
        {tab === "operations" && (
          <>
            <section className="intro">
              <h2>Inspect the running service.</h2>
              <p>
                Readiness checks cover the database, model artifacts, and
                matching evaluation reports.
              </p>
            </section>
            <section className="card">
              <div className="section-heading">
                <h3>Service readiness</h3>
                <button className="secondary" onClick={refreshHealth}>
                  Refresh health
                </button>
              </div>
              <span className={`badge ${readiness?.ready ? "low" : "high"}`}>
                {readiness?.ready ? "Ready" : "Not ready"}
              </span>
              {readiness?.checks &&
                Object.entries(readiness.checks).map(([name, check]) => (
                  <p key={name}>
                    <strong>{name}:</strong>{" "}
                    {check.ready ? "ready" : check.reason}
                  </p>
                ))}
            </section>
            {operations && (
              <section className="card">
                <h3>Observed traffic</h3>
                <div className="metrics-grid">
                  {[
                    [
                      "Persisted predictions",
                      operations.predictions.toLocaleString(),
                    ],
                    [
                      "Prediction p50",
                      operations.prediction_p50_ms == null
                        ? "Unavailable"
                        : `${operations.prediction_p50_ms.toFixed(1)} ms`,
                    ],
                    [
                      "Prediction p95",
                      operations.prediction_p95_ms == null
                        ? "Unavailable"
                        : `${operations.prediction_p95_ms.toFixed(1)} ms`,
                    ],
                    ["HTTP requests", operations.http.requests ?? 0],
                    ["Server failures", operations.http.status_5xx ?? 0],
                  ].map(([name, value]) => (
                    <div className="metric" key={name}>
                      <span>{name}</span>
                      <strong>{value}</strong>
                    </div>
                  ))}
                </div>
                <p className="muted">
                  {operations.prediction_latency_scope}. HTTP counters cover
                  worker {operations.process_id} since startup, not a fleet
                  aggregate. Batch prediction timings are amortized per row.
                </p>
              </section>
            )}
          </>
        )}
        <footer>
          Fraud Signal · Python / Scikit-Learn / Random Forest / XGBoost / SMOTE
          ·{" "}
          {profile === "banksim"
            ? "BankSim research simulation"
            : "ULB research benchmark"}
        </footer>
      </main>
    </div>
  );
}
