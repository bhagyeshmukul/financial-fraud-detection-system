// Main dashboard page that orchestrates prediction, metrics, and logs visualization.
import { useEffect, useMemo, useState } from "react";

import MetricsCard from "../components/MetricsCard";
import ModelCharts from "../components/ModelCharts";
import PredictionResult from "../components/PredictionResult";
import SampleScenarioPanel from "../components/SampleScenarioPanel";
import TransactionForm from "../components/TransactionForm";
import TransactionTable from "../components/TransactionTable";
import { fetchPredictionLogs, fetchSampleTransactions, predictFraud } from "../services/api";

const initialForm = () => {
  // Initialize all model-required feature values with numeric defaults.
  const base = { Time: 0, Amount: 0 };
  for (let i = 1; i <= 28; i += 1) base[`V${i}`] = 0;
  return base;
};

function FraudDashboard() {
  const [form, setForm] = useState(initialForm());
  const [result, setResult] = useState(null);
  const [logs, setLogs] = useState([]);
  const [samples, setSamples] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const metrics = useMemo(() => ({ accuracy: 0.98, precision: 0.90, recall: 0.92, f1_score: 0.91, roc_auc: 0.97 }), []);

  const onChange = (event) => {
    // Keep form values numeric so payload matches backend schema types.
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: Number(value) }));
  };

  const loadLogs = async () => {
    // Load recent predictions for the audit/log table.
    const response = await fetchPredictionLogs();
    setLogs(response.data);
  };

  const loadSamples = async () => {
    // Load curated threat-level scenarios for interactive testing.
    const response = await fetchSampleTransactions();
    setSamples(response.data?.samples || []);
  };

  useEffect(() => {
    loadLogs();
    loadSamples();
  }, []);

  const onSubmit = async (event) => {
    // Submit one prediction request and refresh logs upon success.
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const response = await predictFraud(form);
      setResult(response.data);
      await loadLogs();
    } catch (err) {
      setError(err?.response?.data?.detail || "Prediction request failed.");
    } finally {
      setLoading(false);
    }
  };

  const onApplySample = (payload) => {
    setForm(payload);
    setResult(null);
    setError("");
  };

  return (
    <div className="container dashboard-shell">
      <section className="hero-panel card">
        <h1>Fraud Signal Intelligence Console</h1>
        <p className="subtitle">
          Real-time fraud scoring with model probability, risk buckets, and prediction log tracking.
        </p>
        <div className="hero-pills">
          <span className="pill">30 input signals</span>
          <span className="pill">`Time` + `Amount` + `V1..V28`</span>
          <span className="pill">Audit logging enabled</span>
        </div>
      </section>

      <section className="card v-explainer-inline">
        <h3>What exactly are V1 to V28?</h3>
        <p>
          `V1..V28` are anonymized, PCA-transformed behavior signals from the original credit-card dataset.
          They are <strong>not raw business columns</strong> like location/device/merchant name.
          Think of them as compressed hidden patterns: unusual combinations can increase fraud probability.
        </p>
      </section>

      {error && <div className="error">{error}</div>}
      <SampleScenarioPanel samples={samples} onApplySample={onApplySample} />
      <TransactionForm form={form} onChange={onChange} onSubmit={onSubmit} loading={loading} />
      <PredictionResult result={result} />
      <MetricsCard metrics={metrics} />
      <ModelCharts />
      <TransactionTable />
      <div className="card">
        <h3>Latest Prediction Logs</h3>
        {loading && <p>Loading...</p>}
        {!loading && (
          <table>
            <thead><tr><th>ID</th><th>Amount</th><th>Probability</th><th>Label</th><th>Risk</th><th>Created At</th></tr></thead>
            <tbody>
              {logs.map((item) => (
                <tr key={item.id}>
                  <td>{item.id}</td>
                  <td>{item.transaction_amount}</td>
                  <td>{(item.fraud_probability * 100).toFixed(2)}%</td>
                  <td>{item.prediction_label}</td>
                  <td>{item.risk_level}</td>
                  <td>{item.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default FraudDashboard;
