import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Tag, ChevronRight } from 'lucide-react'

async function fetchAssets() {
  const res = await fetch('/api/v1/assets')
  if (!res.ok) throw new Error('Failed to fetch assets')
  return res.json()
}

async function fetchAsset(tag) {
  const res = await fetch(`/api/v1/assets/${encodeURIComponent(tag)}`)
  if (!res.ok) throw new Error('Asset not found')
  return res.json()
}

const AREA_LABELS = {
  reactor:            'Reactor (PCP-PID-001)',
  distillation:       'Distillation (PCP-PID-002)',
  storage:            'Storage (PCP-PID-003)',
  utilities:          'Utilities / Boiler (PCP-PID-004)',
  effluent_treatment: 'Effluent Treatment (PCP-PID-005)',
}

function StateBadge({ state }) {
  return (
    <span className={`badge ${state === 'verified' ? 'badge-verified' : 'badge-proposed'}`}>
      {state === 'verified' ? '✓ Verified' : '~ AI proposed'}
    </span>
  )
}

function AssetDetail({ tag, onClose }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['asset', tag],
    queryFn: () => fetchAsset(tag),
  })

  return (
    <div className="panel" style={{ borderLeft: '3px solid var(--teal)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h3 className="tag" style={{ fontSize: 16, color: 'var(--teal)' }}>{tag}</h3>
        <button
          onClick={onClose}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
          aria-label="Close asset detail"
        >
          ✕
        </button>
      </div>

      {isLoading && <p className="loading">Loading…</p>}
      {isError && <div className="error-box">Could not load asset detail.</div>}

      {data && (
        <>
          <table className="data-table" style={{ marginBottom: 16 }}>
            <tbody>
              <tr><td><strong>Tag</strong></td><td className="mono">{data.asset.tag}</td></tr>
              <tr><td><strong>Type</strong></td><td>{data.asset.asset_type}</td></tr>
              <tr><td><strong>Area</strong></td><td>{AREA_LABELS[data.asset.area] || data.asset.area}</td></tr>
              <tr><td><strong>Drawing</strong></td><td className="mono">{data.asset.drawing_id || '—'}</td></tr>
              <tr><td><strong>Source ID</strong></td><td className="mono">{data.asset.source_id}</td></tr>
              <tr><td><strong>State</strong></td><td><StateBadge state={data.asset.state} /></td></tr>
            </tbody>
          </table>

          <h3 style={{ marginBottom: 8 }}>Process Relationships</h3>
          {data.relationships.length === 0
            ? <p className="text-muted text-small">No relationships recorded.</p>
            : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>From</th>
                    <th>Relationship</th>
                    <th>To</th>
                    <th>Source</th>
                    <th>State</th>
                  </tr>
                </thead>
                <tbody>
                  {data.relationships.map((r, i) => (
                    <tr key={i}>
                      <td className="mono">{r.from_tag}</td>
                      <td style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{r.relationship_type}</td>
                      <td className="mono">{r.to_tag}</td>
                      <td className="mono text-small text-muted">{r.source_id}</td>
                      <td><StateBadge state={r.state} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )
          }
        </>
      )}
    </div>
  )
}

// Group assets by area
function groupByArea(assets) {
  const groups = {}
  for (const a of assets) {
    const area = a.area || 'unknown'
    if (!groups[area]) groups[area] = []
    groups[area].push(a)
  }
  return groups
}

export default function AssetsPage() {
  const [selectedTag, setSelectedTag] = useState(null)
  const { data, isLoading, isError } = useQuery({
    queryKey: ['assets'],
    queryFn: fetchAssets,
  })

  const grouped = data ? groupByArea(data.assets) : {}
  const areas = Object.keys(AREA_LABELS)

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
        <Tag size={20} />
        <h1>P&amp;ID Asset Registry</h1>
      </div>
      <p className="text-muted" style={{ marginBottom: 24 }}>
        {data ? data.total : '…'} verified assets across 5 process areas.
        All tags are sourced from manual review of the five Pragyan P&amp;IDs.
      </p>

      {isLoading && <p className="loading">Loading assets…</p>}
      {isError && <div className="error-box">Cannot load assets. Is the backend running?</div>}

      {selectedTag && (
        <AssetDetail tag={selectedTag} onClose={() => setSelectedTag(null)} />
      )}

      {data && areas.map(area => {
        const areaAssets = grouped[area] || []
        if (areaAssets.length === 0) return null
        return (
          <div key={area} className="panel">
            <div className="panel-header">
              <h3>{AREA_LABELS[area]}</h3>
              <span className="text-muted text-small">({areaAssets.length} assets)</span>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Tag</th>
                  <th>Type</th>
                  <th>Drawing</th>
                  <th>State</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {areaAssets.map(a => (
                  <tr
                    key={a.tag}
                    style={{ cursor: 'pointer' }}
                    onClick={() => setSelectedTag(a.tag)}
                  >
                    <td>
                      <span className="tag" style={{ color: 'var(--teal)' }}>{a.tag}</span>
                    </td>
                    <td className="text-small text-muted">{a.asset_type}</td>
                    <td className="mono text-small">{a.drawing_id || '—'}</td>
                    <td><StateBadge state={a.state} /></td>
                    <td><ChevronRight size={14} color="var(--text-muted)" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      })}
    </div>
  )
}
