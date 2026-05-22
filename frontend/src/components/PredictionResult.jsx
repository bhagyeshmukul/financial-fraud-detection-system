// Result panel showing latest model prediction output.
function PredictionResult({ result }) {
  if (!result) return null;

  return (
    <div className="card">
      <h3>Prediction Result</h3>
      <p><strong>Label:</strong> {result.prediction_label}</p>
      <p><strong>Fraud Probability:</strong> {(result.fraud_probability * 100).toFixed(2)}%</p>
      <p>
        <strong>Risk Level:</strong>{" "}
        <span className={`badge ${result.risk_level.toLowerCase()}`}>{result.risk_level}</span>
      </p>
    </div>
  );
}

export default PredictionResult;
