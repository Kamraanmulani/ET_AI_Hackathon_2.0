// Asset360Page.jsx — Asset 360 Evidence View
// Shows canonical asset info, P&ID relationships, work-order evidence,
// OCR citations, and audit timeline.
// All evidence is labelled with source, page, region, and review state.
// No live values, alarms, calibration results, or risk scores are shown.
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchAssetEvidence, fetchAssetAudit, ocrPageUrl } from '../api';
import AssetEvidenceGraph from '../components/AssetEvidenceGraph';

const STATE_BADGE = {
  verified: 'badge-verified',
  pending_review: 'badge-pending',
  AI_proposed: 'badge-proposed',
  'AI proposed': 'badge-proposed',
  rejected: 'badge-error',
  corrected: 'badge-proposed',
  unreadable: 'badge-error',
};

function StateBadge({ state }) {
  const cls = STATE_BADGE[state] || 'badge-pending';
  return <span className={`badge ${cls}`}>{state?.replace(/_/g, ' ') || 'unknown'}</span>;
}

function ConfBar({ value }) {
  if (!value) return null;
  const pct = Math.round(value * 100);
  return (
    <span title={`Confidence: ${pct}%`}>
      <span className="conf-bar" style={{ width: `${Math.max(pct, 10)}px` }} />
      <span className="conf-value" style={{ marginLeft: 4 }}>{pct}%</span>
    </span>
  );
}

