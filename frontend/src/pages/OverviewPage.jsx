import { useQuery } from '@tanstack/react-query'
import { CheckCircle, AlertCircle, Database, Activity } from 'lucide-react'

async function fetchHealth() {
  const res = await fetch('/api/v1/health')
  return res.json()
}

async function fetchMetrics() {
  const res = await fetch('/api/v1/metrics')
  if (!res.ok) return null
  return res.json()
}

function StatusIcon({ ok }) {
  return ok
    ? <CheckCircle size={16} color="var(--green)" aria-label="connected" />
    : <AlertCircle size={16} color="var(--red)" aria-label="disconnected" />
}

export default function OverviewPage() {
  const health = useQuery({ queryKey: ['health'], queryFn: fetchHealth, refetchInterval: 10_000 })
  const metrics = useQuery({ queryKey: ['metrics'], queryFn: fetchMetrics })

  const hd = health.data
  const md = metrics.data

  return (
    <div>
      <h1 style={{ marginBottom: 4 }}>Overview</h1>
      <p className="text-muted" style={{ marginBottom: 24 }}>
        Pragyan Plant Intelligence — source-grounded asset knowledge workspace
      </p>

      {/* System health */}
      <div className="panel">
        <div className="panel-header">
          <Activity size={16} />
          <h3>System Health</h3>
        </div>
        {health.isLoading && <p className="loading">Checking backend…</p>}
        {health.isError && (
          <div className="error-box">
            Cannot reach the backend. Is FastAPI running on port 8000?<br />
            Run: <code className="mono">cd backend &amp;&amp; uvicorn app.main:app --reload</code>
          </div>
        )}
        {hd && (
          <table className="data-table">
            <tbody>
              <tr>
                <td><strong>Service status</strong></td>
                <td>
                  <StatusIcon ok={hd.status === 'ok'} />
                  {' '}{hd.status === 'ok' ? 'Operational' : 'Degraded'}
                </td>
              </tr>
              <tr>
                <td><strong>MongoDB</strong></td>
                <td>
                  <StatusIcon ok={hd.database?.connected} />
                  {' '}{hd.database?.connected ? `Connected (${hd.database.db})` : 'Unavailable'}
                </td>
              </tr>
              <tr>
                <td><strong>Version</strong></td>
                <td className="mono">{hd.version}</td>
              </tr>
              {!hd.database?.connected && (
                <tr>
                  <td colSpan={2}>
                    <div className="error-box" style={{ marginTop: 8 }}>
                      {hd.message}
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Metrics */}
      {md && (
        <>
          <h2 style={{ marginBottom: 16 }}>Corpus Metrics</h2>
          <div className="metric-grid">
            <div className="metric-card">
              <div className="metric-value">{md.documents?.total ?? '—'}</div>
              <div className="metric-label">Active documents</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{md.assets?.total ?? '—'}</div>
              <div className="metric-label">P&amp;ID assets</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{md.assets?.relationships ?? '—'}</div>
              <div className="metric-label">Verified relationships</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{md.ocr?.total_regions ?? '—'}</div>
              <div className="metric-label">OCR regions</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{md.review?.pending_tasks ?? '—'}</div>
              <div className="metric-label">Pending reviews</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{md.documents?.original ?? '—'}</div>
              <div className="metric-label">Original sources</div>
            </div>
            <div className="metric-card">
              <div className="metric-value" style={{ color: 'var(--amber)' }}>
                {md.documents?.synthetic_demo ?? '—'}
              </div>
              <div className="metric-label">Synthetic-demo documents</div>
            </div>
          </div>

          <div className="panel">
            <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              <strong>Data provenance note:</strong> Original P&amp;ID images and the scanned
              work-order PDF are the authoritative sources. All other documents in this corpus are
              synthetic demo records — clearly labelled throughout the application.
              OCR-extracted fields are <span className="badge badge-proposed">AI proposed</span> until
              reviewed by a human.
            </p>
          </div>
        </>
      )}
    </div>
  )
}
