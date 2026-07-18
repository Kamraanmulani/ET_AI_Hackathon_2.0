// ReviewPage.jsx — Interactive Review Queue
// Shows pending OCR and asset-link review tasks.
// Reviewer can: Verify, Reject, Correct (with input), or Mark unreadable.
// Every decision creates an audit event via POST /api/v1/review/tasks/{id}/decide.
// No plant-control actions are present.
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchReviewTasks, fetchReviewTask, submitDecision, ocrPageUrl } from '../api';

const TASK_TYPE_LABELS = {
  asset_link_review: 'Asset link',
  ocr_field_review: 'OCR field',
  field_review: 'OCR field',
  ocr_page_review: 'OCR page',
};

const STATE_BADGE = {
  pending_review: 'badge-pending',
  verified: 'badge-verified',
  rejected: 'badge-error',
  corrected: 'badge-proposed',
  unreadable: 'badge-error',
};

function StateBadge({ state }) {
  const cls = STATE_BADGE[state] || 'badge-pending';
  return <span className={`badge ${cls}`}>{state?.replace(/_/g, ' ')}</span>;
}

function ConfBar({ value }) {
  if (!value) return null;
  const pct = Math.round(value * 100);
  return (
    <span title={`Confidence: ${pct}%`}>
      <span className="conf-bar" style={{ width: `${Math.max(pct, 8)}px` }} />
      <span className="conf-value" style={{ marginLeft: 4 }}>{pct}%</span>
    </span>
  );
}

