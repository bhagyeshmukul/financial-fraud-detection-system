/** Draw backend-computed PR, ROC and calibration curves without recalculating evidence in the UI. */
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
/** Reuse one bounded 0..1 chart layout; diagonal lines provide ROC/calibration references. */
function Curve({ title, points, xLabel, yLabel, diagonal = false }) {
  return (
    <div className="card">
      <h3>{title}</h3>
      {!points?.length ? (
        <p>Unavailable for this evaluation.</p>
      ) : (
        <div className="chart-box">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={points}
              margin={{ top: 15, right: 20, bottom: 20, left: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#dce3e9" />
              <XAxis
                dataKey="x"
                type="number"
                domain={[0, 1]}
                label={{ value: xLabel, position: "insideBottom", offset: -10 }}
              />
              <YAxis
                type="number"
                domain={[0, 1]}
                label={{ value: yLabel, angle: -90, position: "insideLeft" }}
              />
              <Tooltip formatter={(value) => Number(value).toFixed(4)} />
              {diagonal && (
                <ReferenceLine
                  segment={[
                    { x: 0, y: 0 },
                    { x: 1, y: 1 },
                  ]}
                  stroke="#a8b3bf"
                  strokeDasharray="4 4"
                />
              )}
              <Line
                type="linear"
                dataKey="y"
                stroke="#087f75"
                dot={false}
                strokeWidth={2}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
/** Map each saved curve to its own correctly labelled axes. */
export default function PerformanceCharts({ metrics }) {
  return (
    <div className="chart-grid">
      <Curve
        title="Precision–recall curve"
        points={metrics?.pr_curve}
        xLabel="Recall"
        yLabel="Precision"
      />
      <Curve
        title="ROC curve"
        points={metrics?.roc_curve}
        xLabel="False positive rate"
        yLabel="True positive rate"
        diagonal
      />
      <Curve
        title="Probability calibration"
        points={metrics?.calibration_curve}
        xLabel="Mean predicted probability"
        yLabel="Observed fraud rate"
        diagonal
      />
    </div>
  );
}
