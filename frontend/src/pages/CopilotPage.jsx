// CopilotPage.jsx — Pragyan Expert Knowledge Copilot conversational workspace.
// Desktop: conversation centre, asset context panel, evidence drawer.
// Mobile: single column, citation chips open bottom sheet, 44px tap targets.
import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  createConversation,
  sendMessage,
  submitFeedback,
  fetchCopilotStatus,
  triggerIndex,
  fetchAsset,
} from '../api';

// ── Constants ─────────────────────────────────────────────────────────────────

const EXAMPLE_QUESTIONS = [
  'What evidence is linked to ETP-601?',
  'What drawing contains ETP-601?',
  'What verified P&ID relationship is recorded for P-601?',
  'What work-order evidence mentions R-201?',
  'Show inspection records for C-301.',
];

const SAFETY_BOUNDARY_QUESTIONS = [
  'Close XV-603.',
  'What is the current pressure of B-501?',
  'Is the plant OISD compliant?',
];

const PROVENANCE_LABELS = {
  original: { label: 'Original', cls: 'badge-verified', title: 'From original P&ID source files' },
  synthetic_demo: { label: 'Synthetic Demo', cls: 'badge-synthetic', title: 'Synthetic demo data — not real plant evidence' },
  derived_ocr: { label: 'OCR Derived', cls: 'badge-pending', title: 'Derived from OCR of scanned maintenance records' },
};

const REVIEW_STATE_LABELS = {
  verified: { label: 'Verified', cls: 'badge-verified' },
  'AI proposed': { label: 'AI Proposed', cls: 'badge-proposed' },
  pending_review: { label: 'Pending Review', cls: 'badge-pending' },
  rejected: { label: 'Rejected', cls: 'badge-unreadable' },
  unreadable: { label: 'Unreadable', cls: 'badge-unreadable' },
};

const SUPPORT_LABELS = {
  high_support: { label: 'High Evidence Support', cls: 'status-verified' },
  partial_support: { label: 'Partial Evidence Support', cls: 'status-pending' },
  insufficient: { label: 'Insufficient Evidence', cls: 'status-unreadable' },
};

// ── Small components ──────────────────────────────────────────────────────────

function ProvenanceBadge({ provenance, reviewState }) {
  const prov = PROVENANCE_LABELS[provenance] || { label: provenance, cls: 'badge-pending', title: '' };
  const rev = REVIEW_STATE_LABELS[reviewState] || { label: reviewState, cls: 'badge-pending' };
  return (
    <span style={{ display: 'inline-flex', gap: 4, flexWrap: 'wrap' }}>
      <span className={`badge ${prov.cls}`} title={prov.title}>{prov.label}</span>
      <span className={`badge ${rev.cls}`}>{rev.label}</span>
    </span>
  );
}

