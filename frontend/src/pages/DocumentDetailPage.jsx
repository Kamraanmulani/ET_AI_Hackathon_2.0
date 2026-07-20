import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchDocument, fetchDocumentEntities } from '../api';
import { ChevronLeft, Box, CheckCircle, AlertTriangle } from 'lucide-react';

const READINESS_MAP = {
  ready: { label: 'Ready', cls: 'badge-verified' },
  needs_review: { label: 'Needs review', cls: 'badge-pending' },
  processing: { label: 'Processing', cls: 'badge-processing' },
  attention_needed: { label: 'Attention needed', cls: 'badge-error' },
  available: { label: 'Available', cls: 'badge-neutral' }
};

function ReadinessBadge({ value }) {
  const entry = READINESS_MAP[value] || { label: value, cls: 'badge-neutral' };
  return <span className={`badge ${entry.cls}`}>{entry.label}</span>;
}

export default function DocumentDetailPage() {
  const { documentId } = useParams();
  const navigate = useNavigate();

  const { data: doc, isLoading, error } = useQuery({
    queryKey: ['document', documentId],
    queryFn: () => fetchDocument(documentId),
  });

  const { data: entitiesData } = useQuery({
    queryKey: ['document-entities', documentId],
    queryFn: () => fetchDocumentEntities(documentId),
    enabled: !!doc,
  });

  if (isLoading) return <div className="loading">Loading record details…</div>;
  
  if (error) {
    return (
      <div>
        <button className="btn btn-outline" onClick={() => navigate('/catalogue')} style={{ marginBottom: 20 }}>
          <ChevronLeft className="w-4 h-4 inline mr-1" /> Back to Catalogue
        </button>
        <div className="error-box">
          Document not found or error loading data.
        </div>
      </div>
    );
  }

  const entities = entitiesData?.entities || [];
  
  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <button className="link-btn" onClick={() => navigate('/catalogue')} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <ChevronLeft className="w-4 h-4" /> Back to Catalogue
        </button>
      </div>

      <div className="page-header">
        <div className="page-title-row">
          <h1>{doc.display_type}</h1>
          <ReadinessBadge value={doc.readiness} />
        </div>
      </div>

      <div className="panel" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div>
          <h3 className="text-secondary">Record ID</h3>
          <code className="mono">{doc.record_id}</code>
        </div>
        
        <div>
          <h3 className="text-secondary">Record Date</h3>
          <div className="text-muted">{doc.document_date}</div>
        </div>

        <div>
          <h3 className="text-secondary">Related Assets</h3>
          {doc.asset_tags?.length > 0 ? (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 4 }}>
              {doc.asset_tags.map(tag => (
                <span 
                  key={tag} 
                  className="badge badge-neutral" 
                  style={{ cursor: 'pointer', border: '1px solid #d1d5db', padding: '4px 8px' }}
                  onClick={() => navigate(`/assets/${tag}`)}
                >
                  <Box className="w-4 h-4 inline mr-2 opacity-60" />
                  {tag}
                </span>
              ))}
            </div>
          ) : (
            <div className="text-muted">—</div>
          )}
        </div>
        
        {entities.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h3 className="text-secondary">Extracted Entities</h3>
            <table className="data-table" style={{ marginTop: 8 }}>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Value</th>
                  <th>State</th>
                </tr>
              </thead>
              <tbody>
                {entities.map((ent, i) => (
                  <tr key={i}>
                    <td><code className="mono text-muted">{ent.entity_type}</code></td>
                    <td>{ent.normalized_value || ent.text}</td>
                    <td>
                      {ent.resolution?.state === 'verified' ? (
                        <span style={{ color: 'var(--green)', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                          <CheckCircle className="w-3 h-3" /> Verified
                        </span>
                      ) : (
                        <span style={{ color: 'var(--amber)', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                          <AlertTriangle className="w-3 h-3" /> {ent.resolution?.state || 'pending'}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
