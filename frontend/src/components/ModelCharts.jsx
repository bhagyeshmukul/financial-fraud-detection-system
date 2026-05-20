import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

function ModelCharts() {
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
      <h3>ROC-AUC / Precision-Recall Placeholder</h3>
      <div className="chart-box">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points}>
            <XAxis dataKey="x" />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="y" stroke="#1f6feb" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="muted">Confusion Matrix display can be rendered from backend metrics report in production integration.</p>
    </div>
  );
}

export default ModelCharts;
