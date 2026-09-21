import { ChangeEvent, FormEvent, useEffect, useState } from 'react'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import {
  AlertCircle, ArrowUpRight, BookOpen, CheckCircle2, ChevronRight, CircleDot,
  FileText, GitBranch, LoaderCircle, Search, Settings2, ShieldCheck, Sparkles,
  Upload, X,
} from 'lucide-react'
import './styles.css'

type Evidence = { id: string; document_name: string; text: string; page: number | null; section: string; score: number; citation: string }
type Answer = { question?: string; answer: string; confidence: number; status: string; provider: unknown; evidence: Evidence[]; graph_context: string[]; plan: { question_type: string; entities: string[] }; verification?: { supported: boolean; mode?: string } }
type Document = { id: string; name: string; source: string; chunks: number }
const API = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const DEMO_DOCUMENTS: Document[] = [
  { id: 'demo-1', name: 'graphmind-methodology.txt', source: 'offline demo corpus', chunks: 4 },
  { id: 'demo-2', name: 'retrieval-systems-survey.txt', source: 'offline demo corpus', chunks: 3 },
]
const DEMO_EVIDENCE: Evidence[] = [
  { id: 'demo-e1', document_name: 'graphmind-methodology.txt', text: 'Every passage keeps its source document, section, page when available, and stable chunk identifier so answers can be audited.', page: 2, section: 'Evidence and provenance', score: 0.96, citation: 'graphmind-methodology.txt (p. 2)' },
  { id: 'demo-e2', document_name: 'retrieval-systems-survey.txt', text: 'Hybrid retrieval blends lexical matching with semantic vectors to improve recall while preserving interpretable evidence signals.', page: 4, section: 'Retrieval', score: 0.84, citation: 'retrieval-systems-survey.txt (p. 4)' },
]
const DEMO_ANSWER: Answer = {
  answer: 'GraphMind preserves the source document, section, page when available, and a stable chunk identifier for each passage. This provenance lets a reader audit the answer instead of trusting an opaque generated claim.',
  confidence: 0.94, status: 'grounded', provider: { provider: 'offline-demo', active: true }, evidence: DEMO_EVIDENCE,
  graph_context: ['provenance relates to evidence', 'retrieval relates to vectors'],
  plan: { question_type: 'factoid', entities: ['provenance', 'passage'] }, verification: { supported: true, mode: 'demo' },
}

