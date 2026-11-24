import React, { useMemo, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { AlertTriangle, Network, Filter } from 'lucide-react';

// Edge colours come from the token block so the graph follows the theme.
const token = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function ProvenanceBadge({ provenance, reviewState }) {
  if (provenance === 'synthetic_demo') {
    return <span className="badge badge-demo"><AlertTriangle size={12} aria-hidden="true" />Synthetic Demo</span>;
  }
  if (provenance === 'original') {
    return <span className="badge badge-verified">Original</span>;
  }
  if (reviewState === 'verified') {
    return <span className="badge badge-verified">Verified Match</span>;
  }
  return <span className="badge badge-proposed">AI Proposed</span>;
}

import { useQuery } from '@tanstack/react-query';
import { fetchAssetEvidenceGraph } from '../api';

// Custom Nodes
const AssetNode = ({ data }) => {
  return (
    <div className="graph-node-asset">
      <Handle type="target" position={Position.Top} className="graph-handle-asset" />
      <div className="graph-node-title">{data.label}</div>
      <div className="graph-node-sub">Target asset</div>
      <Handle type="source" position={Position.Bottom} className="graph-handle-asset" />
    </div>
  );
};

const DocumentNode = ({ data }) => {
  return (
    <div className="graph-node-doc">
      <Handle type="target" position={Position.Top} className="graph-handle-doc" />
      <div className="graph-node-title">{data.label}</div>
      <ProvenanceBadge provenance={data.provenance} reviewState={data.review_state} />
      <Handle type="source" position={Position.Bottom} className="graph-handle-doc" />
    </div>
  );
};

const nodeTypes = {
  asset: AssetNode,
  document: DocumentNode,
};

export default function AssetEvidenceGraph({ tag, onNodeClick }) {
  const [excludeSynthetic, setExcludeSynthetic] = useState(false);
  const [excludeProposed, setExcludeProposed] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ['asset-evidence-graph', tag],
    queryFn: () => fetchAssetEvidenceGraph(tag),
  });

  const { initialNodes, initialEdges } = useMemo(() => {
    if (!data || !data.nodes) return { initialNodes: [], initialEdges: [] };

    let filteredNodes = data.nodes;
    let filteredEdges = data.edges;

    if (excludeSynthetic) {
      filteredNodes = filteredNodes.filter(n => n.provenance !== 'synthetic_demo');
      filteredEdges = filteredEdges.filter(e => filteredNodes.find(n => n.id === e.target || n.id === e.source));
    }
    if (excludeProposed) {
      filteredNodes = filteredNodes.filter(n => n.review_state !== 'pending_review');
      filteredEdges = filteredEdges.filter(e => filteredNodes.find(n => n.id === e.target || n.id === e.source));
    }

    // Simple radial/tree layout
    const outNodes = [];
    const outEdges = [];

    // Find central node
    const centerNode = filteredNodes.find(n => n.id === tag.toUpperCase());
    if (centerNode) {
      outNodes.push({
        id: centerNode.id,
        type: centerNode.type,
        position: { x: 400, y: 300 },
        data: centerNode
      });
    }

    // Arrange others in a circle
    const others = filteredNodes.filter(n => n.id !== tag.toUpperCase());
    const radius = 250;
    const center = { x: 400, y: 300 };
    
    others.forEach((node, i) => {
      const angle = (i / others.length) * 2 * Math.PI;
      outNodes.push({
        id: node.id,
        type: node.type,
        position: {
          x: center.x + radius * Math.cos(angle),
          y: center.y + radius * Math.sin(angle)
        },
        data: node
      });
    });

    // Edges
    const colours = { proposed: token('--amber'), synthetic: token('--blue'), verified: token('--green') };
    filteredEdges.forEach(edge => {
      const isProposed = edge.state === 'pending_review';
      const isSynthetic = edge.evidence_basis.includes('Synthetic');
      outEdges.push({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.evidence_basis,
        animated: isProposed,
        style: {
          stroke: isProposed ? colours.proposed : (isSynthetic ? colours.synthetic : colours.verified),
          strokeWidth: 2,
          strokeDasharray: isProposed ? '5,5' : 'none'
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isProposed ? colours.proposed : (isSynthetic ? colours.synthetic : colours.verified),
        },
        labelStyle: { fill: 'var(--text-secondary)', fontSize: 11, fontWeight: 500 },
        labelBgStyle: { fill: 'var(--panel)', fillOpacity: 0.8 },
      });
    });

    return { initialNodes: outNodes, initialEdges: outEdges };
  }, [data, tag, excludeSynthetic, excludeProposed]);

  // We need to manage React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Update flow state when initial data changes
  React.useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  if (isLoading) return <div className="graph-state">Loading graph…</div>;
  if (error) return <div className="graph-state is-error">Error loading graph</div>;

  return (
    <div className="graph-frame">
      <div className="graph-toolbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Network size={18} aria-hidden="true" style={{ color: 'var(--teal)' }} />
          <h3>Asset Evidence Graph</h3>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Filter size={16} aria-hidden="true" style={{ color: 'var(--text-muted)' }} />
            <label>
              <input 
                type="checkbox" 
                checked={!excludeProposed} 
                onChange={e => setExcludeProposed(!e.target.checked)}
              />
              <span>Include Proposed OCR</span>
            </label>
          </div>
          <label>
            <input 
              type="checkbox" 
              checked={!excludeSynthetic} 
              onChange={e => setExcludeSynthetic(!e.target.checked)}
            />
            <span>Include Synthetic Data</span>
          </label>
        </div>
      </div>
      
      <div style={{ flex: 1, width: '100%', height: '100%' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={(_, node) => {
             if (node.type === 'document' && onNodeClick) {
                 onNodeClick(node.data);
             }
          }}
          nodeTypes={nodeTypes}
          fitView
          zoomOnScroll={false}
          preventScrolling={false}
          attributionPosition="bottom-left"
        >
          <Background color="var(--border)" gap={16} />
          <Controls />
        </ReactFlow>
      </div>
    </div>
  );
}
