// QueryPage.jsx — Grounded Query Workspace
// Search the active corpus by keyword.
// Returns cited OCR evidence with source_id, page, region, review_state.
// Returns "insufficient evidence" when nothing matches.
// No LLM calls, no Qdrant, no external data.
import { useState } from 'react';
import { fetchQuery } from '../api';

const STATE_BADGE = {
  pending_review: { cls: 'badge-pending', label: 'Pending review' },
  verified: { cls: 'badge-verified', label: 'Verified' },
  'AI proposed': { cls: 'badge-proposed', label: 'AI proposed' },
  rejected: { cls: 'badge-error', label: 'Rejected' },
};

function StateBadge({ state }) {
  const entry = STATE_BADGE[state] || { cls: 'badge-pending', label: state || 'unknown' };
  return <span className={`badge ${entry.cls}`}>{entry.label}</span>;
}

function CitationCard({ citation, index }) {
  return (
    <div className="citation-card">
      <div className="citation-header">
        <span className="text-muted text-small" style={{ fontWeight: 700 }}>#{index + 1}</span>
        <span className="citation-source">
          {citation.source_id}
          {citation.source_page && ` · Page ${citation.source_page}`}
          {citation.source_region_id && (
            <> · <code className="mono">{citation.source_region_id}</code></>
          )}
        </span>
        <StateBadge state={citation.review_state || citation.state} />
        {citation.confidence && (
          <span className="conf-value">
            {Math.round(citation.confidence * 100)}% conf.
          </span>
        )}
      </div>

      {citation.text && (
        <div className="citation-text">{citation.text}</div>
      )}

      {citation.asset_tag_mentions?.length > 0 && (
        <div className="citation-tags">
          {citation.asset_tag_mentions.map((tag) => (
            <a
              key={tag}
              href={`/assets/${tag}`}
              className="citation-tag-chip"
              title={`Open Asset 360 for ${tag}`}
            >
              {tag}
            </a>
          ))}
        </div>
      )}

      {citation.page_image_url && (
        <div style={{ marginTop: 8 }}>
          <a
            href={citation.page_image_url}
            target="_blank"
            rel="noreferrer"
            className="link-btn"
          >
            Open source page ↗
          </a>
        </div>
      )}
    </div>
  );
}

export default function QueryPage() {
  const [query, setQuery] = useState('');
  const [assetTag, setAssetTag] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim() || query.trim().length < 2) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await fetchQuery(query.trim(), assetTag.trim() || undefined);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-title-row">
          <h1>Grounded Query</h1>
        </div>
      </div>
      <p className="text-muted text-small" style={{ marginBottom: 16 }}>
        Search the active corpus for cited evidence. Results show source documents, page numbers,
        and review state. Returns "insufficient evidence" when nothing matches.
        No LLM, no Qdrant — pure source-grounded search.
      </p>

      <form onSubmit={handleSearch}>
        <div className="query-bar">
          <input
            id="query-input"
            className="query-input"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search work-order text… e.g. R-201, bearing, pump overload"
            aria-label="Search query"
            minLength={2}
            required
          />
          <input
            className="query-input"
            type="text"
            value={assetTag}
            onChange={(e) => setAssetTag(e.target.value)}
            placeholder="Asset tag (optional)"
            aria-label="Filter by asset tag"
            style={{ maxWidth: 160 }}
          />
          <button type="submit" className="btn-search" disabled={loading || query.trim().length < 2}>
            {loading ? 'Searching…' : 'Search'}
          </button>
        </div>
      </form>

      {error && (
        <div className="error-box" style={{ marginBottom: 16 }}>
          Search error: {error}
        </div>
      )}

      {result && (
        <div>
          {result.result === 'insufficient_evidence' ? (
            <div className="insufficient-evidence">
              <h3>Insufficient Evidence</h3>
              <p>
                No matching records found in the active corpus for query:{' '}
                <strong>&ldquo;{result.query}&rdquo;</strong>
              </p>
              <p style={{ marginTop: 8 }}>
                {result.message}
              </p>
            </div>
          ) : (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                <h2 style={{ fontSize: 16 }}>
                  {result.citation_count} citation{result.citation_count !== 1 ? 's' : ''} found
                </h2>
                <span className="text-muted text-small">
                  for &ldquo;{result.query}&rdquo;
                  {result.asset_tag ? ` · asset: ${result.asset_tag}` : ''}
                </span>
              </div>

              <div className="panel" style={{ padding: '8px 12px', marginBottom: 16, background: '#FFFBEB' }}>
                <span className="text-muted text-small">
                  ⚠ {result.provenance_note}
                </span>
              </div>

              {result.citations.map((citation, i) => (
                <CitationCard key={citation.source_region_id || i} citation={citation} index={i} />
              ))}
            </div>
          )}
        </div>
      )}

      {!result && !loading && (
        <div className="insufficient-evidence">
          <h3>Enter a search query above</h3>
          <p>
            Search the OCR-extracted text from the scanned Maintenance Records / Work Orders PDF.
            Examples: asset tags (R-201, ETP-601), work-order IDs (WO-2024-0113), symptoms, or technician names.
          </p>
        </div>
      )}
    </div>
  );
}
