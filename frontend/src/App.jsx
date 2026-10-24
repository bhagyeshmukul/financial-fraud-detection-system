// Root app component that renders the fraud dashboard page.
import FraudDashboard from "./pages/FraudDashboard";

/** Keep the root small; the page component owns feature-level behavior. */
function App() {
  return <FraudDashboard />;
}

export default App;
