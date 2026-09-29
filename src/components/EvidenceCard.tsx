import React, { useState } from 'react';
import { Evidence } from '../hooks/useGraphMind';

interface EvidenceCardProps {
  evidence: Evidence;
  index: number;
}

export const EvidenceCard: React.FC<EvidenceCardProps> = ({ evidence, index }) => {
  const [expanded, setExpanded] = useState(false);
  const isTruncated = evidence.text.length > 200;

  return (
    <div className="evidence-card">
      <div className="evidence-header">
        <span className="evidence-index">[{index}]</span>
        <div className="evidence-meta">
          <span className="doc-name">{evidence.docName}</span>
          <span className="doc-page">Pg. {evidence.page}</span>
        </div>
      </div>
      <div className="evidence-section">
        Section: {evidence.section}
      </div>
      <div className="evidence-text" onClick={() => setExpanded(!expanded)}>
        {expanded || !isTruncated ? evidence.text : `${evidence.text.substring(0, 200)}...`}
      </div>
      <div className="evidence-footer">
        <div className="relevance-bar-container">
          <div 
            className="relevance-bar" 
            style={{ width: `${Math.max(0, Math.min(100, evidence.relevance * 100))}%` }}
          ></div>
        </div>
        <span className="relevance-score">Rel: {(evidence.relevance * 100).toFixed(0)}%</span>
      </div>
    </div>
  );
};
