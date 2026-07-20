// App.jsx — Pragyan Plant Intelligence SPA routing and navigation.
// Phase 4: full operational workspace with P&ID Explorer, Asset 360,
// interactive Review Queue, Source Catalogue, and Grounded Query.
// RAG Phase: adds Expert Knowledge Copilot route.
import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom';
import OverviewPage from './pages/OverviewPage';
import CataloguePage from './pages/CataloguePage';
import DrawingsPage from './pages/DrawingsPage';
import AssetsPage from './pages/AssetsPage';
import Asset360Page from './pages/Asset360Page';
import ReviewPage from './pages/ReviewPage';
import QueryPage from './pages/QueryPage';
import CopilotPage from './pages/CopilotPage';
import DocumentDetailPage from './pages/DocumentDetailPage';

function Rail() {
  const location = useLocation();
  const navItems = [
    { to: '/copilot', label: 'Copilot', icon: '⚗️' },
    { to: '/drawings', label: 'P&ID Explorer', icon: '📐' },
    { to: '/catalogue', label: 'Source Catalogue', icon: '🗂️' },
    { to: '/assets', label: 'Assets', icon: '🏭' },
    { to: '/review', label: 'Review Queue', icon: '✅' },
    { to: '/query', label: 'Query', icon: '🔍' },
    { to: '/', label: 'Overview', icon: '📊', exact: true },
  ];
  return (
    <nav className="rail" aria-label="Primary navigation">
      <div className="rail-section">Workspace</div>
      {navItems.map(({ to, label, icon, exact }) => (
        <NavLink
          key={to}
          to={to}
          end={exact}
          className={({ isActive }) => `rail-link${isActive ? ' active' : ''}`}
          aria-label={label}
        >
          <span aria-hidden="true">{icon}</span>
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
function Topbar() {
  return (
    <header className="topbar" role="banner">
      <a href="/" className="topbar-brand" aria-label="Pragyan Plant Intelligence home">
        <span aria-hidden="true">⚗️</span>
        <span>Pragyan Plant Intelligence</span>
      </a>
      <span className="text-muted text-small" style={{ marginLeft: 16 }}>
        Source-grounded asset knowledge workspace
      </span>
      <div style={{ marginLeft: 'auto' }}>
        <span
          className="badge badge-synthetic"
          title="Prototype — read-only decision support; not a plant control system"
        >
          Prototype · Read-only
        </span>
      </div>
    </header>
  );
}
function AppShell() {
  return (
    <div className="app-shell">
      <Topbar />
      <Rail />
      <main className="main" id="main-content" tabIndex={-1}>
        <Routes>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/catalogue" element={<CataloguePage />} />
          <Route path="/drawings" element={<DrawingsPage />} />
          <Route path="/assets" element={<AssetsPage />} />
          <Route path="/assets/:tag" element={<Asset360Page />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="/query" element={<QueryPage />} />
          <Route path="/copilot" element={<CopilotPage />} />
          <Route path="/documents/:documentId" element={<DocumentDetailPage />} />
          <Route
            path="*"
            element={
              <div style={{ padding: 32 }}>
                <h2>Page not found</h2>
                <p className="text-muted">Use the navigation on the left to explore the workspace.</p>
              </div>
            }
          />
        </Routes>
      </main>
    </div>
  );
}
export default AppShell;
