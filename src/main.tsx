import { ChangeEvent, FormEvent, useEffect, useState } from 'react'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import {
  AlertCircle, ArrowUpRight, BookOpen, CheckCircle2, ChevronRight, CircleDot,
  FileText, GitBranch, LoaderCircle, MessageSquare, Search, Settings2, ShieldCheck,
  Sparkles, Trash2, Upload, X,
} from 'lucide-react'
import {
  loginWithEmail, registerWithEmail, loginWithGoogle, loginWithGitHub, loginWithMicrosoft,
  loginAnonymously, sendMagicLink, completeMagicLinkSignIn, sendPhoneOtp, resetPassword,
  logout as firebaseLogout, onAuthChange, syncQueryToFirebase, type ConfirmationResult,
} from './lib/firebase'
import './styles.css'

type Evidence = { id: string; document_name: string; text: string; page: number | null; section: string; score: number; citation: string }
type Answer = { question?: string; mode?: string; answer: string; confidence: number; status: string; provider: any; evidence: Evidence[]; graph_context: string[]; plan: { question_type: string; entities: string[] }; verification?: { supported: boolean; mode?: string } }
type Document = { id: string; name: string; source: string; chunks: number }
type ChatTurn = { role: 'user' | 'assistant'; content: string; model?: string; confidence?: number; mode?: string }
type ChatSession = { id: string; title: string; updatedAt: number; turns: ChatTurn[]; lastAnswer: Answer | null }

const SESSIONS_KEY = 'graphmind_sessions_v1'

const DEFAULT_API = typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? 'http://127.0.0.1:8000'
  : 'https://graphmind-api-zhrf.onrender.com'
const API = (import.meta.env.VITE_API_URL || DEFAULT_API).replace(/\/$/, '')

const MODEL_OPTIONS = [
  { value: 'auto', label: 'Auto Cascade (GPT-OSS 120B + Gemini 3.8 + Qwen 3.8)' },
  { value: 'openai/gpt-oss-120b', label: 'OpenAI GPT-OSS 120B (Groq Primary)' },
  { value: 'gemini-3.8-flash', label: 'Google Gemini 3.8 Flash' },
  { value: 'qwen/qwen3.8-27b', label: 'Qwen 3.8 27B (Scientific Reasoning)' },
  { value: 'openai/gpt-oss-20b', label: 'OpenAI GPT-OSS 20B (Ultra-Fast)' },
  { value: 'local', label: 'Local Extractive + TF-IDF (Offline Safe)' },
]

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

function loadSavedSessions(): ChatSession[] {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed) && parsed.length > 0) return parsed
    }
  } catch {
    // Ignore storage errors
  }
  return [{ id: 'session-initial', title: 'New Research Thread', updatedAt: Date.now(), turns: [], lastAnswer: null }]
}

