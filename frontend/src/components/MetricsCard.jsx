// Card component to display key model-quality metrics.
function MetricsCard({ metrics }) {
  if (!metrics) return null;
  return (
    <div className="card">
      <h3>Model Metrics (Selected Model)</h3>
      <div className="metrics-grid">
        <p>Accuracy: {metrics.accuracy?.toFixed?.(4) ?? "-"}</p>
        <p>Precision: {metrics.precision?.toFixed?.(4) ?? "-"}</p>
        <p>Recall: {metrics.recall?.toFixed?.(4) ?? "-"}</p>
        <p>F1-Score: {metrics.f1_score?.toFixed?.(4) ?? "-"}</p>
        <p>ROC-AUC: {metrics.roc_auc?.toFixed?.(4) ?? "-"}</p>
      </div>
    </div>
  );
}

export default MetricsCard;