function CitationChip({ citation, onClick, isActive }) {
  const prov = PROVENANCE_LABELS[citation.provenance] || {};
  return (
    <button
      className={`citation-chip${isActive ? ' active' : ''}`}
      onClick={() => onClick(citation)}
      title={`Open: ${citation.title}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '2px 8px',
        borderRadius: 4,
        border: '1px solid var(--border)',
        background: isActive ? 'var(--teal)' : 'var(--panel)',
        color: isActive ? '#fff' : 'var(--text-primary)',
        cursor: 'pointer',
        fontSize: 12,
        fontFamily: 'var(--font-mono)',
        fontWeight: 600,
        transition: 'all 0.15s',
        minHeight: 28,
      }}
    >
      <span>{citation.citation_id}</span>
      {citation.provenance === 'synthetic_demo' && (
        <span style={{ color: isActive ? '#fff' : 'var(--amber)', fontSize: 10 }}>⚠</span>
      )}
    </button>
  );
}

function StatusBanner({ status, label, confidence }) {
  const cfg = {
    supported: { bg: '#DCFCE7', color: '#177245', icon: '✓', text: 'Supported by evidence' },
    insufficient_evidence: { bg: '#FEE2E2', color: '#B42318', icon: '○', text: 'Insufficient Evidence' },
    safety_boundary: { bg: '#FEF9C3', color: '#B45309', icon: '⚠', text: 'Outside scope — read-only system' },
  };
  const c = cfg[status] || cfg.supported;
  const sup = label ? SUPPORT_LABELS[label] : null;

  return (
    <div style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 8,
      padding: '4px 10px',
      borderRadius: 4,
      background: c.bg,
      color: c.color,
      fontSize: 12,
      fontWeight: 600,
    }}>
      <span>{c.icon}</span>
      <span>{sup ? sup.label : c.text}</span>
      {confidence?.evidence_count > 0 && (
        <span style={{ fontWeight: 400, opacity: 0.8 }}>
          · {confidence.evidence_count} source{confidence.evidence_count !== 1 ? 's' : ''}
        </span>
      )}
    </div>
  );
}

function ServiceStatusBar({ status }) {
  if (!status) return null;
  const items = [
    { key: 'ollama', label: 'LLM', ok: status.ollama?.available },
    { key: 'qdrant', label: 'Vector', ok: status.qdrant?.available },
    { key: 'neo4j', label: 'Graph', ok: status.neo4j?.available },
    { key: 'mongo', label: 'MongoDB', ok: status.mongodb?.available },
  ];
  const allOk = items.every(i => i.ok);
  if (allOk) return null;

  return (
    <div style={{
      display: 'flex',
      gap: 8,
      flexWrap: 'wrap',
      padding: '6px 16px',
      background: '#FEF9C3',
      borderBottom: '1px solid var(--border)',
      fontSize: 12,
    }}>
      <span style={{ color: 'var(--amber)', fontWeight: 600 }}>⚠ Service status:</span>
      {items.map(it => (
        <span key={it.key} style={{ color: it.ok ? 'var(--green)' : 'var(--amber)' }}>
          {it.ok ? '✓' : '✗'} {it.label}
        </span>
      ))}
      {!status.mongodb?.chunk_count && (
        <span style={{ color: 'var(--red)' }}>· Corpus not indexed — click "Index Now"</span>
      )}
    </div>
  );
}

// ── Message bubble ─────────────────────────────────────────────────────────────

function MessageBubble({ msg, onSelectCitation, selectedCitation, onFeedback }) {
  const [showDetails, setShowDetails] = useState(false);
  const isUser = msg.role === 'user';

  if (isUser) {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', margin: '8px 0' }}>
        <div style={{
          maxWidth: '70%',
          padding: '10px 14px',
          borderRadius: '14px 14px 4px 14px',
          background: 'var(--teal)',
          color: '#fff',
          fontSize: 14,
          lineHeight: '20px',
        }}>
          {msg.content}
        </div>
      </div>
    );
  }

  // Assistant message
  return (
    <div style={{ margin: '8px 0' }}>
      <div style={{
        display: 'flex',
        gap: 8,
        alignItems: 'flex-start',
      }}>
        {/* Avatar */}
        <div style={{
          width: 28,
          height: 28,
          borderRadius: '50%',
          background: 'var(--teal)',
          color: '#fff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 12,
          fontWeight: 700,
          flexShrink: 0,
          marginTop: 4,
        }}>P</div>

        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Status banner */}
          {msg.answer_status && (
            <div style={{ marginBottom: 6 }}>
              <StatusBanner
                status={msg.answer_status}
                label={msg.answer_confidence?.label}
                confidence={msg.answer_confidence}
              />
            </div>
          )}

          {/* Synthetic demo warning */}
          {msg.citations?.some(c => c.provenance === 'synthetic_demo') && (
            <div style={{
              padding: '6px 10px',
              background: '#FEF9C3',
              borderLeft: '3px solid var(--amber)',
              borderRadius: '0 4px 4px 0',
              fontSize: 12,
              color: 'var(--amber)',
              marginBottom: 8,
              fontWeight: 600,
            }}>
              ⚠ Some citations are Synthetic Demo Data — not real plant evidence
            </div>
          )}

          {/* Answer text */}
          <div style={{
            background: 'var(--panel)',
            border: '1px solid var(--border)',
            borderRadius: '4px 14px 14px 14px',
            padding: '12px 14px',
            fontSize: 14,
            lineHeight: '22px',
            whiteSpace: 'pre-wrap',
          }}>
            {msg.content}
          </div>

          {/* Citation chips */}
          {msg.citations?.length > 0 && (
            <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
              <span style={{ fontSize: 12, color: 'var(--text-muted)', marginRight: 4 }}>Citations:</span>
              {msg.citations.map(c => (
                <CitationChip
                  key={c.citation_id}
                  citation={c}
                  onClick={onSelectCitation}
                  isActive={selectedCitation?.citation_id === c.citation_id}
                />
              ))}
            </div>
          )}

          {/* Suggested follow-ups */}
          {msg.suggested_followups?.length > 0 && (
            <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {msg.suggested_followups.map((f, i) => (
                <span
                  key={i}
                  style={{
                    padding: '3px 10px',
                    borderRadius: 4,
                    border: '1px solid var(--teal)',
                    color: 'var(--teal)',
                    fontSize: 12,
                    cursor: 'default',
                  }}
                >{f}</span>
              ))}
            </div>
          )}

          {/* Details toggle */}
          <div style={{ marginTop: 6, display: 'flex', gap: 12, alignItems: 'center' }}>
            {msg.latency_ms > 0 && (
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                {msg.latency_ms}ms
                {msg.retrieval_info?.ollama_used && ' · LLM'}
                {msg.retrieval_info?.used_qdrant && ' · Vector'}
                {msg.retrieval_info?.used_graph && ' · Graph'}
                {msg.retrieval_info?.used_mongo_fallback && ' · Keyword fallback'}
              </span>
            )}
            <button
              onClick={() => setShowDetails(!showDetails)}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                fontSize: 11,
                padding: 0,
              }}
            >
              {showDetails ? 'Hide details' : 'Why this answer?'}
            </button>
            {onFeedback && (
              <>
                <button
                  onClick={() => onFeedback(msg.message_id, 'helpful')}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13 }}
                  title="Helpful"
                >👍</button>
                <button
                  onClick={() => onFeedback(msg.message_id, 'not_helpful')}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13 }}
                  title="Not helpful"
                >👎</button>
              </>
            )}
          </div>

          {/* Retrieval details */}
          {showDetails && msg.retrieval_info && (
            <div style={{
              marginTop: 8,
              padding: '10px 12px',
              background: '#F7F9FB',
              border: '1px solid var(--border)',
              borderRadius: 4,
              fontSize: 12,
              color: 'var(--text-secondary)',
            }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>Retrieval details</div>
              <div>Tags detected: {msg.retrieval_info.tags_found?.join(', ') || 'none'}</div>
              <div>Vector search: {msg.retrieval_info.used_qdrant ? '✓' : '✗ (unavailable or no results)'}</div>
              <div>Graph traversal: {msg.retrieval_info.used_graph ? '✓' : '✗'}</div>
              <div>Keyword fallback: {msg.retrieval_info.used_mongo_fallback ? '✓' : '✗'}</div>
              <div>LLM generation: {msg.retrieval_info.ollama_used ? '✓' : '✗ (Ollama unavailable)'}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Evidence Drawer ────────────────────────────────────────────────────────────

function EvidenceDrawer({ citation, onClose }) {
  if (!citation) return null;

  return (
    <div style={{
      borderLeft: '1px solid var(--border)',
      background: 'var(--panel)',
      padding: '16px',
      overflowY: 'auto',
      minWidth: 0,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontFamily: 'var(--font-mono)', fontSize: 13 }}>
          {citation.citation_id}
        </h3>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontSize: 18,
            color: 'var(--text-muted)',
            padding: 4,
            minWidth: 44,
            minHeight: 44,
          }}
          aria-label="Close evidence drawer"
        >×</button>
      </div>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>{citation.title}</div>
        <ProvenanceBadge provenance={citation.provenance} reviewState={citation.review_state} />
      </div>

      {citation.asset_tags?.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Asset tags: </span>
          {citation.asset_tags.map(t => (
            <Link
              key={t}
              to={`/assets/${t}`}
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 12,
                color: 'var(--teal)',
                marginRight: 6,
                textDecoration: 'none',
                fontWeight: 600,
              }}
            >{t}</Link>
          ))}
        </div>
      )}

      {citation.page && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
          Page: {citation.page}
        </div>
      )}

      <div style={{
        padding: '10px 12px',
        background: '#F7F9FB',
        border: '1px solid var(--border)',
        borderRadius: 4,
        fontSize: 13,
        lineHeight: '20px',
        fontFamily: citation.provenance === 'derived_ocr' ? 'var(--font-mono)' : 'var(--font-ui)',
        marginBottom: 12,
        maxHeight: 300,
        overflowY: 'auto',
        whiteSpace: 'pre-wrap',
      }}>
        {citation.excerpt}
      </div>

      {citation.open_target && (
        <Link
          to={citation.open_target}
          style={{
            display: 'block',
            padding: '8px 14px',
            background: 'var(--teal)',
            color: '#fff',
            borderRadius: 4,
            textDecoration: 'none',
            fontSize: 13,
            fontWeight: 600,
            textAlign: 'center',
            minHeight: 44,
            lineHeight: '26px',
          }}
        >
          Open source →
        </Link>
      )}

      <div style={{ marginTop: 12, fontSize: 11, color: 'var(--text-muted)' }}>
        Score: {citation.score} · Source: {citation.source_id}
      </div>
    </div>
  );
}

// ── Asset Context Panel ────────────────────────────────────────────────────────

function AssetContextPanel({ tag }) {
  const [asset, setAsset] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!tag) return;
    setLoading(true);
    fetchAsset(tag)
      .then(setAsset)
      .catch(() => setAsset(null))
      .finally(() => setLoading(false));
  }, [tag]);

  if (!tag) return null;

  return (
    <div style={{
      borderLeft: '1px solid var(--border)',
      background: 'var(--panel)',
      padding: '16px',
      overflowY: 'auto',
    }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>ASSET CONTEXT</div>
      {loading && <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Loading…</div>}
      {asset && (
        <>
          <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 16, color: 'var(--teal)', marginBottom: 8 }}>
            {asset.tag}
          </div>
          <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
            <tbody>
              {[
                ['Type', asset.asset_type],
                ['Area', asset.area],
                ['Drawing', asset.drawing_id],
                ['State', asset.state],
              ].map(([k, v]) => v ? (
                <tr key={k}>
                  <td style={{ color: 'var(--text-muted)', paddingRight: 8, paddingBottom: 4, verticalAlign: 'top' }}>{k}</td>
                  <td style={{ fontFamily: k === 'Drawing' ? 'var(--font-mono)' : 'inherit', paddingBottom: 4 }}>{v}</td>
                </tr>
              ) : null)}
            </tbody>
          </table>
          <div style={{ marginTop: 12, display: 'flex', gap: 8, flexDirection: 'column' }}>
            <Link
              to={`/assets/${tag}`}
              style={{
                display: 'block',
                padding: '6px 12px',
                border: '1px solid var(--teal)',
                color: 'var(--teal)',
                borderRadius: 4,
                textDecoration: 'none',
                fontSize: 12,
                fontWeight: 600,
                textAlign: 'center',
                minHeight: 36,
                lineHeight: '22px',
              }}
            >Asset 360 →</Link>
            {asset.drawing_id && (
              <Link
                to={`/drawings?id=${asset.drawing_id}`}
                style={{
                  display: 'block',
                  padding: '6px 12px',
                  border: '1px solid var(--border)',
                  color: 'var(--text-primary)',
                  borderRadius: 4,
                  textDecoration: 'none',
                  fontSize: 12,
                  textAlign: 'center',
                  minHeight: 36,
                  lineHeight: '22px',
                }}
              >View P&ID →</Link>
            )}
          </div>
        </>
      )}
      {!loading && !asset && tag && (
        <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>Tag {tag} not found in registry.</div>
      )}
    </div>
  );
}

// ── Main CopilotPage ───────────────────────────────────────────────────────────

export default function CopilotPage() {
  const [searchParams] = useSearchParams();
  const initialTag = searchParams.get('asset')?.toUpperCase() || '';

  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [selectedTag, setSelectedTag] = useState(initialTag);
  const [selectedCitation, setSelectedCitation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [statusData, setStatusData] = useState(null);
  const [indexing, setIndexing] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState({ include_ai_proposed: true, include_synthetic_demo: true });
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);

  const inputRef = useRef(null);
  const bottomRef = useRef(null);

  // Fetch service status on mount
  useEffect(() => {
    fetchCopilotStatus()
      .then(setStatusData)
      .catch(() => setStatusData(null));
  }, []);

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Pre-fill question when coming from Asset 360
  useEffect(() => {
    if (initialTag && messages.length === 0) {
      setInput(`What evidence is linked to ${initialTag}?`);
    }
  }, [initialTag]);

  async function ensureConversation() {
    if (conversationId) return conversationId;
    const convo = await createConversation({
      title: selectedTag ? `Copilot: ${selectedTag}` : 'Plant knowledge query',
      selected_asset_tag: selectedTag || null,
    });
    setConversationId(convo.conversation_id);
    return convo.conversation_id;
  }

  async function handleSend(queryText) {
    const q = (queryText || input).trim();
    if (!q || isLoading) return;

    setInput('');
    setSelectedCitation(null);
    setIsLoading(true);

    // Optimistically add user message
    const userMsg = { role: 'user', content: q, message_id: `u-${Date.now()}` };
    setMessages(prev => [...prev, userMsg]);

    try {
      const cid = await ensureConversation();
      const response = await sendMessage(cid, {
        message: q,
        selected_asset_tag: selectedTag || null,
        filters,
      });
      setMessages(prev => [...prev, { ...response, role: 'assistant' }]);
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${err.message}. Please check the backend is running.`,
        answer_status: 'insufficient_evidence',
        message_id: `err-${Date.now()}`,
      }]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleSelectCitation(citation) {
    setSelectedCitation(prev => prev?.citation_id === citation.citation_id ? null : citation);
    setMobileDrawerOpen(true);
  }

  async function handleFeedback(messageId, rating) {
    if (!conversationId) return;
    try {
      await submitFeedback({ conversation_id: conversationId, message_id: messageId, rating });
    } catch {
      // Non-critical
    }
  }

  async function handleIndex() {
    setIndexing(true);
    try {
      const result = await triggerIndex(false);
      alert(`Indexed ${result.indexed} chunks (${result.skipped} skipped, ${result.failed} failed).`);
      const status = await fetchCopilotStatus();
      setStatusData(status);
    } catch (err) {
      alert(`Index failed: ${err.message}`);
    } finally {
      setIndexing(false);
    }
  }

  function handleClearConversation() {
    setConversationId(null);
    setMessages([]);
    setSelectedCitation(null);
    setInput('');
  }

  const showDrawer = selectedCitation !== null;
  const showContext = selectedTag !== '';
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;

  // Desktop grid: context | conversation | evidence
  // Mobile: stacked
  const gridCols = isMobile
    ? '1fr'
    : showContext && showDrawer
    ? '220px 1fr 320px'
    : showContext && !showDrawer
    ? '220px 1fr'
    : showDrawer
    ? '1fr 320px'
    : '1fr';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Page header */}
      <div style={{
        padding: '14px 20px 10px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--panel)',
        flexShrink: 0,
        display: 'flex',
        gap: 12,
        alignItems: 'center',
        flexWrap: 'wrap',
      }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 16, fontWeight: 650 }}>⚗️ Expert Knowledge Copilot</h1>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
            Ask plant questions · Inspect source evidence · Honest abstention
          </div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          {/* Asset tag filter */}
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Asset:</label>
            <input
              type="text"
              placeholder="ETP-601"
              value={selectedTag}
              onChange={e => setSelectedTag(e.target.value.toUpperCase())}
              style={{
                padding: '4px 8px',
                border: '1px solid var(--border)',
                borderRadius: 4,
                fontFamily: 'var(--font-mono)',
                fontSize: 12,
                width: 90,
              }}
              aria-label="Filter by asset tag"
            />
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            style={{
              padding: '4px 10px',
              border: '1px solid var(--border)',
              borderRadius: 4,
              background: showFilters ? 'var(--surface)' : 'var(--panel)',
              cursor: 'pointer',
              fontSize: 12,
            }}
          >Filters ▾</button>
          <button
            onClick={handleIndex}
            disabled={indexing}
            style={{
              padding: '4px 10px',
              border: '1px solid var(--border)',
              borderRadius: 4,
              background: 'var(--panel)',
              cursor: 'pointer',
              fontSize: 12,
              opacity: indexing ? 0.6 : 1,
            }}
          >{indexing ? 'Indexing…' : 'Index Now'}</button>
          {messages.length > 0 && (
            <button
              onClick={handleClearConversation}
              style={{
                padding: '4px 10px',
                border: '1px solid var(--border)',
                borderRadius: 4,
                background: 'var(--panel)',
                cursor: 'pointer',
                fontSize: 12,
                color: 'var(--text-muted)',
              }}
            >Clear</button>
          )}
        </div>
      </div>

      {/* Filter panel */}
      {showFilters && (
        <div style={{
          padding: '8px 20px',
          borderBottom: '1px solid var(--border)',
          background: '#F7F9FB',
          display: 'flex',
          gap: 16,
          fontSize: 13,
          flexShrink: 0,
        }}>
          <label style={{ display: 'flex', gap: 6, alignItems: 'center', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={filters.include_ai_proposed}
              onChange={e => setFilters(f => ({ ...f, include_ai_proposed: e.target.checked }))}
            />
            Include AI Proposed evidence
          </label>
          <label style={{ display: 'flex', gap: 6, alignItems: 'center', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={filters.include_synthetic_demo}
              onChange={e => setFilters(f => ({ ...f, include_synthetic_demo: e.target.checked }))}
            />
            Include Synthetic Demo data
          </label>
        </div>
      )}

      {/* Service status bar */}
      <ServiceStatusBar status={statusData} />

      {/* Main content area */}
      <div style={{
        flex: 1,
        display: 'grid',
        gridTemplateColumns: gridCols,
        overflow: 'hidden',
        minHeight: 0,
      }}>
        {/* Asset context panel (desktop) */}
        {showContext && !isMobile && (
          <AssetContextPanel tag={selectedTag} />
        )}

        {/* Conversation column */}
        <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0 }}>
          {/* Messages */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: '16px 20px',
          }}>
            {messages.length === 0 && (
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                gap: 24,
                padding: 24,
              }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 32, marginBottom: 8 }}>⚗️</div>
                  <h2 style={{ margin: '0 0 8px', fontSize: 18 }}>Pragyan Knowledge Copilot</h2>
                  <p style={{ color: 'var(--text-muted)', fontSize: 13, maxWidth: 460 }}>
                    Ask a plant engineering question. Answers are grounded in source evidence from P&IDs,
                    maintenance records, and inspections. Unsupported questions receive an honest abstention.
                  </p>
                </div>

                <div style={{ width: '100%', maxWidth: 520 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 8 }}>
                    SUPPORTED QUESTIONS
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {EXAMPLE_QUESTIONS.map(q => (
                      <button
                        key={q}
                        onClick={() => handleSend(q)}
                        style={{
                          textAlign: 'left',
                          padding: '8px 12px',
                          border: '1px solid var(--border)',
                          borderRadius: 6,
                          background: 'var(--panel)',
                          cursor: 'pointer',
                          fontSize: 13,
                          color: 'var(--text-primary)',
                          transition: 'border-color 0.15s',
                          minHeight: 44,
                        }}
                      >{q}</button>
                    ))}
                  </div>
                </div>

                <div style={{ width: '100%', maxWidth: 520 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 8 }}>
                    SAFETY BOUNDARY (try these to see abstention)
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {SAFETY_BOUNDARY_QUESTIONS.map(q => (
                      <button
                        key={q}
                        onClick={() => handleSend(q)}
                        style={{
                          textAlign: 'left',
                          padding: '8px 12px',
                          border: '1px solid var(--amber)',
                          borderRadius: 6,
                          background: '#FEF9C3',
                          cursor: 'pointer',
                          fontSize: 13,
                          color: 'var(--amber)',
                          minHeight: 44,
                        }}
                      >{q}</button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <MessageBubble
                key={msg.message_id || i}
                msg={msg}
                onSelectCitation={handleSelectCitation}
                selectedCitation={selectedCitation}
                onFeedback={msg.role === 'assistant' ? handleFeedback : null}
              />
            ))}

            {isLoading && (
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', margin: '8px 0', paddingLeft: 36 }}>
                <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                  Retrieving evidence…
                </div>
                <div style={{
                  display: 'inline-flex',
                  gap: 4,
                }}>
                  {[0, 1, 2].map(i => (
                    <span
                      key={i}
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: '50%',
                        background: 'var(--teal)',
                        display: 'inline-block',
                        animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
                      }}
                    />
                  ))}
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input area */}
          <div style={{
            padding: '12px 16px',
            borderTop: '1px solid var(--border)',
            background: 'var(--panel)',
            flexShrink: 0,
          }}>
            <div style={{
              display: 'flex',
              gap: 8,
              alignItems: 'flex-end',
              maxWidth: '100%',
            }}>
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask a plant engineering question… (Enter to send, Shift+Enter for new line)"
                disabled={isLoading}
                rows={2}
                style={{
                  flex: 1,
                  padding: '10px 12px',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  fontFamily: 'var(--font-ui)',
                  fontSize: 14,
                  resize: 'none',
                  lineHeight: '20px',
                  background: isLoading ? '#F7F9FB' : 'var(--panel)',
                }}
                aria-label="Ask a plant knowledge question"
                id="copilot-input"
              />
              <button
                onClick={() => handleSend()}
                disabled={!input.trim() || isLoading}
                style={{
                  padding: '10px 18px',
                  borderRadius: 6,
                  background: 'var(--teal)',
                  color: '#fff',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: 14,
                  fontWeight: 600,
                  minWidth: 72,
                  minHeight: 44,
                  opacity: (!input.trim() || isLoading) ? 0.5 : 1,
                  transition: 'opacity 0.15s',
                }}
                id="copilot-send-btn"
              >Send</button>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
              Source-grounded only · Abstains when evidence is insufficient · Not a plant control system
            </div>
          </div>
        </div>

        {/* Evidence drawer (desktop) */}
        {showDrawer && !isMobile && (
          <EvidenceDrawer citation={selectedCitation} onClose={() => setSelectedCitation(null)} />
        )}
      </div>

      {/* Mobile: asset context + citation bottom sheet */}
      {isMobile && mobileDrawerOpen && selectedCitation && (
        <div
          style={{
            position: 'fixed',
            bottom: 0,
            left: 0,
            right: 0,
            background: 'var(--panel)',
            borderTop: '2px solid var(--teal)',
            borderRadius: '16px 16px 0 0',
            zIndex: 100,
            maxHeight: '70vh',
            overflowY: 'auto',
            padding: '16px',
          }}
          role="dialog"
          aria-modal="true"
          aria-label="Evidence detail"
        >
          <EvidenceDrawer
            citation={selectedCitation}
            onClose={() => { setMobileDrawerOpen(false); setSelectedCitation(null); }}
          />
        </div>
      )}

      {/* Bounce animation */}
      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); }
          40% { transform: translateY(-6px); }
        }
        .citation-chip:hover { opacity: 0.85; }
      `}</style>
    </div>
  );
}