function App() {
  const [question, setQuestion] = useState('What does GraphMind preserve for each passage?')
  const [answer, setAnswer] = useState<Answer | null>(null)
  const [documents, setDocuments] = useState<Document[]>([])
  const [health, setHealth] = useState<{ status: string; chunks: number; provider: { provider?: string; active?: boolean }; neo4j: boolean; agents?: { name: string; mode: string }[] } | null>(null)
  const [offline, setOffline] = useState(false)
  const [busy, setBusy] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  const loadWorkspace = async () => {
    try {
      const [healthResponse, documentsResponse] = await Promise.all([fetch(`${API}/api/health`), fetch(`${API}/api/documents`)])
      if (!healthResponse.ok || !documentsResponse.ok) throw new Error('API unavailable')
      setHealth(await healthResponse.json())
      setDocuments(await documentsResponse.json())
    } catch {
      setOffline(true)
      setHealth({ status: 'demo', chunks: 7, provider: { provider: 'offline-demo', active: true }, neo4j: false, agents: ['planner', 'retrieval', 'graph', 'verifier', 'generator'].map((name) => ({ name, mode: 'offline-demo' })) })
      setDocuments(DEMO_DOCUMENTS)
    }
  }
  useEffect(() => { void loadWorkspace() }, [])

  const ask = async (event?: FormEvent) => {
    event?.preventDefault()
    if (!question.trim()) return
    setBusy(true); setError('')
    try {
      if (offline) {
        await new Promise((resolve) => window.setTimeout(resolve, 350))
        setAnswer({ ...DEMO_ANSWER, question })
        return
      }
      const response = await fetch(`${API}/api/ask`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) })
      if (!response.ok) throw new Error((await response.json()).detail || 'Query failed')
      setAnswer(await response.json())
    } catch (reason) {
      setOffline(true)
      setHealth({ status: 'demo', chunks: 7, provider: { provider: 'offline-demo', active: true }, neo4j: false, agents: ['planner', 'retrieval', 'graph', 'verifier', 'generator'].map((name) => ({ name, mode: 'offline-demo' })) })
      setDocuments(DEMO_DOCUMENTS)
      setAnswer({ ...DEMO_ANSWER, question })
    }
    finally { setBusy(false) }
  }

  const upload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    setUploading(true); setError('')
    const form = new FormData(); form.append('file', file)
    try {
      if (offline) {
        await new Promise((resolve) => window.setTimeout(resolve, 500))
        setDocuments((current) => [...current, { id: `demo-upload-${Date.now()}`, name: file.name, source: 'offline demo upload', chunks: 1 }])
        return
      }
      const response = await fetch(`${API}/api/documents`, { method: 'POST', body: form })
      if (!response.ok) throw new Error((await response.json()).detail || 'Upload failed')
      await loadWorkspace()
    } catch (reason) {
      setOffline(true)
      setHealth({ status: 'demo', chunks: 7, provider: { provider: 'offline-demo', active: true }, neo4j: false, agents: ['planner', 'retrieval', 'graph', 'verifier', 'generator'].map((name) => ({ name, mode: 'offline-demo' })) })
      setDocuments((current) => [...current, { id: `demo-upload-${Date.now()}`, name: file.name, source: 'offline demo upload', chunks: 1 }])
    }
    finally { setUploading(false); event.target.value = '' }
  }

  return <div className="app-shell">
    <header className="topbar">
      <a className="logo" href="#top"><span className="logo-mark"><GitBranch size={18} /></span><span>graph<span>mind</span></span></a>
      <nav><a className="active" href="#ask">Ask literature</a><a href="#library">Library</a><a href="#method">How it works</a></nav>
      <div className={`top-status ${offline ? 'demo-status' : ''}`}><CircleDot size={13} /> {offline ? 'OFFLINE DEMO MODE' : health?.status === 'ok' ? 'API ENGINE READY' : 'CONNECTING'} <Settings2 size={15} /></div>
    </header>
    <main id="top">
      <section className="hero">
        <div className="hero-copy"><div className="eyebrow"><Sparkles size={14} /> SCIENTIFIC LITERATURE QA</div><h1>Answers that<br /><em>show their work.</em></h1><p>GraphMind turns dense papers into grounded answers with provenance, hybrid retrieval, and an auditable evidence trail.</p><div className="hero-chips"><span><ShieldCheck size={14} /> Evidence-first</span><span><GitBranch size={14} /> Graph-aware</span><span><CircleDot size={14} /> Runs locally</span></div></div>
        <div className="hero-visual"><div className="halo halo-one" /><div className="halo halo-two" /><div className="visual-core"><GitBranch size={45} /><span>REASON<br />WITH<br />EVIDENCE</span></div><div className="orbit-label label-a">VECTOR</div><div className="orbit-label label-b">GRAPH</div><div className="orbit-label label-c">VERIFY</div></div>
      </section>
      <section className="workspace" id="ask">
        <div className="section-title"><div><span className="kicker">01 / RESEARCH CONSOLE</span><h2>Ask your library.</h2></div><span className="muted">Planner → retrieve → verify → cite</span></div>
        <form className="query-box" onSubmit={ask}><Search size={20} /><input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a question about your indexed papers…" /><button disabled={busy}>{busy ? <LoaderCircle className="spin" size={17} /> : <ArrowUpRight size={17} />} Ask</button></form>
        {error && <div className="notice error"><AlertCircle size={17} /> {error}<button onClick={() => setError('')} aria-label="Dismiss"><X size={15} /></button></div>}
        {busy && <div className="loading-card"><LoaderCircle className="spin" size={22} /><div><strong>Following the evidence trail…</strong><span>Planning sub-queries and scoring passages</span></div></div>}
        {!busy && answer && <div className="answer-grid"><article className="answer-card"><div className="card-head"><span className={`answer-status ${answer.status}`}><CheckCircle2 size={14} /> {answer.status === 'grounded' ? 'GROUNDED ANSWER' : 'INSUFFICIENT EVIDENCE'}</span><span className="confidence">Confidence {Math.round(answer.confidence * 100)}%</span></div><p className="answer-text">{answer.answer}</p><div className="answer-meta"><span>Provider: {JSON.stringify(answer.provider)}</span><span>Question type: {answer.plan.question_type}</span></div>{answer.graph_context.length > 0 && <div className="graph-context"><strong><GitBranch size={14} /> Graph context</strong>{answer.graph_context.map((item) => <span key={item}>{item}</span>)}</div>}</article><EvidencePanel evidence={answer.evidence} /></div>}
        {!busy && !answer && <div className="empty-state"><BookOpen size={25} /><strong>Ask your first question</strong><span>Answers will include ranked passages, section context, and citation-ready metadata.</span></div>}
      </section>
      <section className="library-section" id="library"><div className="section-title"><div><span className="kicker">02 / DOCUMENT LIBRARY</span><h2>What GraphMind knows.</h2></div><label className="upload-button"><Upload size={16} /> {uploading ? 'Extracting…' : 'Upload PDF or TXT'}<input type="file" accept=".pdf,.txt,.md" onChange={upload} disabled={uploading} /></label></div><div className="library-grid">{documents.map((document) => <article className="document-card" key={document.id}><div className="document-icon"><FileText size={20} /></div><div><strong>{document.name}</strong><span>{document.source === 'demo' ? 'Demo corpus' : 'Uploaded document'} · {document.chunks} chunks</span></div><ChevronRight size={16} /></article>)}</div></section>
      <section className="method-section" id="method"><div className="section-title"><div><span className="kicker">03 / TRANSPARENT BY DESIGN</span><h2>A practical pipeline.</h2></div></div><div className="method-grid">{[['01', 'Ingest', 'Extract text, detect sections, and preserve page metadata.'], ['02', 'Retrieve', 'Blend lexical matching with a dependency-free local vector index.'], ['03', 'Reason', 'Use graph context when available, with a local relationship fallback.'], ['04', 'Verify', 'Expose confidence, evidence, and citations instead of hiding uncertainty.']].map(([number, title, text]) => <article key={number}><span>{number}</span><h3>{title}</h3><p>{text}</p></article>)}</div></section>
    </main>
    <footer><span>GraphMind / B.Tech prototype</span><span>{health ? `${health.chunks} chunks · ${health.provider.provider || 'local'} provider · ${(health.agents || []).length || 5} agents` : 'FastAPI + React'}</span></footer>
  </div>
}

function EvidencePanel({ evidence }: { evidence: Evidence[] }) {
  return <aside className="evidence-card"><div className="card-head"><span className="evidence-title"><BookOpen size={14} /> SUPPORTING EVIDENCE</span><span className="muted">{evidence.length} passages</span></div>{evidence.length === 0 ? <p className="muted">No supporting passages found.</p> : evidence.map((item, index) => <div className="evidence-item" key={item.id}><div className="evidence-number">{String(index + 1).padStart(2, '0')}</div><div><strong>{item.document_name}</strong><span className="citation">{item.citation} · score {item.score}</span><p>{item.text}</p></div></div>)}</aside>
}

const root = document.getElementById('root')
if (!root) throw new Error('GraphMind root element was not found')
createRoot(root).render(<StrictMode><App /></StrictMode>)

export default App
