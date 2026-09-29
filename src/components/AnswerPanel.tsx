import React from 'react';
import { AnswerResponse } from '../hooks/useGraphMind';

interface AnswerPanelProps {
  data: AnswerResponse | null;
  loading: boolean;
}

export const AnswerPanel: React.FC<AnswerPanelProps> = ({ data, loading }) => {
  if (loading) {
    return (
      <div className="answer-panel loading">
        <div className="typing-indicator">
          <span></span><span></span><span></span>
        </div>
        <p>Synthesizing research...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="answer-panel empty">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeOpacity="0.5">
          <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
        </svg>
        <h2>Ask a question to explore the literature</h2>
        <p>GraphMind combines knowledge graphs with vector search to provide precise, citable answers.</p>
      </div>
    );
  }

  const getConfidenceColor = (score: number) => {
    if (score >= 0.8) return '#22c55e'; // green
    if (score >= 0.5) return '#eab308'; // yellow
    return '#ef4444'; // red
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(data.answer);
  };

  const handleExport = () => {
    const blob = new Blob([`# GraphMind Answer\n\n${data.answer}\n\n## Sources\n${data.evidence.map((e, i) => `[${i+1}] ${e.docName} (Page ${e.page})`).join('\n')}`], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'graphmind_answer.md';
    a.click();
  };

  // Replace [1], [2] with styled markers
  const renderFormattedAnswer = (text: string) => {
    const parts = text.split(/(\[\d+\])/g);
    return parts.map((part, index) => {
      if (part.match(/\[\d+\]/)) {
        return <span key={index} className="citation-marker">{part}</span>;
      }
      return part;
    });
  };

  return (
    <div className="answer-panel">
      <div className="answer-header">
        <div className="confidence-badge" style={{ borderColor: getConfidenceColor(data.confidence), color: getConfidenceColor(data.confidence) }}>
          Confidence: {(data.confidence * 100).toFixed(0)}%
        </div>
        <div className="answer-actions">
          <button onClick={handleCopy} title="Copy to clipboard">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
          </button>
          <button onClick={handleExport} title="Export as Markdown">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
          </button>
        </div>
      </div>
      
      <div className="answer-content">
        {renderFormattedAnswer(data.answer)}
      </div>

      <div className="agent-pipeline">
        <h4>Pipeline Status:</h4>
        <div className="agent-list">
          {data.agents.map((agent, i) => (
            <div key={i} className={`agent-chip ${agent.completed ? 'completed' : ''}`}>
              {agent.completed && <span className="checkmark">✓</span>} {agent.name}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
