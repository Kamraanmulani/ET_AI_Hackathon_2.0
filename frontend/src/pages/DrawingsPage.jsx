// DrawingsPage.jsx — P&ID Explorer
// Renders the original unmodified P&ID images with separate SVG overlay layer.
// Tag labels are clickable and open Asset 360.
// Overlays are marked as coordinate_approximate in the UI.
import { useState, useRef, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { fetchDrawings, fetchDrawing, pidImageUrl } from '../api';

const AREA_LABELS = {
  reactor: 'Reactor',
  distillation: 'Distillation',
  storage: 'Storage & Tank Farm',
  utilities: 'Utilities / Boiler',
  effluent_treatment: 'Effluent Treatment',
};

// SVG overlay for asset tags on the P&ID image
function PidOverlay({ overlays, imageSize, onTagClick }) {
  if (!overlays || !imageSize.w || !imageSize.h) return null;

  return (
    <svg
      className="pid-overlay-svg"
      viewBox={`0 0 ${imageSize.w} ${imageSize.h}`}
      aria-label="Asset tag overlays"
    >
      {overlays.map((ov) => {
        const x = ov.x_pct * imageSize.w;
        const y = ov.y_pct * imageSize.h;
        const labelLen = ov.tag.length;
        const bw = labelLen * 18 + 24;
        const bh = 40;
        return (
          <g
            key={ov.tag}
            className="pid-tag-label"
            onClick={() => onTagClick(ov.tag)}
            role="button"
            aria-label={`Asset ${ov.tag} — click to open Asset 360`}
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && onTagClick(ov.tag)}
          >
            <rect
              className="pid-tag-bubble"
              x={x - bw / 2}
              y={y - bh / 2}
              width={bw}
              height={bh}
              rx="3"
            />
            <text
              className="pid-tag-text"
              x={x}
              y={y + 10}
              textAnchor="middle"
              fontSize="30"
              fontFamily="IBM Plex Mono, monospace"
              fontWeight="600"
            >
              {ov.tag}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function DrawingCanvas({ drawing }) {
  const navigate = useNavigate();
  const imgRef = useRef(null);
  const [imgSize, setImgSize] = useState({ w: 0, h: 0 });
  const [scale, setScale] = useState(1);

  const handleImgLoad = useCallback(() => {
    if (imgRef.current) {
      setImgSize({ w: imgRef.current.naturalWidth, h: imgRef.current.naturalHeight });
    }
  }, []);

  if (!drawing) return <div className="loading">Select a drawing on the left.</div>;

  return (
    <div className="pid-canvas-wrapper">
      <div
        className="pid-canvas-inner"
        style={{ transform: `scale(${scale})` }}
      >
        <img
          ref={imgRef}
          src={pidImageUrl(drawing.filename)}
          alt={`${drawing.label} P&ID drawing — original source, unmodified`}
          className="pid-source-img"
          onLoad={handleImgLoad}
          draggable={false}
        />
        <PidOverlay
          overlays={drawing.overlays}
          imageSize={imgSize}
          onTagClick={(tag) => navigate(`/assets/${tag}`)}
        />
      </div>

      {/* Zoom controls */}
      <div className="pid-controls">
        <button className="pid-control-btn" onClick={() => setScale((s) => Math.min(s + 0.2, 3))} aria-label="Zoom in">＋ Zoom</button>
        <button className="pid-control-btn" onClick={() => setScale(1)} aria-label="Reset zoom">Reset</button>
        <button className="pid-control-btn" onClick={() => setScale((s) => Math.max(s - 0.2, 0.3))} aria-label="Zoom out">－ Zoom</button>
      </div>

      {/* Legend */}
      <div className="pid-legend">
        <div style={{ marginBottom: 4, fontWeight: 600, fontSize: 11 }}>LEGEND</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
          <span style={{
            display: 'inline-block', width: 28, height: 14,
            background: 'rgba(8,126,139,0.15)', border: '1px solid #087E8B', borderRadius: 2
          }} />
          Tag overlay
        </div>
        <div style={{ marginTop: 4, fontSize: 11, color: 'var(--text-muted)' }}>
          ~ Positions are approximate
        </div>
      </div>
    </div>
  );
}

// Accessible asset list fallback
function AssetList({ overlays }) {
  const navigate = useNavigate();
  if (!overlays?.length) return null;
  return (
    <div style={{ marginTop: 12 }}>
      <div className="text-muted text-small" style={{ marginBottom: 6 }}>
        Asset tags in this drawing (click to open Asset 360):
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {overlays.map((ov) => (
          <button
            key={ov.tag}
            className="link-btn"
            style={{ fontFamily: 'IBM Plex Mono, monospace', fontSize: 12 }}
            onClick={() => navigate(`/assets/${ov.tag}`)}
          >
            {ov.tag}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function DrawingsPage() {
  // Default to ETP (PCP-PID-005) as the lead demo drawing
  const [selectedId, setSelectedId] = useState('PCP-PID-005');

  const { data: listData, isLoading: listLoading } = useQuery({
    queryKey: ['drawings'],
    queryFn: fetchDrawings,
  });

  const { data: drawingData, isLoading: drawingLoading } = useQuery({
    queryKey: ['drawing', selectedId],
    queryFn: () => fetchDrawing(selectedId),
    enabled: !!selectedId,
  });

  const drawings = listData?.drawings || [];

  if (listLoading) return <div className="loading">Loading P&ID drawings…</div>;

  return (
    <div>
      <div className="page-header">
        <div className="page-title-row">
          <h1>P&amp;ID Explorer</h1>
          <span className="text-muted" style={{ fontSize: 14 }}>
            Original source drawings — unmodified
          </span>
        </div>
      </div>

      <p className="text-muted text-small" style={{ marginBottom: 16 }}>
        Click a tag overlay to open Asset 360. Overlay positions are manually estimated
        (~ approximate) — not extracted from the drawing.
      </p>

      <div className="pid-explorer">
        {/* Drawing list */}
        <div className="pid-drawing-list">
          {drawings.map((d) => (
            <button
              key={d.drawing_id}
              className={`pid-drawing-btn${selectedId === d.drawing_id ? ' active' : ''}`}
              onClick={() => setSelectedId(d.drawing_id)}
              aria-pressed={selectedId === d.drawing_id}
            >
              <span className="label">{d.label}</span>
              <span className="sub">{d.drawing_id} · {d.overlay_count} tags</span>
            </button>
          ))}
        </div>

        {/* Canvas */}
        <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          {drawingLoading ? (
            <div className="loading">Loading drawing…</div>
          ) : (
            <DrawingCanvas drawing={drawingData} />
          )}
          {drawingData && <AssetList overlays={drawingData.overlays} />}
        </div>
      </div>
    </div>
  );
}
