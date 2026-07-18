import { useQuery } from '@tanstack/react-query'
import { FileText } from 'lucide-react'

async function fetchDocuments() {
  const res = await fetch('/api/v1/documents')
  if (!res.ok) throw new Error('Failed to fetch documents')
  return res.json()
}

function ProvenanceBadge({ provenance }) {
  if (provenance === 'synthetic_demo')
    return <span className="badge badge-synthetic">Synthetic demo data</span>
  return <span className="badge badge-original">Original source</span>
}

function ExtractionBadge({ state }) {
  const map = {
    registry_seeded: { cls: 'badge-verified', label: 'Registry seeded' },
    pending_ocr:     { cls: 'badge-pending',  label: 'Pending OCR' },
    completed:       { cls: 'badge-verified', label: 'Completed' },
    pending:         { cls: 'badge-pending',  label: 'Pending' },
  }
  const { cls, label } = map[state] || { cls: 'badge-pending', label: state }
  return <span className={`badge ${cls}`}>{label}</span>
}

export default function DocumentsPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['documents'],
    queryFn: fetchDocuments,
  })

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
        <FileText size={20} />
        <h1>Source Documents</h1>
      </div>
      <p className="text-muted" style={{ marginBottom: 24 }}>
        Active corpus — {data ? data.total : '…'} documents. Original P&amp;ID images and
        scanned work-order PDF are immutable sources. All other records are synthetic demo data.
      </p>

      {isLoading && <p className="loading">Loading documents…</p>}
      {isError && (
        <div className="error-box">
          Cannot load documents. Is the backend running and the corpus imported?
        </div>
      )}

      {data && (
        <div className="panel" style={{ padding: 0, overflow: 'hidden' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Source ID</th>
                <th>Type</th>
                <th>Provenance</th>
                <th>Extraction State</th>
                <th>SHA-256 (first 16)</th>
                <th>Pages / Size</th>
              </tr>
            </thead>
            <tbody>
              {data.documents.map(doc => (
                <tr key={doc.source_id}>
                  <td className="mono" style={{ color: 'var(--blue)', maxWidth: 220 }}>
                    <span className="truncate" title={doc.source_id}>{doc.source_id}</span>
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                    {doc.document_type}
                  </td>
                  <td><ProvenanceBadge provenance={doc.provenance} /></td>
                  <td><ExtractionBadge state={doc.extraction_state} /></td>
                  <td className="mono text-small text-muted">
                    {doc.sha256 ? doc.sha256.slice(0, 16) + '…' : '—'}
                  </td>
                  <td className="text-small text-muted">
                    {doc.page_count ? `${doc.page_count} pages` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
