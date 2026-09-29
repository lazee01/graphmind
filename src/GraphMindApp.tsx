import React, { useState, useRef, useEffect } from 'react';
import { useGraphMind } from './hooks/useGraphMind';
import { PDFUploader } from './components/PDFUploader';
import { DocumentList } from './components/DocumentList';
import { AnswerPanel } from './components/AnswerPanel';
import { EvidenceCard } from './components/EvidenceCard';
import { GraphPanel } from './components/GraphPanel';

export const GraphMindApp: React.FC = () => {
  const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
  const { documents, uploadDocument, ask, health, loading, demoMode } = useGraphMind(apiUrl);
  
  const [query, setQuery] = useState('');
  const [answerData, setAnswerData] = useState<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    
    const data = await ask(query);
    if (data) {
      setAnswerData(data);
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [answerData]);

  return (
    <div className="graphmind-app">
      <header className="app-header">
        <div className="header-left">
          <img src="/graphmind-icon.svg" alt="GraphMind Logo" className="app-logo" />
          <h1>GraphMind <span className="subtitle">Research Console</span></h1>
        </div>
        <div className="header-right">
          {demoMode && <span className="demo-badge">DEMO MODE</span>}
          <div className={`status-indicator ${health}`}>
            <span className="status-dot"></span>
            {health === 'checking' ? 'Connecting...' : health === 'online' ? 'API Online' : 'API Offline'}
          </div>
        </div>
      </header>

      <div className="app-layout">
        <aside className="left-panel">
          <div className="panel-section">
            <h2>Document Library <span className="badge">{documents.length}</span></h2>
            <PDFUploader onUpload={uploadDocument} />
            <DocumentList documents={documents} />
          </div>
        </aside>

        <main className="center-panel">
          <div className="qa-container">
            <div className="messages-area">
              <AnswerPanel data={answerData} loading={loading} />
              <div ref={messagesEndRef} />
            </div>
            
            <form className="query-form" onSubmit={handleAsk}>
              <input 
                type="text" 
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Ask a question about your documents..."
                disabled={loading}
              />
              <button type="submit" disabled={loading || !query.trim()}>
                {loading ? 'Thinking...' : 'Ask GraphMind'}
              </button>
            </form>
          </div>
        </main>

        <aside className="right-panel">
          <div className="panel-section">
            <h2>Evidence & Citations</h2>
            {answerData?.evidence ? (
              <div className="evidence-list">
                {answerData.evidence.map((ev: any, i: number) => (
                  <EvidenceCard key={ev.id} evidence={ev} index={i + 1} />
                ))}
              </div>
            ) : (
              <div className="empty-state">
                Ask a question to see extracted evidence.
              </div>
            )}
          </div>
        </aside>
      </div>

      {answerData?.paths && answerData.paths.length > 0 && (
        <GraphPanel paths={answerData.paths} />
      )}
    </div>
  );
};
