// Transaction input form with field-level guidance for model features.
const fields = ["Time", ...Array.from({ length: 28 }, (_, i) => `V${i + 1}`), "Amount"];

const fieldHints = {
  Time: "Elapsed seconds since first transaction in the dataset timeline.",
  Amount: "Transaction amount in currency units.",
  V: "Anonymized PCA component used by the model (latent behavior signal).",
};

const getFieldHint = (field) => {
  if (field === "Time") return fieldHints.Time;
  if (field === "Amount") return fieldHints.Amount;
  return fieldHints.V;
};

function TransactionForm({ form, onChange, onSubmit, loading }) {
  return (
    <form className="card" onSubmit={onSubmit}>
      <h3>Transaction Input</h3>
      <p className="muted">
        Enter all 30 features required by the model: <strong>Time</strong>, <strong>V1..V28</strong>, and <strong>Amount</strong>.
      </p>
      <p className="muted">
        Quick interpretation: <strong>V1..V28</strong> are anonymized behavioral components (PCA signals), not readable business labels.
      </p>
      <div className="grid">
        {fields.map((field) => (
          <label key={field} className="field-label">
            <span className="field-name">{field}</span>
            <input
              name={field}
              type="number"
              step="any"
              value={form[field]}
              onChange={onChange}
              required
            />
            <small className="field-hint">{getFieldHint(field)}</small>
          </label>
        ))}
      </div>
      <details className="feature-explainer">
        <summary>What are V1 to V28?</summary>
        <p>
          <strong>V1..V28</strong> are anonymized PCA-transformed variables from the credit-card dataset.
          They do not map to raw business column names, but they capture hidden transaction behavior patterns
          (spending rhythm, interaction combinations, anomaly signatures) that help the model identify suspicious activity.
        </p>
      </details>
      <button type="submit" disabled={loading}>{loading ? "Predicting..." : "Predict Fraud"}</button>
    </form>
  );
}

export default TransactionForm;
