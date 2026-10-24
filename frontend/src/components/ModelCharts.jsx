/** Delay the larger chart package until evaluation charts are actually rendered. */
import { lazy, Suspense } from "react";
const Charts = lazy(() => import("./PerformanceCharts"));
/** Provide loading feedback while the separate chart bundle arrives. */
export default function ModelCharts({ metrics }) {
  return (
    <Suspense fallback={<p>Loading evaluation charts…</p>}>
      <Charts metrics={metrics} />
    </Suspense>
  );
}
