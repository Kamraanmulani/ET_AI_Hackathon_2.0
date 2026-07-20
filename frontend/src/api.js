// api.js — Shared API client for Pragyan Plant Intelligence frontend.
// All calls go to the FastAPI backend; never directly to MongoDB or external services.

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

async function apiFetch(path, options = {}) {
  const resp = await fetch(`${API_BASE}${path}`, options);
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || `API error ${resp.status} on ${path}`);
  }
  return resp.json();
}

// ── Health ───────────────────────────────────────────────────────────────────
export const fetchHealth = () => apiFetch('/api/v1/health');
export const fetchMetrics = () => apiFetch('/api/v1/metrics');

// ── Documents / Catalogue ────────────────────────────────────────────────────
export const fetchDocuments = () => apiFetch('/api/v1/documents');
export const fetchCatalogueDocuments = () => apiFetch('/api/v1/documents/catalogue');
export const fetchDocument = (id) => apiFetch(`/api/v1/documents/${id}`);
export const fetchDocumentEntities = (id) => apiFetch(`/api/v1/documents/${id}/entities`);

// ── Drawings / P&ID Explorer ─────────────────────────────────────────────────
export const fetchDrawings = () => apiFetch('/api/v1/drawings');
export const fetchDrawing = (id) => apiFetch(`/api/v1/drawings/${id}`);

// ── Assets ───────────────────────────────────────────────────────────────────
export const fetchAssets = () => apiFetch('/api/v1/assets');
export const fetchAsset = (tag) => apiFetch(`/api/v1/assets/${tag}`);
export const fetchAssetEvidence = (tag) => apiFetch(`/api/v1/assets/${tag}/evidence`);
export const fetchAssetAudit = (tag) => apiFetch(`/api/v1/assets/${tag}/audit`);
export const fetchAssetEvidenceGraph = (tag) => apiFetch(`/api/v1/assets/${tag}/evidence-graph`);

// ── Review Queue ─────────────────────────────────────────────────────────────
export const fetchReviewSummary = () => apiFetch('/api/v1/review');
export const fetchReviewTasks = (params = {}) => {
  const qs = new URLSearchParams(
    Object.fromEntries(Object.entries(params).filter(([, v]) => v !== null && v !== undefined))
  ).toString();
  return apiFetch(`/api/v1/review/tasks${qs ? '?' + qs : ''}`);
};
export const fetchReviewTask = (id) => apiFetch(`/api/v1/review/tasks/${id}`);
export const submitDecision = (taskId, body) =>
  apiFetch(`/api/v1/review/tasks/${taskId}/decide`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

// ── Grounded Query ────────────────────────────────────────────────────────────
export const fetchQuery = (q, assetTag) => {
  const qs = new URLSearchParams({ q, ...(assetTag ? { asset_tag: assetTag } : {}) }).toString();
  return apiFetch(`/api/v1/query?${qs}`);
};

// ── Expert Knowledge Copilot ──────────────────────────────────────────────────
export const createConversation = (body) =>
  apiFetch('/api/v1/copilot/conversations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

export const sendMessage = (conversationId, body) =>
  apiFetch(`/api/v1/copilot/conversations/${conversationId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

export const getConversation = (conversationId) =>
  apiFetch(`/api/v1/copilot/conversations/${conversationId}`);

export const submitFeedback = (body) =>
  apiFetch('/api/v1/copilot/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

export const fetchCopilotStatus = () => apiFetch('/api/v1/copilot/status');

export const triggerIndex = (force = false) =>
  apiFetch(`/api/v1/copilot/index?force=${force}`, { method: 'POST' });

// ── Static asset helpers ──────────────────────────────────────────────────────
export const pidImageUrl = (filename) => `${API_BASE}/static/pid/${encodeURIComponent(filename)}`;
export const ocrPageUrl = (pageNum) => `${API_BASE}/static/ocr-pages/page-${String(pageNum).padStart(3, '0')}.png`;
