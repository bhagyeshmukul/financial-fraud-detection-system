/** Display recorded metrics without substituting invented values for missing evidence. */
/** Format a 0..1 fraction as a percentage while preserving unavailable values. */
export const percent = (value, digits = 2) =>
  value == null ? "Unavailable" : `${(value * 100).toFixed(digits)}%`;
/** Render the same metric definitions for frozen tests and labelled uploads. */
export default function MetricsCard({
  metrics,
  title = "Frozen test evaluation",
}) {
  if (!metrics)
    return <div className="empty">Matching evaluation is unavailable.</div>;
  return (
    <section aria-label={title}>
      <h3>{title}</h3>
      <div className="metrics-grid">
        {/* Iterate over parallel label/value pairs to keep all six cards consistent. */}
        {[
          ["Accuracy", percent(metrics.accuracy)],
          ["Precision", percent(metrics.precision)],
          ["Fraud recall", percent(metrics.recall)],
          ["PR-AUC", metrics.pr_auc?.toFixed(4) ?? "Unavailable"],
          [
            "Average precision",
            metrics.average_precision?.toFixed(4) ?? "Unavailable",
          ],
          ["ROC-AUC", metrics.roc_auc?.toFixed(4) ?? "Unavailable"],
        ].map(([name, value]) => (
          <div className="metric" key={name}>
            <span>{name}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      <p className="muted">
        {metrics.samples?.toLocaleString()} transactions ·{" "}
        {metrics.frauds?.toLocaleString()} labelled frauds · threshold{" "}
        {metrics.threshold?.toPrecision(4)}
      </p>
    </section>
  );
}