function RelationshipsPanel({ relationships }) {
  if (!relationships?.length) {
    return <div className="no-evidence">No verified P&ID relationships in registry.</div>;
  }
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>From</th>
          <th>Relation</th>
          <th>To</th>
          <th>State</th>
          <th>Source</th>
        </tr>
      </thead>
      <tbody>
        {relationships.map((r, i) => (
          <tr key={i}>
            <td><code className="mono">{r.from_tag}</code></td>
            <td className="text-muted">{r.relation_type?.replace(/_/g, ' ')}</td>
            <td><code className="mono">{r.to_tag}</code></td>
            <td><StateBadge state={r.state} /></td>
            <td className="text-muted text-small"><code className="mono">{r.source_id}</code></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function WorkOrderLinks({ links }) {
  if (!links?.length) {
    return (
      <div className="no-evidence">
        No linked evidence — no work-order records linked to this asset in the active corpus.
      </div>
    );
  }
  return (
    <div>
      {links.map((link, i) => (
        <div key={link.link_id || i} className="evidence-row">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <code className="mono" style={{ fontSize: 12 }}>{link.asset_tag}</code>
            <StateBadge state={link.review_state || link.state} />
          </div>
          {link.ocr_region && (
            <div className="evidence-text">{link.ocr_region.text}</div>
          )}
          <div className="evidence-meta">
            <span>Source: <code className="mono">{link.source_id}</code></span>
            {link.source_page && <span>· Page {link.source_page}</span>}
            {link.source_region_id && (
              <span>· Region <code className="mono">{link.source_region_id}</code></span>
            )}
            {link.ocr_region?.confidence && (
              <ConfBar value={link.ocr_region.confidence} />
            )}
            {link.source_page && (
              <a
                href={ocrPageUrl(link.source_page)}
                target="_blank"
                rel="noreferrer"
                className="link-btn"
                style={{ marginLeft: 4 }}
              >
                Open source page ↗
              </a>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function OcrRegionsPanel({ regions }) {
  if (!regions?.length) {
    return <div className="no-evidence">No OCR text regions mention this asset tag.</div>;
  }
  return (
    <div>
      {regions.slice(0, 10).map((r, i) => (
        <div key={r.region_id || i} className="evidence-row">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <code className="mono text-muted" style={{ fontSize: 11 }}>{r.region_id}</code>
            <StateBadge state={r.review_state || r.state} />
            <ConfBar value={r.confidence} />
          </div>
          <div className="evidence-text">{r.text}</div>
          <div className="evidence-meta">
            <span>Page {r.source_page}</span>
            {r.source_page && (
              <a
                href={ocrPageUrl(r.source_page)}
                target="_blank"
                rel="noreferrer"
                className="link-btn"
              >
                Open page ↗
              </a>
            )}
          </div>
        </div>
      ))}
      {regions.length > 10 && (
        <div className="text-muted text-small" style={{ paddingTop: 8 }}>
          Showing 10 of {regions.length} matching regions.
        </div>
      )}
    </div>
  );
}

function AuditTimeline({ events }) {
  if (!events?.length) {
    return <div className="no-evidence">No audit events for this asset yet.</div>;
  }
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Timestamp</th>
          <th>Event</th>
          <th>Actor</th>
          <th>Detail</th>
        </tr>
      </thead>
      <tbody>
        {events.map((ev, i) => (
          <tr key={i}>
            <td className="mono text-muted" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>
              {ev.timestamp ? new Date(ev.timestamp).toLocaleString() : '—'}
            </td>
            <td>{ev.event_type?.replace(/_/g, ' ')}</td>
            <td className="text-muted">{ev.actor || '—'}</td>
            <td className="text-muted text-small">
              {ev.detail?.decision && <span>Decision: <strong>{ev.detail.decision}</strong></span>}
              {ev.detail?.new_state && <span> → {ev.detail.new_state}</span>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function Asset360Page() {
  const { tag } = useParams();
  const tagUpper = tag?.toUpperCase();

  const { data: evidenceData, isLoading, error } = useQuery({
    queryKey: ['asset-evidence', tagUpper],
    queryFn: () => fetchAssetEvidence(tagUpper),
    enabled: !!tagUpper,
  });

  const { data: auditData } = useQuery({
    queryKey: ['asset-audit', tagUpper],
    queryFn: () => fetchAssetAudit(tagUpper),
    enabled: !!tagUpper,
  });

  if (isLoading) return <div className="loading">Loading Asset 360 for {tagUpper}…</div>;
  if (error) return (
    <div>
      <div className="error-box">
        Asset <code className="mono">{tagUpper}</code> not found in the P&amp;ID registry.
        <br />{error.message}
      </div>
      <Link to="/drawings" className="link-btn" style={{ marginTop: 12, display: 'inline-block' }}>
        ← Back to P&amp;ID Explorer
      </Link>
    </div>
  );

  const { asset, relationships, work_order_links, ocr_regions, evidence_summary } = evidenceData || {};

  return (
    <div>
      {/* Header */}
      <div className="asset360-header">
        <div>
          <div className="asset360-tag">{asset?.tag}</div>
          <div className="asset360-meta">
            {asset?.type?.replace(/_/g, ' ')} · {asset?.area?.replace(/_/g, ' ')}
          </div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 10, alignItems: 'center' }}>
          <span className="badge badge-verified">
            {asset?.state || 'verified'}
          </span>
          {asset?.source_id && (
            <code className="mono text-muted" style={{ fontSize: 12 }}>{asset.source_id}</code>
          )}
          <Link to={`/copilot?asset=${asset?.tag || tagUpper}`} className="btn btn-primary" style={{ textDecoration: 'none', background: 'var(--teal)', color: '#fff' }}>
            Ask Copilot ⚗️
          </Link>
          <Link to="/drawings" className="btn btn-outline" style={{ textDecoration: 'none' }}>
            View in P&amp;ID Explorer
          </Link>
        </div>
      </div>

      {/* Evidence summary */}
      {evidence_summary && (
        <div className="metric-grid" style={{ marginBottom: 20 }}>
          <div className="metric-card">
            <div className="metric-value">{evidence_summary.relationship_count}</div>
            <div className="metric-label">P&amp;ID relationships</div>
          </div>
          <div className="metric-card">
            <div className="metric-value" style={{ color: 'var(--amber)' }}>
              {evidence_summary.link_count}
            </div>
            <div className="metric-label">Work-order links</div>
          </div>
          <div className="metric-card">
            <div className="metric-value" style={{ color: 'var(--green)' }}>
              {evidence_summary.verified_links}
            </div>
            <div className="metric-label">Verified links</div>
          </div>
          <div className="metric-card">
            <div className="metric-value" style={{ color: 'var(--violet)' }}>
              {evidence_summary.pending_links}
            </div>
            <div className="metric-label">Pending review</div>
          </div>
        </div>
      )}

      {/* Asset Evidence Graph */}
      <div className="panel" style={{ marginTop: 0, padding: 0, border: 'none', background: 'transparent' }}>
        <AssetEvidenceGraph tag={tagUpper} />
      </div>

      {/* Evidence panels */}
      <div className="evidence-grid">
        <div className="panel">
          <div className="panel-header">
            <h3>P&amp;ID Relationships</h3>
            <span className="badge badge-verified" style={{ marginLeft: 8 }}>Verified</span>
          </div>
          <RelationshipsPanel relationships={relationships} />
        </div>

        <div className="panel">
          <div className="panel-header">
            <h3>Work-Order Evidence</h3>
            <span className="badge badge-proposed" style={{ marginLeft: 8 }}>AI proposed</span>
          </div>
          <p className="text-muted text-small" style={{ marginBottom: 10 }}>
            Linked OCR extractions — pending human review. No claim is verified automatically.
          </p>
          <WorkOrderLinks links={work_order_links} />
        </div>
      </div>

      <div className="panel" style={{ marginTop: 0 }}>
        <div className="panel-header">
          <h3>OCR Text Mentions</h3>
          <span className="badge badge-proposed" style={{ marginLeft: 8 }}>AI proposed</span>
        </div>
        <p className="text-muted text-small" style={{ marginBottom: 10 }}>
          OCR regions containing this asset tag. All pending human review.
        </p>
        <OcrRegionsPanel regions={ocr_regions} />
      </div>

      <div className="panel" style={{ marginTop: 0 }}>
        <div className="panel-header">
          <h3>Audit Timeline</h3>
        </div>
        <AuditTimeline events={auditData?.events} />
      </div>
    </div>
  );
}
