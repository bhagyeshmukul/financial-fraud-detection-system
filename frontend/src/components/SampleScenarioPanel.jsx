/** Load one labelled legitimate/fraud example without pretending the sample reflects prevalence. */
export default function SampleScenarioPanel({
  samples,
  onApplySample,
  disabled,
}) {
  const choices = [
    samples.find((sample) => sample.actual_label === 0),
    samples.find((sample) => sample.actual_label === 1),
  ].filter(Boolean);
  return (
    <div className="card">
      <h3>Dataset examples</h3>
      <p className="muted">
        Original validation rows with known labels. A model can disagree; the
        label is never supplied to prediction.
      </p>
      <div className="button-row">
        {/* Each button copies original publisher inputs; the model has not scored it yet. */}
        {choices.map((sample) => (
          <button
            type="button"
            className="secondary"
            key={sample.id}
            disabled={disabled}
            onClick={() => onApplySample(sample.payload)}
          >
            Load{" "}
            {sample.actual_label ? "labelled fraud" : "labelled legitimate"}{" "}
            example
          </button>
        ))}
      </div>
      {!samples.length && (
        <p>
          No verified examples available. Import the dataset and train this
          profile first.
        </p>
      )}
    </div>
  );
}
