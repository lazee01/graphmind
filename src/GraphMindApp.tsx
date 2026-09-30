import React, { useState, useRef, useEffect } from 'react';
import { useGraphMind } from './hooks/useGraphMind';
import { PDFUploader } from './components/PDFUploader';
import { DocumentList } from './components/DocumentList';
import { AnswerPanel } from './components/AnswerPanel';
import { EvidenceCard } from './components/EvidenceCard';
import { GraphPanel } from './components/GraphPanel';
import LoginPage, { type AuthUser } from './components/LoginPage';
import { onAuthChange, logout as firebaseLogout } from './lib/firebase';

export const GraphMindApp: React.FC = () => {
  const apiUrl = 'https://graphmind-api-zhrf.onrender.com';
  const { documents, uploadDocument, ask, health, loading, demoMode } = useGraphMind(apiUrl);
  
  const [query, setQuery] = useState('');
  const [answerData, setAnswerData] = useState<any>(null);
  const [user, setUser] = useState<AuthUser | null>(() => {
    try {
      const saved = localStorage.getItem('graphmind_user');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [showLogin, setShowLogin] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      const unsub = onAuthChange(u => {
        if (u) {
          setUser({ uid: u.uid, email: u.email, displayName: u.displayName });
        }
      });
      return unsub;
    } catch {
      // Using local backend auth session
    }
  }, []);

  const handleLogout = async () => {
    localStorage.removeItem('graphmind_token');
    localStorage.removeItem('graphmind_user');
    setUser(null);
    try {
      await firebaseLogout();
    } catch {
      // Ignore if Firebase wasn't active
    }
  };

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

  if (showLogin) {
    return (
      <div style={{ position: 'relative' }}>
        <button
          onClick={() => setShowLogin(false)}
          style={{
            position: 'fixed', top: 20, right: 24, zIndex: 1000,
            background: '#1e293b', color: '#e2e8f0', border: '1px solid #334155',
            borderRadius: '8px', padding: '8px 16px', cursor: 'pointer', fontWeight: 600,
          }}
        >
          ✕ Back to Console
        </button>
        <LoginPage
          onSuccess={(loggedInUser) => {
            if (loggedInUser) setUser(loggedInUser);
            setShowLogin(false);
          }}
        />
      </div>
    );
  }

  return (
    <div className="graphmind-app">
      <header className="app-header">
        <div className="header-left">
          <img src="/graphmind-icon.svg" alt="GraphMind Logo" className="app-logo" />
          <h1>GraphMind <span className="subtitle">Research Console</span></h1>
        </div>
        <div className="header-right" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {demoMode && <span className="demo-badge">DEMO MODE</span>}
          <div className={`status-indicator ${health}`}>
            <span className="status-dot"></span>
            {health === 'checking' ? 'Connecting...' : health === 'online' ? 'API Online (Groq Llama 3.3 70B)' : 'API Offline'}
          </div>
          {user ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: '#67e8f9', fontSize: '13px', fontWeight: 600 }}>
                👤 {user.displayName || user.email}
              </span>
              <button
                onClick={handleLogout}
                style={{
                  background: '#1e293b', color: '#f87171', border: '1px solid #334155',
                  borderRadius: '6px', padding: '6px 12px', cursor: 'pointer', fontSize: '12px',
                }}
              >
                Sign Out
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowLogin(true)}
              style={{
                background: '#06b6d4', color: '#0a0e1a', border: 'none',
                borderRadius: '6px', padding: '7px 14px', cursor: 'pointer',
                fontSize: '13px', fontWeight: 700,
              }}
            >
              🔒 Sign In
            </button>
          )}
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
                placeholder="Ask a scientific question (e.g., How does RAPTOR improve over RAG?)..."
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
