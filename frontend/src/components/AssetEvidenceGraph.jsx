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
import { Network, Filter } from 'lucide-react';

function ProvenanceBadge({ provenance, reviewState }) {
  if (provenance === 'synthetic_demo') {
    return <span className="badge" style={{ background: '#dbeafe', color: '#1e40af', border: '1px solid #bfdbfe' }}>⚠ Synthetic Demo</span>;
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
    <div className="px-6 py-4 rounded-xl border-4 border-teal-500 bg-white shadow-lg text-center font-bold text-xl min-w-[150px]">
      <Handle type="target" position={Position.Top} className="!bg-teal-500" />
      <div className="text-teal-700">{data.label}</div>
      <div className="text-sm font-normal text-gray-500 mt-1 uppercase tracking-wider">Target Asset</div>
      <Handle type="source" position={Position.Bottom} className="!bg-teal-500" />
    </div>
  );
};

const DocumentNode = ({ data }) => {
  return (
    <div className="px-4 py-3 rounded-lg border border-gray-200 bg-white shadow-md max-w-[250px]">
      <Handle type="target" position={Position.Top} className="!bg-gray-400" />
      <div className="font-medium text-gray-800 text-sm mb-2 break-words">{data.label}</div>
      <ProvenanceBadge provenance={data.provenance} reviewState={data.review_state} />
      <Handle type="source" position={Position.Bottom} className="!bg-gray-400" />
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
          stroke: isProposed ? '#eab308' : (isSynthetic ? '#3b82f6' : '#10b981'),
          strokeWidth: 2,
          strokeDasharray: isProposed ? '5,5' : 'none'
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isProposed ? '#eab308' : (isSynthetic ? '#3b82f6' : '#10b981'),
        },
        labelStyle: { fill: '#4b5563', fontSize: 11, fontWeight: 500 },
        labelBgStyle: { fill: '#ffffff', fillOpacity: 0.8 },
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

  if (isLoading) return <div className="h-96 flex items-center justify-center text-gray-500">Loading graph...</div>;
  if (error) return <div className="h-96 flex items-center justify-center text-red-500">Error loading graph</div>;

  return (
    <div style={{ height: '600px', minHeight: '600px', display: 'flex', flexDirection: 'column', border: '1px solid #e5e7eb', borderRadius: '0.75rem', backgroundColor: '#f9fafb', overflow: 'hidden', position: 'relative' }}>
      <div style={{ backgroundColor: '#fff', padding: '12px 16px', borderBottom: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', justifyContent: 'space-between', zIndex: 10, boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Network className="w-5 h-5 text-teal-600" />
          <h3 className="font-semibold text-gray-800" style={{ margin: 0 }}>Asset Evidence Graph</h3>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Filter className="w-4 h-4 text-gray-500" />
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
              <input 
                type="checkbox" 
                checked={!excludeProposed} 
                onChange={e => setExcludeProposed(!e.target.checked)}
              />
              <span className="text-gray-700">Include Proposed OCR</span>
            </label>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
            <input 
              type="checkbox" 
              checked={!excludeSynthetic} 
              onChange={e => setExcludeSynthetic(!e.target.checked)}
            />
            <span className="text-gray-700">Include Synthetic Data</span>
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
          attributionPosition="bottom-left"
        >
          <Background color="#ccc" gap={16} />
          <Controls />
        </ReactFlow>
      </div>
    </div>
  );
}
