// Interactive panel to load story-based threat-level sample payloads into the form.
function SampleScenarioPanel({ samples, onApplySample }) {
  return (
    <div className="card">
      <h3>Threat-Level Sample Scenarios</h3>
      <p className="muted">
        Pick a scenario to auto-fill the 30-feature form. Each story represents a different fraud-risk pattern.
      </p>
      <div className="scenario-grid">
        {samples.map((sample) => (
          <div key={sample.id} className={`scenario-card ${sample.threat_level.toLowerCase()}`}>
            <div className="scenario-head">
              <h4>{sample.title}</h4>
              <span className={`badge ${sample.threat_level.toLowerCase()}`}>{sample.threat_level}</span>
            </div>
            <p>{sample.story}</p>
            <button type="button" onClick={() => onApplySample(sample.payload)}>Use This Scenario</button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default SampleScenarioPanel;