// Individual task row — expandable with decision controls
function TaskRow({ task }) {
  const [open, setOpen] = useState(false);
  const [correctedValue, setCorrectedValue] = useState('');
  const [decided, setDecided] = useState(task.state !== 'pending_review');
  const [lastDecision, setLastDecision] = useState(null);
  const queryClient = useQueryClient();

  const detailQuery = useQuery({
    queryKey: ['review-task', task.task_id],
    queryFn: () => fetchReviewTask(task.task_id),
    enabled: open,
  });

  const mutation = useMutation({
    mutationFn: ({ decision, correctedValue }) =>
      submitDecision(task.task_id, { decision, corrected_value: correctedValue || undefined }),
    onSuccess: (data) => {
      setDecided(true);
      setLastDecision(data.decision);
      queryClient.invalidateQueries({ queryKey: ['review-tasks'] });
      queryClient.invalidateQueries({ queryKey: ['review-task', task.task_id] });
    },
  });

  const decide = (decision) => mutation.mutate({ decision, correctedValue });

  const detail = detailQuery.data;
  const isPending = !decided && task.state === 'pending_review';

  return (
    <div className="review-task-row">
      {/* Summary row */}
      <div
        className="review-task-summary"
        onClick={() => setOpen((o) => !o)}
        role="button"
        aria-expanded={open}
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && setOpen((o) => !o)}
      >
        <span style={{ width: 24, color: 'var(--text-muted)' }}>{open ? '▾' : '▸'}</span>
        <span className="badge" style={{ background: '#F3F4F6', color: 'var(--text-secondary)', fontSize: 11 }}>
          {TASK_TYPE_LABELS[task.task_type] || task.task_type}
        </span>
        <code className="mono" style={{ fontSize: 12 }}>{task.task_id}</code>
        {task.proposed_asset_tag && (
          <code className="mono" style={{ color: 'var(--teal)', fontSize: 12 }}>
            {task.proposed_asset_tag}
          </code>
        )}
        {task.proposed_value && (
          <span className="text-muted text-small truncate" style={{ maxWidth: 200 }}>
            {task.proposed_value}
          </span>
        )}
        <span style={{ marginLeft: 'auto' }}>
          {lastDecision ? (
            <StateBadge state={lastDecision === 'verify' ? 'verified' : lastDecision} />
          ) : (
            <StateBadge state={task.state} />
          )}
        </span>
        {task.source_page && (
          <span className="text-muted text-small" style={{ marginLeft: 8 }}>
            p.{task.source_page}
          </span>
        )}
      </div>

      {/* Expanded body */}
      {open && (
        <div className="review-task-body open">
          {detailQuery.isLoading && <div className="loading">Loading detail…</div>}

          {detail && (
            <>
              {/* OCR Region text */}
              {detail.ocr_region && (
                <div>
                  <div className="text-muted text-small" style={{ marginBottom: 4, marginTop: 8 }}>
                    OCR extracted text (region <code className="mono">{detail.ocr_region.region_id}</code>):
                  </div>
                  <div className="evidence-text">{detail.ocr_region.text}</div>
                  <div className="evidence-meta">
                    Confidence: <ConfBar value={detail.ocr_region.confidence} />
                    &nbsp;· State: <StateBadge state={detail.ocr_region.review_state} />
                  </div>
                </div>
              )}

              {/* Source page image */}
              {detail.source_page && (
                <div style={{ marginTop: 12 }}>
                  <div className="text-muted text-small" style={{ marginBottom: 4 }}>
                    Source page {detail.source_page} (original scanned document):
                  </div>
                  <img
                    src={ocrPageUrl(detail.source_page)}
                    alt={`Source page ${detail.source_page} — scanned maintenance work order`}
                    className="review-page-img"
                    loading="lazy"
                  />
                </div>
              )}

              {/* Proposed value */}
              {(detail.proposed_asset_tag || detail.proposed_value) && (
                <div style={{ marginTop: 10 }}>
                  <span className="text-muted text-small">Proposed: </span>
                  <code className="mono" style={{ color: 'var(--violet)' }}>
                    {detail.proposed_asset_tag || detail.proposed_value}
                  </code>
                </div>
              )}
            </>
          )}

          {/* Decision controls */}
          {isPending && !decided ? (
            <div className="decision-buttons">
              <button
                className="btn btn-verify"
                onClick={() => decide('verify')}
                disabled={mutation.isPending}
                aria-label="Verify this extraction"
              >
                ✓ Verify
              </button>
              <button
                className="btn btn-reject"
                onClick={() => decide('reject')}
                disabled={mutation.isPending}
                aria-label="Reject this extraction"
              >
                ✗ Reject
              </button>
              <button
                className="btn btn-unread"
                onClick={() => decide('mark_unreadable')}
                disabled={mutation.isPending}
                aria-label="Mark as unreadable"
              >
                ? Unreadable
              </button>

              {/* Correct with input */}
              <div className="correct-input-row">
                <input
                  className="correct-input"
                  placeholder="Corrected value…"
                  value={correctedValue}
                  onChange={(e) => setCorrectedValue(e.target.value)}
                  aria-label="Enter corrected value"
                />
                <button
                  className="btn btn-correct"
                  onClick={() => {
                    if (correctedValue.trim()) decide('correct');
                  }}
                  disabled={mutation.isPending || !correctedValue.trim()}
                  aria-label="Submit correction"
                >
                  Correct
                </button>
              </div>

              {mutation.isError && (
                <div className="error-box" style={{ width: '100%', marginTop: 8 }}>
                  {mutation.error?.message}
                </div>
              )}
            </div>
          ) : (
            <div style={{ marginTop: 12 }}>
              <StateBadge state={lastDecision ? (lastDecision === 'verify' ? 'verified' : lastDecision) : task.state} />
              <span className="text-muted text-small" style={{ marginLeft: 8 }}>
                Decision recorded.
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ReviewPage() {
  const [taskType, setTaskType] = useState(null);
  const [page, setPage] = useState(1);
  const LIMIT = 20;

  const { data, isLoading, error } = useQuery({
    queryKey: ['review-tasks', taskType, page],
    queryFn: () => fetchReviewTasks({ task_type: taskType, page, limit: LIMIT }),
  });

  const tasks = data?.tasks || [];
  const total = data?.total || 0;
  const totalPages = data?.pages || 1;

  const FILTERS = [
    { key: null, label: 'All' },
    { key: 'asset_link_review', label: 'Asset link review' },
    { key: 'ocr_field_review', label: 'OCR field review' },
    { key: 'ocr_page_review', label: 'OCR page review' },
  ];

  if (isLoading) return <div className="loading">Loading review queue…</div>;
  if (error) return <div className="error-box">Failed to load review tasks: {error.message}</div>;

  return (
    <div>
      <div className="page-header">
        <div className="page-title-row">
          <h1>Review Queue</h1>
          <span className="text-muted" style={{ fontSize: 14 }}>{total} tasks total</span>
        </div>
      </div>
      <p className="text-muted text-small" style={{ marginBottom: 12 }}>
        Review OCR extractions and asset-link proposals. Every decision is logged to the audit trail.
        Allowed actions: Verify, Reject, Correct, Mark unreadable. No plant-control actions.
      </p>

      <div className="filter-tabs">
        {FILTERS.map((f) => (
          <button
            key={String(f.key)}
            className={`filter-tab${taskType === f.key ? ' active' : ''}`}
            onClick={() => { setTaskType(f.key); setPage(1); }}
            aria-pressed={taskType === f.key}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="panel" style={{ padding: 0 }}>
        {tasks.length === 0 && (
          <div className="no-evidence">
            No tasks match this filter.
          </div>
        )}
        {tasks.map((task) => (
          <TaskRow key={task.task_id} task={task} />
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', gap: 8, marginTop: 16, alignItems: 'center' }}>
          <button
            className="btn btn-outline"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            ← Prev
          </button>
          <span className="text-muted text-small">
            Page {page} of {totalPages}
          </span>
          <button
            className="btn btn-outline"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
