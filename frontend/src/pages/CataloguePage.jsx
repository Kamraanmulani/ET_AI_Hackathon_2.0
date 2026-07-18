// CataloguePage.jsx — Source Catalogue
// Lists all active documents with type, provenance, extraction state, and hash.
// Distinguishes original source, synthetic-demo, and derived OCR records.
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchDocuments } from '../api';

const PROVENANCE_LABELS = {
  original: { label: 'Original source', cls: 'badge-original' },
  synthetic_demo: { label: 'Synthetic demo data', cls: 'badge-synthetic' },
};

const EXTRACTION_LABELS = {
  ocr_complete: { label: 'OCR complete', cls: 'badge-proposed' },
  pending_review: { label: 'Pending review', cls: 'badge-pending' },
  no_extraction: { label: 'No extraction', cls: 'badge-error' },
  pending: { label: 'Pending', cls: 'badge-pending' },
  verified: { label: 'Verified', cls: 'badge-verified' },
};

function Badge({ value, map, fallback = 'badge-pending' }) {
  const entry = map[value] || { label: value || '—', cls: fallback };
  return <span className={`badge ${entry.cls}`}>{entry.label}</span>;
}

const TYPE_ICONS = {
  pid_drawing: '📐',
  work_order_pdf: '📋',
  sop: '📄',
  inspection: '🔍',
  incident: '⚠️',
  email: '✉️',
};

export default function CataloguePage() {
  const [filter, setFilter] = useState('all');
  const { data, isLoading, error } = useQuery({
    queryKey: ['documents'],
    queryFn: fetchDocuments,
  });

  const docs = data?.documents || [];

  const filtered = docs.filter((d) => {
    if (filter === 'original') return d.provenance === 'original';
    if (filter === 'synthetic') return d.provenance === 'synthetic_demo';
    return true;
  });

  const origCount = docs.filter((d) => d.provenance === 'original').length;
  const synCount = docs.filter((d) => d.provenance === 'synthetic_demo').length;

  if (isLoading) return <div className="loading">Loading source catalogue…</div>;
  if (error) return <div className="error-box">Failed to load documents: {error.message}</div>;

  return (
    <div>
      <div className="page-header">
        <div className="page-title-row">
          <h1>Source Catalogue</h1>
          <span className="text-muted" style={{ fontSize: 14 }}>
            {docs.length} active documents
          </span>
        </div>
      </div>

      <div className="metric-grid" style={{ marginBottom: 20 }}>
        <div className="metric-card">
          <div className="metric-value">{docs.length}</div>
          <div className="metric-label">Total documents</div>
        </div>
        <div className="metric-card">
          <div className="metric-value" style={{ color: 'var(--green)' }}>{origCount}</div>
          <div className="metric-label">Original sources</div>
        </div>
        <div className="metric-card">
          <div className="metric-value" style={{ color: 'var(--amber)' }}>{synCount}</div>
          <div className="metric-label">Synthetic demo</div>
        </div>
      </div>

      <div className="filter-tabs">
        {[
          { key: 'all', label: `All (${docs.length})` },
          { key: 'original', label: `Original (${origCount})` },
          { key: 'synthetic', label: `Synthetic demo (${synCount})` },
        ].map((t) => (
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
        <table className="data-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Source ID</th>
              <th>Provenance</th>
              <th>Extraction</th>
              <th>SHA-256 (first 16)</th>
              <th>Pages / Size</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((doc) => (
              <tr key={doc.source_id}>
                <td title={doc.document_type}>
                  {TYPE_ICONS[doc.document_type] || '📁'}
                  <span className="text-muted" style={{ marginLeft: 6, fontSize: 12 }}>
                    {doc.document_type?.replace(/_/g, ' ')}
                  </span>
                </td>
                <td>
                  <code className="mono">{doc.source_id}</code>
                </td>
                <td>
                  <Badge value={doc.provenance} map={PROVENANCE_LABELS} />
                </td>
                <td>
                  <Badge
                    value={doc.extraction_state}
                    map={EXTRACTION_LABELS}
                  />
                </td>
                <td>
                  <code className="mono text-muted">
                    {doc.sha256 ? doc.sha256.slice(0, 16) + '…' : '—'}
                  </code>
                </td>
                <td className="text-muted" style={{ fontSize: 12 }}>
                  {doc.page_count
                    ? `${doc.page_count} page${doc.page_count > 1 ? 's' : ''}`
                    : doc.image_width
                    ? `${doc.image_width}×${doc.image_height}px`
                    : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="no-evidence">No documents match the current filter.</div>
        )}
      </div>

      <p className="text-muted text-small" style={{ marginTop: 12 }}>
        Active corpus: 5 Pragyan P&amp;IDs + 1 scanned Maintenance Records PDF (original sources).
        Synthetic demo documents are visibly labelled and not treated as plant-authoritative records.
      </p>
    </div>
  );
}
