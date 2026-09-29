import React, { useState } from 'react';
import { GraphPath } from '../hooks/useGraphMind';

interface GraphPanelProps {
  paths: GraphPath[];
}

export const GraphPanel: React.FC<GraphPanelProps> = ({ paths }) => {
  const [collapsed, setCollapsed] = useState(false);

  if (!paths || paths.length === 0) return null;

  return (
    <div className={`graph-panel ${collapsed ? 'collapsed' : ''}`}>
      <div className="graph-panel-header" onClick={() => setCollapsed(!collapsed)}>
        <h3>Knowledge Graph Paths ({paths.length})</h3>
        <button className="collapse-btn">
          {collapsed ? '▲' : '▼'}
        </button>
      </div>
      
      {!collapsed && (
        <div className="graph-panel-content">
          <div className="graph-paths">
            {paths.map(path => (
              <div key={path.id} className="graph-path-row">
                <div className="graph-node source">{path.source}</div>
                <div className="graph-relation">
                  <div className="relation-line" style={{ backgroundColor: path.color }}></div>
                  <span className="relation-label" style={{ color: path.color }}>{path.relation}</span>
                </div>
                <div className="graph-node target">{path.target}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
