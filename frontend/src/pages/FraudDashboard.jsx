import { useMemo, useState } from "react";

import MetricsCard from "../components/MetricsCard";
import ModelCharts from "../components/ModelCharts";
import PredictionResult from "../components/PredictionResult";
import TransactionForm from "../components/TransactionForm";
import TransactionTable from "../components/TransactionTable";
import { fetchPredictionLogs, predictFraud } from "../services/api";

const initialForm = () => {
  const base = { Time: 0, Amount: 0 };
  for (let i = 1; i <= 28; i += 1) base[`V${i}`] = 0;
  return base;
};

function FraudDashboard() {
  const [form, setForm] = useState(initialForm());
  const [result, setResult] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const metrics = useMemo(() => ({ accuracy: 0.98, precision: 0.90, recall: 0.92, f1_score: 0.91, roc_auc: 0.97 }), []);

  const onChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: Number(value) }));
  };

  const loadLogs = async () => {
    const response = await fetchPredictionLogs();
    setLogs(response.data);
  };

  const onSubmit = async (event) => {
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

  return (
    <div className="container">
      <h1>Financial Fraud Detection Dashboard</h1>
      {error && <div className="error">{error}</div>}
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
