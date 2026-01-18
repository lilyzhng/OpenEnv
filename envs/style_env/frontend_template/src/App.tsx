import Dashboard from "./pages/Dashboard";
import Home from "./pages/Home";

/**
 * Root application component.
 * This file should generally not be modified during evaluation tasks.
 * Evaluation pages are added to src/pages/ and rendered via routing or direct import.
 */
function App() {
  // Simple router for demo purposes
  const path = window.location.pathname;

  if (path === "/consumer") {
    return <Home />;
  }

  return (
    <div>
      <div className="fixed bottom-4 right-4 z-50 flex gap-2">
        <a
          href="/"
          className="rounded-full bg-gray-900 px-4 py-2 text-sm font-medium text-white shadow-lg hover:bg-gray-800"
        >
          Enterprise Demo
        </a>
        <a
          href="/consumer"
          className="rounded-full bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-lg hover:bg-indigo-700"
        >
          Consumer Demo
        </a>
      </div>
      <Dashboard />
    </div>
  );
}

export default App;
