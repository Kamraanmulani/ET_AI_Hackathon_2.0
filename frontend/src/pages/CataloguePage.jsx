// CataloguePage.jsx — Plant Information Catalogue
// Operational register for Pragyan Chemical Plant.
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchCatalogueDocuments } from '../api';
import { ChevronRight, FileText, Settings, AlertTriangle, MessageSquare, Clipboard, File, Box } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const TYPE_ICONS = {
  drawings: <Settings className="w-4 h-4" />,
  maintenance: <Settings className="w-4 h-4" />,
  inspections: <Clipboard className="w-4 h-4" />,
  safety_procedures: <FileText className="w-4 h-4" />,
  incidents: <AlertTriangle className="w-4 h-4" />,
  communications: <MessageSquare className="w-4 h-4" />,
  other: <File className="w-4 h-4" />,
};

const READINESS_MAP = {
  ready: { label: 'Ready', cls: 'badge-verified' },
  needs_review: { label: 'Needs review', cls: 'badge-pending' },
  processing: { label: 'Processing', cls: 'badge-processing' },
  attention_needed: { label: 'Attention needed', cls: 'badge-error' },
  available: { label: 'Available', cls: 'badge-neutral' }
};

const FILTER_TABS = [
  { key: 'all', label: 'All records' },
  { key: 'drawings', label: 'Drawings' },
  { key: 'maintenance', label: 'Maintenance' },
  { key: 'inspections', label: 'Inspections' },
  { key: 'safety_procedures', label: 'Safety & procedures' },
  { key: 'incidents', label: 'Incidents' },
  { key: 'communications', label: 'Communications' },
];

function ReadinessBadge({ value }) {
  const entry = READINESS_MAP[value] || { label: value, cls: 'badge-neutral' };
  return <span className={`badge ${entry.cls}`}>{entry.label}</span>;
}

export default function CataloguePage() {
  const [filter, setFilter] = useState('all');
  const navigate = useNavigate();
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['catalogue-documents'],
    queryFn: fetchCatalogueDocuments,
  });

  const docs = data?.documents || [];

  const filtered = docs.filter((d) => filter === 'all' || d.category === filter);

  const drawingsCount = docs.filter((d) => d.category === 'drawings').length;
  const maintenanceCount = docs.filter((d) => d.category === 'maintenance').length;
  const opsSafetyCount = docs.filter((d) => ['safety_procedures', 'incidents', 'communications'].includes(d.category)).length;

  if (isLoading) return <div className="loading">Loading plant information…</div>;
  if (error) return <div className="error-box">Failed to load catalogue: {error.message}</div>;

  return (
    <div>
      <div className="page-header">
        <div className="page-title-row">
          <h1>Plant Information Catalogue</h1>
          <span className="text-muted" style={{ fontSize: 14 }}>
            {docs.length} records available
          </span>
        </div>
        <p className="text-muted" style={{ marginTop: 8 }}>
          Searchable engineering, maintenance, safety, and operating records.
        </p>
      </div>

      <div className="metric-grid" style={{ marginBottom: 20 }}>
        <div className="metric-card">
          <div className="metric-value">{docs.length}</div>
          <div className="metric-label">Records available</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{drawingsCount}</div>
          <div className="metric-label">Engineering drawings</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{maintenanceCount}</div>
          <div className="metric-label">Maintenance records</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{opsSafetyCount}</div>
          <div className="metric-label">Operations & safety records</div>
        </div>
      </div>

      <div className="filter-tabs" style={{ overflowX: 'auto', whiteSpace: 'nowrap', paddingBottom: 4 }}>
        {FILTER_TABS.map((t) => (
          <button
            key={t.key}
            className={`filter-tab${filter === t.key ? ' active' : ''}`}
            onClick={() => setFilter(t.key)}
            aria-pressed={filter === t.key}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="panel" style={{ padding: 0 }}>
        {/* Desktop Table View */}
        <div className="hide-mobile">
          <table className="data-table">
            <thead>
              <tr>
                <th>Record</th>
                <th>Record ID</th>
                <th>Related assets</th>
                <th>Updated</th>
                <th>Readiness</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((doc) => (
                <tr key={doc.record_id} onClick={() => navigate(doc.open_target)} style={{cursor: 'pointer'}}>
                  <td title={doc.display_type}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {TYPE_ICONS[doc.category] || TYPE_ICONS.other}
                      <span className="text-gray-800" style={{ fontSize: 13, fontWeight: 500 }}>
                        {doc.display_type}
                      </span>
                    </div>
                  </td>
                  <td>
                    <code className="mono">{doc.record_id}</code>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {doc.asset_tags.slice(0, 2).map(tag => (
                        <span 
                          key={tag} 
                          className="badge badge-neutral" 
                          style={{ cursor: 'pointer', border: '1px solid #d1d5db' }}
                          onClick={(e) => { e.stopPropagation(); navigate(`/assets/${tag}`); }}
                        >
                          <Box className="w-3 h-3 inline mr-1 opacity-60" />
                          {tag}
                        </span>
                      ))}
                      {doc.asset_tags.length > 2 && (
                        <span className="badge badge-neutral text-xs opacity-70">
                          +{doc.asset_tags.length - 2}
                        </span>
                      )}
                      {doc.asset_tags.length === 0 && <span className="text-muted text-xs">—</span>}
                    </div>
                  </td>
                  <td className="text-muted" style={{ fontSize: 13 }}>
                    {doc.document_date}
                  </td>
                  <td>
                    <ReadinessBadge value={doc.readiness} />
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button 
                      className="icon-button" 
                      onClick={(e) => { e.stopPropagation(); navigate(doc.open_target); }}
                      title="Open Record"
                    >
                      <ChevronRight className="w-5 h-5 text-gray-400 hover:text-gray-700" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Mobile List View */}
        <div className="hide-desktop">
          {filtered.map((doc) => (
            <div 
              key={doc.record_id} 
              className="p-4 border-b border-gray-100 active:bg-gray-50 flex justify-between items-center"
              style={{ padding: '16px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
              onClick={() => navigate(doc.open_target)}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {TYPE_ICONS[doc.category] || TYPE_ICONS.other}
                  <span style={{ fontWeight: 500, color: 'var(--ink)', fontSize: '14px' }}>{doc.display_type}</span>
                </div>
                <code className="mono text-small">{doc.record_id}</code>
                <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                  {doc.asset_tags.slice(0, 2).map(tag => (
                    <span 
                      key={tag} 
                      className="badge badge-neutral"
                      style={{ border: '1px solid var(--border)', padding: '2px 6px', fontSize: '11px' }}
                      onClick={(e) => { e.stopPropagation(); navigate(`/assets/${tag}`); }}
                    >
                      {tag}
                    </span>
                  ))}
                  {doc.asset_tags.length > 2 && (
                    <span className="text-small text-muted">+{doc.asset_tags.length - 2}</span>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '4px' }}>
                  <ReadinessBadge value={doc.readiness} />
                  <span className="text-small text-muted">{doc.document_date}</span>
                </div>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-400" />
            </div>
          ))}
        </div>

        {filtered.length === 0 && (
          <div className="no-evidence" style={{ padding: 40, textAlign: 'center' }}>
            No records match the selected category.
          </div>
        )}
      </div>
    </div>
  );
}
