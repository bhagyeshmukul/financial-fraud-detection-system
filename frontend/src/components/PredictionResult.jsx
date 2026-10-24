/** Show an actual saved decision, its applied threshold and the candidate that produced it. */
import { percent } from "./MetricsCard";
/** Stay hidden until a request succeeds; input context is not a causal model explanation. */
export default function PredictionResult({ result }) {
  if (!result) return null;
  return (
    <section className="card result-panel" aria-live="polite">
      <div className="section-heading">
        <h3>Prediction result</h3>
        <span className={`badge ${result.risk_level.toLowerCase()}`}>
          {result.risk_level} risk
        </span>
      </div>
      <div className="result-score">
        <strong>{percent(result.fraud_probability)}</strong>
        <span>estimated fraud probability</span>
      </div>
      <p>
        <strong>{result.prediction_label}</strong> · threshold{" "}
        {percent(result.decision_threshold)} ·{" "}
        {result.processing_ms?.toFixed(1)} ms
      </p>
      <ul>
        {/* Each input/history fact is independently supplied by the shared backend feature code. */}
        {result.context.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      {result.used_model && (
        <div aria-label="Model decision">
          <p>
            <strong>Model used:</strong> {result.used_model} · requested{" "}
            {result.requested_model}
          </p>
          <p>{result.routing_reason}</p>
          {result.router_version && (
            <small>Router version: {result.router_version}</small>
          )}
        </div>
      )}
      <p className="muted">
        Context describes observed inputs, not a causal explanation of the
        model.
      </p>
      <code>{result.model_version}</code>
    </section>
  );
}