function App() {
  const [sessions, setSessions] = useState<ChatSession[]>(() => loadSavedSessions())
  const [activeSessionId, setActiveSessionId] = useState<string>(() => loadSavedSessions()[0].id)
  const [question, setQuestion] = useState('What does GraphMind preserve for each passage?')
  const [mode, setMode] = useState<'rag' | 'hybrid' | 'chat'>('rag')
  const [modelPreference, setModelPreference] = useState<string>('auto')
  const [topK, setTopK] = useState<number>(6)
  const [showEvidenceInChat, setShowEvidenceInChat] = useState<boolean>(false)
  const [documents, setDocuments] = useState<Document[]>([])
  const [selectedDocument, setSelectedDocument] = useState<string | null>(null)
  const [health, setHealth] = useState<{ status: string; chunks: number; provider: { provider?: string; generation_model?: string; gemini_model?: string; active?: boolean; slots?: { name: string; configured: boolean }[] }; neo4j: boolean; agents?: { name: string; mode: string }[] } | null>(null)
  const [offline, setOffline] = useState(false)
  const [busy, setBusy] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [authNotice, setAuthNotice] = useState('')
  const [authOpen, setAuthOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [authMode, setAuthMode] = useState<'login' | 'register' | 'magic' | 'phone' | 'reset'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [phone, setPhone] = useState('')
  const [otpCode, setOtpCode] = useState('')
  const [otpConfirm, setOtpConfirm] = useState<ConfirmationResult | null>(null)
  const [user, setUser] = useState<{ email: string } | null>(null)

  const activeSession = sessions.find((s) => s.id === activeSessionId) || sessions[0]
  const chatHistory = activeSession?.turns || []
  const answer = activeSession?.lastAnswer || null

  useEffect(() => {
    try {
      localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions.slice(0, 25)))
    } catch {
      // Ignore quota errors
    }
  }, [sessions])

  const createNewSession = () => {
    const id = `session-${Date.now()}`
    const fresh: ChatSession = { id, title: 'New Research Thread', updatedAt: Date.now(), turns: [], lastAnswer: null }
    setSessions((prev) => [fresh, ...prev])
    setActiveSessionId(id)
    setQuestion('')
  }

  const removeSession = (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setSessions((prev) => {
      const filtered = prev.filter((s) => s.id !== id)
      if (filtered.length === 0) {
        const fallback: ChatSession = { id: `session-${Date.now()}`, title: 'New Research Thread', updatedAt: Date.now(), turns: [], lastAnswer: null }
        setActiveSessionId(fallback.id)
        return [fallback]
      }
      if (activeSessionId === id) {
        setActiveSessionId(filtered[0].id)
      }
      return filtered
    })
  }

  const appendToActiveSession = (userQ: string, ans: Answer, usedModel: string) => {
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id !== activeSession.id) return s
        const newTurns: ChatTurn[] = [
          ...s.turns,
          { role: 'user', content: userQ, mode },
          { role: 'assistant', content: ans.answer, model: usedModel, confidence: ans.confidence, mode },
        ]
        const newTitle = s.turns.length === 0 ? (userQ.length > 34 ? userQ.slice(0, 34) + '…' : userQ) : s.title
        return { ...s, title: newTitle, updatedAt: Date.now(), turns: newTurns, lastAnswer: ans }
      })
    )
  }

  const clearActiveSessionTurns = () => {
    setSessions((prev) =>
      prev.map((s) => (s.id === activeSession.id ? { ...s, title: 'New Research Thread', turns: [], lastAnswer: null } : s))
    )
  }

  const apiHeaders = (): Record<string, string> => {
    const token = localStorage.getItem('graphmind_token')
    return token ? { Authorization: `Bearer ${token}` } : {}
  }

  useEffect(() => {
    void completeMagicLinkSignIn().then((magicUser) => {
      if (magicUser?.email) setUser({ email: magicUser.email })
    }).catch(() => null)
    const unsub = onAuthChange((fbUser) => {
      if (fbUser) {
        const label = fbUser.email || fbUser.phoneNumber || (fbUser.isAnonymous ? `Guest (${fbUser.uid.slice(0, 5)})` : fbUser.displayName) || 'Authenticated User'
        setUser({ email: label })
        void fbUser.getIdToken().then((t) => localStorage.setItem('graphmind_token', t))
      }
    })
    return () => unsub()
  }, [])

  const loadWorkspace = async () => {
    try {
      const [healthResponse, documentsResponse] = await Promise.all([fetch(`${API}/api/health`), fetch(`${API}/api/documents`, { headers: apiHeaders() })])
      if (!healthResponse.ok || !documentsResponse.ok) throw new Error('API unavailable')
      setHealth(await healthResponse.json())
      setDocuments(await documentsResponse.json())
      setOffline(false)
    } catch {
      setOffline(true)
      setHealth({ status: 'demo', chunks: 7, provider: { provider: 'offline-demo', active: true }, neo4j: false, agents: ['planner', 'retrieval', 'graph', 'verifier', 'generator'].map((name) => ({ name, mode: 'offline-demo' })) })
      setDocuments(DEMO_DOCUMENTS)
    }
  }
  useEffect(() => { void loadWorkspace() }, [])

  const ask = async (event?: FormEvent) => {
    event?.preventDefault()
    const currentQ = question.trim()
    if (!currentQ) return
    setBusy(true); setError('')
    try {
      const response = await fetch(`${API}/api/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...apiHeaders() },
        body: JSON.stringify({
          question: currentQ,
          limit: topK,
          document_id: selectedDocument || undefined,
          mode,
          model_preference: modelPreference,
          history: chatHistory.map((t) => ({ role: t.role, content: t.content })),
        }),
      })
      if (!response.ok) throw new Error((await response.json()).detail || 'Query failed')
      const data: Answer = await response.json()
      const usedModel = modelPreference === 'auto' ? (data.provider?.generation_model || 'GPT-OSS 120B / Gemini 3.8') : modelPreference
      appendToActiveSession(currentQ, data, usedModel)
      if (mode === 'chat') {
        setQuestion('')
      }
      void syncQueryToFirebase({ question: currentQ, answer: data.answer, confidence: data.confidence, status: data.status, userEmail: user?.email })
      if (offline) {
        setOffline(false)
        void loadWorkspace()
      }
    } catch {
      setOffline(true)
      setHealth({ status: 'demo', chunks: 7, provider: { provider: 'offline-demo', active: true }, neo4j: false, agents: ['planner', 'retrieval', 'graph', 'verifier', 'generator'].map((name) => ({ name, mode: 'offline-demo' })) })
      setDocuments(DEMO_DOCUMENTS)
      const fallbackAns = { ...DEMO_ANSWER, question: currentQ }
      appendToActiveSession(currentQ, fallbackAns, 'offline-demo')
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
        const demoId = `demo-upload-${Date.now()}`
        setDocuments((current) => [...current, { id: demoId, name: file.name, source: 'offline demo upload', chunks: 1 }])
        setSelectedDocument(demoId)
        return
      }
      const response = await fetch(`${API}/api/documents`, { method: 'POST', headers: apiHeaders(), body: form })
      if (!response.ok) throw new Error((await response.json()).detail || 'Upload failed')
      const created: Document = await response.json()
      await loadWorkspace()
      if (created?.id) {
        setSelectedDocument(created.id)
      }
    } catch {
      setOffline(true)
      setHealth({ status: 'demo', chunks: 7, provider: { provider: 'offline-demo', active: true }, neo4j: false, agents: ['planner', 'retrieval', 'graph', 'verifier', 'generator'].map((name) => ({ name, mode: 'offline-demo' })) })
      setDocuments((current) => [...current, { id: `demo-upload-${Date.now()}`, name: file.name, source: 'offline demo upload', chunks: 1 }])
    }
    finally { setUploading(false); event.target.value = '' }
  }

  const removeDocument = async (docId: string, e?: React.MouseEvent) => {
    e?.stopPropagation()
    try {
      if (!offline) {
        await fetch(`${API}/api/documents/${docId}`, { method: 'DELETE', headers: apiHeaders() })
      }
      setDocuments((current) => current.filter((d) => d.id !== docId))
      if (selectedDocument === docId) setSelectedDocument(null)
      await loadWorkspace()
    } catch {
      setDocuments((current) => current.filter((d) => d.id !== docId))
    }
  }

  const authenticate = async (event: FormEvent) => {
    event.preventDefault(); setError(''); setAuthNotice('')
    try {
      if (authMode === 'reset') {
        await resetPassword(email)
        setAuthNotice(`Password reset email sent to ${email}. Check your inbox.`)
        setAuthMode('login')
        return
      }
      if (authMode === 'magic') {
        await sendMagicLink(email)
        setAuthNotice(`Magic sign-in link sent to ${email}! Click the link in your email to log in.`)
        return
      }
      if (authMode === 'phone') {
        if (!otpConfirm) {
          const confirmation = await sendPhoneOtp(phone)
          setOtpConfirm(confirmation)
          setAuthNotice(`SMS OTP sent to ${phone}. Enter the 6-digit code below.`)
          return
        } else {
          const cred = await otpConfirm.confirm(otpCode)
          const token = await cred.user.getIdToken()
          localStorage.setItem('graphmind_token', token)
          setUser({ email: cred.user.phoneNumber || phone })
          setOtpConfirm(null)
          setAuthOpen(false)
          return
        }
      }

      try {
        if (authMode === 'register') {
          const cred = await registerWithEmail(email, password, email.split('@')[0])
          const token = await cred.user.getIdToken()
          localStorage.setItem('graphmind_token', token)
          setUser({ email: cred.user.email || email })
          setAuthOpen(false)
          return
        } else {
          const cred = await loginWithEmail(email, password)
          const token = await cred.user.getIdToken()
          localStorage.setItem('graphmind_token', token)
          setUser({ email: cred.user.email || email })
          setAuthOpen(false)
          return
        }
      } catch (fbErr: any) {
        if (fbErr?.code && !String(fbErr.code).includes('operation-not-allowed') && !String(fbErr.code).includes('configuration-not-found')) {
          throw new Error(fbErr.message || 'Firebase authentication failed')
        }
      }

      const response = await fetch(`${API}/api/auth/${authMode}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) })
      if (!response.ok) throw new Error((await response.json()).detail || 'Authentication failed')
      const payload = await response.json()
      if (authMode === 'register') { setAuthMode('login'); setAuthNotice('Account created! Sign in to continue.'); return }
      localStorage.setItem('graphmind_token', payload.access_token); setUser(payload.user); setAuthOpen(false)
    } catch (reason) { setAuthNotice(reason instanceof Error ? reason.message : 'Authentication failed') }
  }

  const signInWithOAuth = async (providerName: 'google' | 'github' | 'microsoft' | 'guest') => {
    setError(''); setAuthNotice('')
    try {
      const cred = providerName === 'google'
        ? await loginWithGoogle()
        : providerName === 'github'
        ? await loginWithGitHub()
        : providerName === 'microsoft'
        ? await loginWithMicrosoft()
        : await loginAnonymously()
      const token = await cred.user.getIdToken()
      localStorage.setItem('graphmind_token', token)
      const label = cred.user.email || cred.user.displayName || (cred.user.isAnonymous ? `Guest (${cred.user.uid.slice(0, 5)})` : 'Authenticated User')
      setUser({ email: label })
      setAuthOpen(false)
    } catch (reason: any) {
      if (providerName === 'guest') {
        const guestEmail = `guest-${Math.random().toString(36).slice(2, 6)}@graphmind.ai`
        setUser({ email: guestEmail })
        setAuthOpen(false)
        return
      }
      setAuthNotice(reason instanceof Error ? reason.message : `${providerName} Sign-In failed`)
    }
  }

  const handleUserClick = async () => {
    if (user) {
      await firebaseLogout().catch(() => null)
      localStorage.removeItem('graphmind_token')
      setUser(null)
    } else {
      setAuthOpen(true)
    }
  }

  const selectedDocObj = documents.find((d) => d.id === selectedDocument)
  const activeModelLabel = MODEL_OPTIONS.find((m) => m.value === modelPreference)?.label.split(' (')[0] || 'Auto Cascade'

  return <div className="app-shell">
    <header className="topbar">
      <a className="logo" href="#top"><span className="logo-mark"><GitBranch size={18} /></span><span>graph<span>mind</span></span></a>
      <nav>
        <a className={mode !== 'chat' ? 'active' : ''} href="#ask" onClick={() => setMode('rag')}>Ask literature</a>
        <a className={mode === 'chat' ? 'active' : ''} href="#ask" onClick={() => setMode('chat')}>AI Chat</a>
        <a href="#library">Library ({documents.length})</a>
        <a href="#method">How it works</a>
      </nav>
      <div className="header-actions">
        <button className="auth-button" onClick={() => setSettingsOpen(true)} title="Project, AI & Library Settings">
          Project settings
        </button>
        <button className="auth-button" onClick={handleUserClick} title={user ? 'Click to sign out' : 'Sign in with Firebase'}>
          {user ? `${user.email} · Sign out` : 'Sign in'}
        </button>
        <button type="button" className={`top-status ${offline ? 'demo-status' : ''}`} onClick={() => setSettingsOpen(true)} title="Open AI & Library Settings">
          <CircleDot size={13} /> {offline ? 'OFFLINE DEMO MODE' : health?.status === 'ok' ? 'API ENGINE READY' : 'CONNECTING'} <Settings2 size={15} />
        </button>
      </div>
    </header>

    {authOpen && (
      <div className="auth-backdrop" onClick={() => setAuthOpen(false)}>
        <form className="auth-card" style={{ width: 'min(460px, 100%)' }} onSubmit={authenticate} onClick={(event) => event.stopPropagation()}>
          <button type="button" className="auth-close" onClick={() => setAuthOpen(false)}><X size={16} /></button>
          <span className="kicker">FIREBASE ENTERPRISE AUTH · GRAPHMIND-001</span>
          <h2>
            {authMode === 'login' ? 'Welcome back.' : authMode === 'register' ? 'Create an account.' : authMode === 'magic' ? 'Magic Email Link.' : authMode === 'phone' ? 'Phone SMS OTP.' : 'Reset Password.'}
          </h2>
          <p>Sign in with OAuth, Email/Password, Passwordless Magic Link, Phone OTP, or Guest Session.</p>

          <div className="mode-pills" style={{ marginBottom: '4px' }}>
            <button type="button" className={`mode-pill ${authMode === 'login' ? 'active' : ''}`} onClick={() => { setAuthMode('login'); setAuthNotice('') }}>Email</button>
            <button type="button" className={`mode-pill ${authMode === 'register' ? 'active' : ''}`} onClick={() => { setAuthMode('register'); setAuthNotice('') }}>Register</button>
            <button type="button" className={`mode-pill ${authMode === 'magic' ? 'active' : ''}`} onClick={() => { setAuthMode('magic'); setAuthNotice('') }}>Magic Link</button>
            <button type="button" className={`mode-pill ${authMode === 'phone' ? 'active' : ''}`} onClick={() => { setAuthMode('phone'); setAuthNotice('') }}>Phone OTP</button>
          </div>

          <div className="provider-grid" style={{ marginBottom: '4px' }}>
            <button type="button" className="auth-button" onClick={() => void signInWithOAuth('google')}>G · Google</button>
            <button type="button" className="auth-button" onClick={() => void signInWithOAuth('github')}>⌥ · GitHub</button>
            <button type="button" className="auth-button" onClick={() => void signInWithOAuth('microsoft')}>⊞ · Microsoft</button>
            <button type="button" className="auth-button" onClick={() => void signInWithOAuth('guest')}>⚡ · Instant Guest</button>
          </div>

          {(authMode === 'login' || authMode === 'register' || authMode === 'magic' || authMode === 'reset') && (
            <input type="email" required placeholder="you@example.com" value={email} onChange={(event) => setEmail(event.target.value)} />
          )}

          {(authMode === 'login' || authMode === 'register') && (
            <input type="password" required minLength={10} placeholder="Password (10+ characters)" value={password} onChange={(event) => setPassword(event.target.value)} />
          )}

          {authMode === 'phone' && (
            <>
              <input type="tel" required placeholder="+91 9876543210 (with country code)" value={phone} onChange={(event) => setPhone(event.target.value)} />
              {otpConfirm && (
                <input type="text" required placeholder="Enter 6-digit SMS OTP code" value={otpCode} onChange={(event) => setOtpCode(event.target.value)} />
              )}
              <div id="recaptcha-container" />
            </>
          )}

          {authNotice && <div className="notice" style={{ marginTop: 0 }}>{authNotice}</div>}

          <button className="auth-submit">
            {authMode === 'login' ? 'Sign in with Email' : authMode === 'register' ? 'Create Account' : authMode === 'magic' ? 'Send Magic Sign-In Link' : authMode === 'phone' ? (otpConfirm ? 'Verify OTP & Sign in' : 'Send SMS OTP') : 'Send Password Reset Email'}
          </button>

          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
            <button type="button" className="auth-switch" onClick={() => { setAuthMode(authMode === 'login' ? 'register' : 'login'); setAuthNotice('') }}>
              {authMode === 'login' ? 'Need an account? Register' : 'Back to Email Sign in'}
            </button>
            {authMode !== 'reset' && (
              <button type="button" className="auth-switch" onClick={() => { setAuthMode('reset'); setAuthNotice('') }}>
                Forgot password?
              </button>
            )}
          </div>
        </form>
      </div>
    )}

    {settingsOpen && (
      <div className="auth-backdrop" onClick={() => setSettingsOpen(false)}>
        <div className="auth-card settings-card" onClick={(event) => event.stopPropagation()}>
          <button type="button" className="auth-close" onClick={() => setSettingsOpen(false)}><X size={16} /></button>
          <span className="kicker">PROJECT, AI & LIBRARY SETTINGS</span>
          <h2>Workspace Control</h2>
          <p>Primary focus: Evidence-first Scientific Literature QA with Hybrid RAG & Knowledge Graphs, plus multi-model AI chat.</p>

          <div className="settings-grid">
            <div className="settings-field">
              <label>PRIMARY RESEARCH MODE</label>
              <select value={mode} onChange={(e) => setMode(e.target.value as 'rag' | 'hybrid' | 'chat')}>
                <option value="rag">Literature RAG + Knowledge Graph (Primary)</option>
                <option value="hybrid">Hybrid RAG + Deep Scientific AI</option>
                <option value="chat">Normal AI Chat (ChatGPT / Gemini style)</option>
              </select>
            </div>

            <div className="settings-field">
              <label>AI MODEL ENGINE (GPT / GEMINI / QWEN)</label>
              <select value={modelPreference} onChange={(e) => setModelPreference(e.target.value)}>
                {MODEL_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>

            <div className="settings-field">
              <label>ACTIVE DOCUMENT SCOPE</label>
              <select value={selectedDocument || ''} onChange={(e) => setSelectedDocument(e.target.value || null)}>
                <option value="">All Indexed Literature ({documents.length} docs)</option>
                {documents.map((doc) => (
                  <option key={doc.id} value={doc.id}>{doc.name} ({doc.chunks} chunks)</option>
                ))}
              </select>
            </div>

            <div className="settings-field">
              <label>EVIDENCE PASSAGES (TOP-K)</label>
              <select value={topK} onChange={(e) => setTopK(Number(e.target.value))}>
                <option value={3}>3 passages (Focused)</option>
                <option value={6}>6 passages (Balanced Default)</option>
                <option value={9}>9 passages (Deep Audit)</option>
                <option value={12}>12 passages (Maximum Recall)</option>
              </select>
            </div>
          </div>

          <div className="settings-field">
            <label>CONNECTED AI & CLOUD PROVIDERS</label>
            <div className="provider-grid">
              <div className="provider-status-item"><span>Groq (GPT-OSS 120B / Qwen 3.8)</span><span className="ok">ACTIVE</span></div>
              <div className="provider-status-item"><span>Google Gemini 3.8 Flash</span><span className="ok">ACTIVE</span></div>
              <div className="provider-status-item"><span>Hugging Face (MiniLM / NER)</span><span className="ok">ACTIVE</span></div>
              <div className="provider-status-item"><span>Firebase (graphmind-001)</span><span className="ok">CONNECTED</span></div>
            </div>
          </div>

          <div className="settings-field">
            <label>DOCUMENT LIBRARY MANAGER ({documents.length} FILES)</label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '150px', overflowY: 'auto' }}>
              {documents.map((doc) => (
                <div key={doc.id} className="provider-status-item">
                  <span>{doc.name} ({doc.chunks} chunks)</span>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button type="button" className="auth-switch" onClick={() => setSelectedDocument(doc.id === selectedDocument ? null : doc.id)}>
                      {selectedDocument === doc.id ? 'Selected ✓' : 'Focus'}
                    </button>
                    <button type="button" className="doc-delete" onClick={(e) => void removeDocument(doc.id, e)} title="Delete document">
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <button type="button" className="auth-submit" onClick={() => setSettingsOpen(false)}>Save & Close Settings</button>
        </div>
      </div>
    )}

    <main id="top">
      <section className="hero">
        <div className="hero-copy"><div className="eyebrow"><Sparkles size={14} /> SCIENTIFIC LITERATURE QA</div><h1>Answers that<br /><em>show their work.</em></h1><p>GraphMind turns dense papers into grounded answers with provenance, hybrid retrieval, and an auditable evidence trail.</p><div className="hero-chips"><span><ShieldCheck size={14} /> Evidence-first</span><span><GitBranch size={14} /> Graph-aware</span><span><CircleDot size={14} /> Multi-Model AI</span></div></div>
        <div className="hero-visual"><div className="halo halo-one" /><div className="halo halo-two" /><div className="visual-core"><GitBranch size={45} /><span>REASON<br />WITH<br />EVIDENCE</span></div><div className="orbit-label label-a">VECTOR</div><div className="orbit-label label-b">GRAPH</div><div className="orbit-label label-c">VERIFY</div></div>
      </section>

      <section className="workspace" id="ask">
        <div className="section-title">
          <div>
            <span className="kicker">01 / RESEARCH CONSOLE</span>
            <h2>{mode === 'chat' ? 'AI Research Chat.' : 'Ask your library.'}</h2>
          </div>
          <span className="muted">
            {mode === 'rag' ? 'PRIMARY: Planner → retrieve → graph → verify → cite' : mode === 'hybrid' ? 'HYBRID: Literature RAG + Frontier AI Synthesis' : 'CHAT: Multi-turn GPT-OSS 120B & Gemini 3.8'}
          </span>
        </div>

        <div className="console-bar">
          <div className="mode-pills">
            <button type="button" className={`mode-pill primary-badge ${mode === 'rag' ? 'active' : ''}`} onClick={() => setMode('rag')}>
              <ShieldCheck size={13} /> Literature RAG <span>(PRIMARY)</span>
            </button>
            <button type="button" className={`mode-pill ${mode === 'hybrid' ? 'active' : ''}`} onClick={() => setMode('hybrid')}>
              <Sparkles size={13} /> Hybrid Research AI
            </button>
            <button type="button" className={`mode-pill ${mode === 'chat' ? 'active' : ''}`} onClick={() => setMode('chat')}>
              <MessageSquare size={13} /> Normal AI Chat (GPT / Gemini)
            </button>
          </div>
          <div className="console-meta">
            <button type="button" className="meta-chip" onClick={() => setSettingsOpen(true)}>
              <Settings2 size={13} /> Model: {activeModelLabel} · Top-{topK}
            </button>
            {selectedDocObj && (
              <button type="button" className="meta-chip" onClick={() => setSelectedDocument(null)} title="Click to search all documents">
                <FileText size={13} /> Scope: {selectedDocObj.name} <X size={12} />
              </button>
            )}
          </div>
        </div>

        <div className="session-bar">
          <button type="button" className="session-new" onClick={createNewSession}>+ New Thread</button>
          {sessions.map((sess) => (
            <div
              key={sess.id}
              className={`session-pill ${sess.id === activeSession.id ? 'active' : ''}`}
              onClick={() => setActiveSessionId(sess.id)}
            >
              <span>{sess.title} ({Math.floor(sess.turns.length / 2)})</span>
              {sessions.length > 1 && (
                <button type="button" className="session-del" onClick={(e) => removeSession(sess.id, e)} title="Delete thread">
                  <X size={11} />
                </button>
              )}
            </div>
          ))}
        </div>

        <form className="query-box" onSubmit={ask}>
          {mode === 'chat' ? <MessageSquare size={20} /> : <Search size={20} />}
          <input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={
              mode === 'chat'
                ? 'Chat with GPT-OSS 120B & Gemini 3.8 (ask anything, follow-ups, code, or science)…'
                : selectedDocObj
                ? `Ask a grounded question about ${selectedDocObj.name}…`
                : 'Ask a question about your indexed papers…'
            }
          />
          <button disabled={busy}>
            {busy ? <LoaderCircle className="spin" size={17} /> : <ArrowUpRight size={17} />} {mode === 'chat' ? 'Send' : 'Ask'}
          </button>
        </form>

        {error && <div className="notice error"><AlertCircle size={17} /> {error}<button onClick={() => setError('')} aria-label="Dismiss"><X size={15} /></button></div>}
        {busy && <div className="loading-card"><LoaderCircle className="spin" size={22} /><div><strong>{mode === 'chat' ? 'Synthesizing response…' : 'Following the evidence trail…'}</strong><span>{mode === 'chat' ? `Running ${activeModelLabel}` : 'Planning sub-queries and scoring passages'}</span></div></div>}

        {mode === 'chat' && !busy && chatHistory.length > 0 && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '14px' }}>
              <span className="muted">THREAD: {activeSession.title.toUpperCase()} ({Math.floor(chatHistory.length / 2)} TURNS)</span>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button type="button" className="meta-chip" onClick={() => setShowEvidenceInChat((v) => !v)}>
                  <BookOpen size={12} /> {showEvidenceInChat ? 'Hide Library Passages' : 'Show Library Passages'}
                </button>
                <button type="button" className="meta-chip" onClick={clearActiveSessionTurns}>
                  <Trash2 size={12} /> Clear Thread
                </button>
              </div>
            </div>
            <div className="chat-thread">
              {chatHistory.map((turn, idx) => (
                <div key={idx} className={`chat-msg ${turn.role}`}>
                  <div className="chat-msg-head">
                    <span>{turn.role === 'user' ? 'YOU' : `GRAPHMIND AI (${turn.model || activeModelLabel})`}</span>
                    {turn.confidence && <span>Confidence {Math.round(turn.confidence * 100)}%</span>}
                  </div>
                  <div className="chat-msg-body">{turn.content}</div>
                </div>
              ))}
            </div>
            {showEvidenceInChat && answer && (
              <div style={{ marginTop: '14px' }}>
                <EvidencePanel evidence={answer.evidence} />
              </div>
            )}
          </div>
        )}

        {mode !== 'chat' && !busy && answer && (
          <div>
            <div className="answer-grid">
              <article className="answer-card">
                <div className="card-head">
                  <span className={`answer-status ${answer.status}`}>
                    <CheckCircle2 size={14} /> {answer.status === 'grounded' ? 'GROUNDED ANSWER' : 'INSUFFICIENT EVIDENCE'}
                  </span>
                  <span className="confidence">Confidence {Math.round(answer.confidence * 100)}%</span>
                </div>
                <p className="answer-text">{answer.answer}</p>
                <div className="answer-meta">
                  <span>Engine: {activeModelLabel}</span>
                  <span>Mode: {mode.toUpperCase()}</span>
                  <span>Question type: {answer.plan.question_type}</span>
                </div>
                {answer.graph_context.length > 0 && (
                  <div className="graph-context">
                    <strong><GitBranch size={14} /> Graph context</strong>
                    {answer.graph_context.map((item) => <span key={item}>{item}</span>)}
                  </div>
                )}
              </article>
              <EvidencePanel evidence={answer.evidence} />
            </div>
            {chatHistory.length > 2 && (
              <div style={{ marginTop: '16px' }}>
                <span className="muted">PREVIOUS QUESTIONS IN THIS THREAD ({Math.floor(chatHistory.length / 2)} TURNS)</span>
                <div className="chat-thread">
                  {chatHistory.slice(0, -2).map((turn, idx) => (
                    <div key={idx} className={`chat-msg ${turn.role}`}>
                      <div className="chat-msg-head">
                        <span>{turn.role === 'user' ? 'YOU' : `GRAPHMIND (${turn.model || activeModelLabel})`}</span>
                      </div>
                      <div className="chat-msg-body">{turn.content}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {!busy && ((mode !== 'chat' && !answer) || (mode === 'chat' && chatHistory.length === 0)) && (
          <div className="empty-state">
            <BookOpen size={25} />
            <strong>{mode === 'chat' ? 'Start a conversation with GraphMind AI' : 'Ask your first question'}</strong>
            <span>
              {mode === 'chat'
                ? 'Powered by OpenAI GPT-OSS 120B, Google Gemini 3.8 Flash & Qwen 3.8 — switch back to Literature RAG anytime.'
                : 'Answers will include ranked passages, section context, and citation-ready metadata.'}
            </span>
          </div>
        )}
      </section>

      <section className="library-section" id="library">
        <div className="section-title">
          <div>
            <span className="kicker">02 / DOCUMENT LIBRARY</span>
            <h2>What GraphMind knows.</h2>
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button type="button" className="auth-button" onClick={() => setSettingsOpen(true)}>
              <Settings2 size={14} /> Library settings
            </button>
            <label className="upload-button">
              <Upload size={16} /> {uploading ? 'Extracting…' : 'Upload PDF or TXT'}
              <input type="file" accept=".pdf,.txt,.md" onChange={upload} disabled={uploading} />
            </label>
          </div>
        </div>
        {selectedDocument && (
          <button className="clear-selection" onClick={() => setSelectedDocument(null)}>
            Querying selected paper ({selectedDocObj?.name}) · Click to search all papers
          </button>
        )}
        <div className="library-grid">
          {documents.map((document) => (
            <div
              className={`document-card ${selectedDocument === document.id ? 'selected' : ''}`}
              key={document.id}
              onClick={() => { setSelectedDocument(document.id === selectedDocument ? null : document.id); window.location.hash = 'ask' }}
            >
              <div className="document-icon"><FileText size={20} /></div>
              <div>
                <strong>{document.name}</strong>
                <span>{document.source === 'demo' ? 'Core knowledge base' : 'Workspace document'} · {document.chunks} chunks</span>
              </div>
              <button
                type="button"
                className="doc-delete"
                onClick={(e) => void removeDocument(document.id, e)}
                title="Remove from Library"
              >
                <Trash2 size={15} />
              </button>
              <ChevronRight size={16} />
            </div>
          ))}
        </div>
      </section>

      <section className="method-section" id="method">
        <div className="section-title">
          <div>
            <span className="kicker">03 / TRANSPARENT BY DESIGN</span>
            <h2>Enterprise-grade architecture.</h2>
          </div>
        </div>
        <div className="method-grid">
          {[['01', 'Ingest', 'Extract text, normalize PDF glyphs, detect sections, and preserve page-level provenance.'], ['02', 'Retrieve', 'Fuse lexical precision with semantic vectors across your selected paper or full library.'], ['03', 'Reason', 'Traverse knowledge graph relationships with multi-agent query decomposition.'], ['04', 'Verify', 'Audit claims with confidence scoring and multi-model synthesis (GPT-OSS 120B, Gemini 3.8 & Qwen 3.8).']].map(([number, title, text]) => (
            <article key={number}><span>{number}</span><h3>{title}</h3><p>{text}</p></article>
          ))}
        </div>
      </section>
    </main>

    <footer>
      <span>GraphMind AI · Enterprise Scientific Intelligence Platform</span>
      <span>{health ? `${health.chunks} indexed chunks · ${activeModelLabel} · ${(health.agents || []).length || 5} active agents` : 'GraphMind Cloud Engine'}</span>
    </footer>
  </div>
}

function EvidencePanel({ evidence }: { evidence: Evidence[] }) {
  return <aside className="evidence-card"><div className="card-head"><span className="evidence-title"><BookOpen size={14} /> SUPPORTING EVIDENCE</span><span className="muted">{evidence.length} passages</span></div>{evidence.length === 0 ? <p className="muted">No supporting passages found.</p> : evidence.map((item, index) => <div className="evidence-item" key={item.id}><div className="evidence-number">{String(index + 1).padStart(2, '0')}</div><div><strong>{item.document_name}</strong><span className="citation">{item.citation} · score {item.score}</span><p>{item.text}</p></div></div>)}</aside>
}

const root = document.getElementById('root')
if (!root) throw new Error('GraphMind root element was not found')
createRoot(root).render(<StrictMode><App /></StrictMode>)

export default App
