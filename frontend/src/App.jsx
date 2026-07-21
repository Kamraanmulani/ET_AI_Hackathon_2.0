import { Routes, Route, NavLink } from 'react-router-dom';
import { Bot, Box, ClipboardCheck, FolderSearch, LayoutDashboard, Network, Search, Workflow } from 'lucide-react';
import OverviewPage from './pages/OverviewPage';
import CataloguePage from './pages/CataloguePage';
import DrawingsPage from './pages/DrawingsPage';
import AssetsPage from './pages/AssetsPage';
import Asset360Page from './pages/Asset360Page';
import ReviewPage from './pages/ReviewPage';
import QueryPage from './pages/QueryPage';
import CopilotPage from './pages/CopilotPage';
import DocumentDetailPage from './pages/DocumentDetailPage';
import LandingPage from './pages/LandingPage';

const navItems = [
  { to: '/copilot', label: 'Copilot', icon: Bot },
  { to: '/drawings', label: 'P&ID Explorer', icon: Workflow },
  { to: '/catalogue', label: 'Source Catalogue', icon: FolderSearch },
  { to: '/assets', label: 'Assets', icon: Box },
  { to: '/review', label: 'Review Queue', icon: ClipboardCheck },
  { to: '/query', label: 'Query', icon: Search },
  { to: '/overview', label: 'Overview', icon: LayoutDashboard, exact: true },
];

function Rail() {
  return (
    <nav className="rail" aria-label="Primary navigation">
      <div className="rail-section">Workspace</div>
      {navItems.map(({ to, label, icon: Icon, exact }) => (
        <NavLink key={to} to={to} end={exact} className={({ isActive }) => `rail-link${isActive ? ' active' : ''}`}>
          <Icon size={17} aria-hidden="true" />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

function Topbar() {
  return (
    <header className="topbar" role="banner">
      <NavLink to="/" className="topbar-brand" aria-label="Pragyan Plant Intelligence home">
        <Network size={17} aria-hidden="true" />
        <span>Pragyan Plant Intelligence</span>
      </NavLink>
      <span className="text-muted text-small" style={{ marginLeft: 16 }}>Source-grounded asset knowledge workspace</span>
    </header>
  );
}

function WorkspaceShell() {
  return (
    <div className="app-shell">
      <Topbar />
      <Rail />
      <main className="main" id="main-content" tabIndex={-1}>
        <Routes>
          <Route path="/overview" element={<OverviewPage />} />
          <Route path="/catalogue" element={<CataloguePage />} />
          <Route path="/drawings" element={<DrawingsPage />} />
          <Route path="/assets" element={<AssetsPage />} />
          <Route path="/assets/:tag" element={<Asset360Page />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="/query" element={<QueryPage />} />
          <Route path="/copilot" element={<CopilotPage />} />
          <Route path="/documents/:documentId" element={<DocumentDetailPage />} />
          <Route path="*" element={<div style={{ padding: 32 }}><h2>Page not found</h2><p className="text-muted">Use the navigation on the left to explore the workspace.</p></div>} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/*" element={<WorkspaceShell />} />
    </Routes>
  );
}
