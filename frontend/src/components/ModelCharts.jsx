// Interactive chart panel for quick visual intuition of model behavior curves.
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

function ModelCharts() {
  // Placeholder points representing a model performance curve shape.
  const points = [
    { x: 0, y: 0 },
    { x: 0.2, y: 0.55 },
    { x: 0.4, y: 0.73 },
    { x: 0.6, y: 0.83 },
    { x: 0.8, y: 0.92 },
    { x: 1, y: 1 },
  ];

  return (
    <div className="card">
      <h3>Model Performance Trend</h3>
      <div className="chart-box">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points}>
            <XAxis dataKey="x" />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="y" stroke="#4f46e5" strokeWidth={3} dot />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="muted">This chart is a visual placeholder and can be replaced with live ROC/PR metrics from backend reports.</p>
    </div>
  );
}

export default ModelCharts;
