import React, { useState } from 'react'
import {
  User, Mail, Shield, Clock, MessageSquare, LogOut,
  FileText, Zap, Brain, Globe, Copy, Check, X, ChevronRight,
  Star, BookOpen, Activity
} from 'lucide-react'

interface AccountPanelProps {
  user: { email: string } | null
  onClose: () => void
  onSignOut: () => void
  onSignIn: () => void
  chatHistory: Array<{ role: string; content: string; model?: string }>
  documentsCount: number
  health: { provider?: { provider?: string; generation_model?: string } } | null
}

export default function AccountPanel({
  user, onClose, onSignOut, onSignIn, chatHistory, documentsCount, health
}: AccountPanelProps) {
  const [copied, setCopied] = useState(false)

  const provider = user?.email?.includes('(') ? user.email.split('(')[1]?.replace(')', '') : 'Email'
  const displayEmail = user?.email?.includes('(') ? user.email.split('(')[0].trim() : user?.email || ''
  const isGuest = user?.email?.toLowerCase().includes('guest') || user?.email?.toLowerCase().includes('anonymous')
  const memberSince = localStorage.getItem('graphmind_member_since') || new Date().toISOString()

  if (!localStorage.getItem('graphmind_member_since')) {
    localStorage.setItem('graphmind_member_since', new Date().toISOString())
  }

  const formatDate = (iso: string) => {
    try { return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) }
    catch { return 'Recently' }
  }

  const copyEmail = () => {
    if (displayEmail) {
      navigator.clipboard.writeText(displayEmail).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000) })
    }
  }

  const userMessages = chatHistory.filter(t => t.role === 'user').length
  const aiMessages = chatHistory.filter(t => t.role === 'assistant').length

  const providerColor: Record<string, string> = {
    google: '#4285f4', github: '#6e5494', microsoft: '#00a4ef',
    email: '#06b6d4', guest: '#f59e0b', anonymous: '#f59e0b',
  }
  const chipColor = providerColor[provider?.toLowerCase() || 'email'] || '#06b6d4'

  return (
    <div className="auth-backdrop" onClick={onClose}>
      <div
        className="auth-card"
        style={{ width: 'min(480px, 96vw)', maxHeight: '90vh', overflowY: 'auto', padding: '0' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
          borderBottom: '1px solid #1e3a5f',
          padding: '28px 28px 20px',
          position: 'relative'
        }}>
          <button
            className="auth-close"
            onClick={onClose}
            style={{ position: 'absolute', top: 16, right: 16 }}
          >
            <X size={16} />
          </button>
          <span className="kicker">GRAPHMIND · ACCOUNT</span>

          {user ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 16 }}>
              {/* Avatar */}
              <div style={{
                width: 64, height: 64, borderRadius: '50%',
                background: `linear-gradient(135deg, ${chipColor}33, ${chipColor}88)`,
                border: `2px solid ${chipColor}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 24, fontWeight: 700, color: chipColor, flexShrink: 0
              }}>
                {isGuest ? '👤' : (displayEmail?.[0] || '?').toUpperCase()}
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <h2 style={{ margin: 0, fontSize: 18, color: '#f1f5f9' }}>
                    {isGuest ? 'Guest Session' : displayEmail || 'Signed In'}
                  </h2>
                  <span style={{
                    background: `${chipColor}22`, border: `1px solid ${chipColor}55`,
                    color: chipColor, borderRadius: 20, padding: '2px 10px', fontSize: 11,
                    textTransform: 'uppercase', letterSpacing: 1, fontWeight: 600
                  }}>
                    {provider || 'Email'}
                  </span>
                </div>
                <p style={{ margin: '4px 0 0', color: '#64748b', fontSize: 13 }}>
                  Member since {formatDate(memberSince)}
                </p>
              </div>
            </div>
          ) : (
            <div style={{ marginTop: 16 }}>
              <h2 style={{ margin: 0, color: '#f1f5f9' }}>Not signed in</h2>
              <p style={{ margin: '6px 0 0', color: '#64748b', fontSize: 14 }}>
                Sign in to save your research history and access all features.
              </p>
            </div>
          )}
        </div>

        <div style={{ padding: '20px 28px' }}>
          {user && !isGuest && (
            <>
              {/* Email row */}
              <div style={{
                background: '#0f172a', border: '1px solid #1e293b', borderRadius: 10,
                padding: '14px 16px', marginBottom: 16,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <Mail size={15} color="#06b6d4" />
                  <span style={{ color: '#cbd5e1', fontSize: 14 }}>{displayEmail}</span>
                </div>
                <button
                  onClick={copyEmail}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#475569', padding: 4 }}
                  title="Copy email"
                >
                  {copied ? <Check size={14} color="#22c55e" /> : <Copy size={14} />}
                </button>
              </div>
            </>
          )}

          {/* Stats grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 16 }}>
            {[
              { icon: <MessageSquare size={18} />, label: 'Messages', value: userMessages },
              { icon: <Brain size={18} />, label: 'AI Replies', value: aiMessages },
              { icon: <FileText size={18} />, label: 'Documents', value: documentsCount },
            ].map(({ icon, label, value }) => (
              <div key={label} style={{
                background: '#0f172a', border: '1px solid #1e293b', borderRadius: 10,
                padding: '14px 12px', textAlign: 'center'
              }}>
                <div style={{ color: '#06b6d4', marginBottom: 6 }}>{icon}</div>
                <div style={{ color: '#f1f5f9', fontSize: 22, fontWeight: 700, lineHeight: 1 }}>{value}</div>
                <div style={{ color: '#64748b', fontSize: 11, marginTop: 4 }}>{label}</div>
              </div>
            ))}
          </div>

          {/* Active AI */}
          <div style={{
            background: '#0f172a', border: '1px solid #1e3a5f', borderRadius: 10,
            padding: '14px 16px', marginBottom: 16,
            display: 'flex', alignItems: 'center', gap: 12
          }}>
            <Zap size={16} color="#06b6d4" />
            <div style={{ flex: 1 }}>
              <div style={{ color: '#94a3b8', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1 }}>Active AI Engine</div>
              <div style={{ color: '#f1f5f9', fontSize: 13, fontWeight: 600, marginTop: 2 }}>
                {health?.provider?.generation_model || 'GPT-OSS 120B'} via {health?.provider?.provider || 'Groq'}
              </div>
            </div>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#22c55e' }} />
          </div>

          {/* Features */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ color: '#475569', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>
              Available Features
            </div>
            {[
              { icon: <BookOpen size={14} />, label: 'Literature RAG', desc: 'Evidence-first scientific QA', active: true },
              { icon: <Brain size={14} />, label: 'Hybrid Research AI', desc: 'RAG + Knowledge Graph + LLM', active: true },
              { icon: <MessageSquare size={14} />, label: 'AI Chat', desc: 'GPT-OSS 120B · Gemini 3.8 · Qwen 3.8', active: true },
              { icon: <Globe size={14} />, label: 'Neo4j Knowledge Graph', desc: health?.provider ? 'Connected' : 'Fallback mode', active: true },
              { icon: <Activity size={14} />, label: 'Multi-Agent Pipeline', desc: 'Planner → Retriever → Verifier → Generator', active: true },
              { icon: <Star size={14} />, label: 'PDF / TXT Ingestion', desc: 'Upload research papers instantly', active: true },
            ].map(({ icon, label, desc, active }) => (
              <div key={label} style={{
                display: 'flex', alignItems: 'center', gap: 12, padding: '9px 0',
                borderBottom: '1px solid #0f172a'
              }}>
                <div style={{ color: active ? '#06b6d4' : '#475569', width: 28 }}>{icon}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#e2e8f0', fontSize: 13, fontWeight: 500 }}>{label}</div>
                  <div style={{ color: '#64748b', fontSize: 12 }}>{desc}</div>
                </div>
                <div style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: active ? '#22c55e' : '#475569'
                }} />
              </div>
            ))}
          </div>

          {/* Recent chat history preview */}
          {chatHistory.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <div style={{ color: '#475569', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>
                Recent Conversations
              </div>
              {chatHistory.filter(t => t.role === 'user').slice(-3).reverse().map((t, i) => (
                <div key={i} style={{
                  background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8,
                  padding: '10px 14px', marginBottom: 6,
                  display: 'flex', alignItems: 'center', gap: 10
                }}>
                  <MessageSquare size={12} color="#475569" />
                  <span style={{
                    color: '#94a3b8', fontSize: 13,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1
                  }}>
                    {t.content}
                  </span>
                  <ChevronRight size={12} color="#334155" />
                </div>
              ))}
            </div>
          )}

          {/* Auth actions */}
          {user ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {isGuest && (
                <button
                  className="auth-submit"
                  style={{ background: 'linear-gradient(135deg, #06b6d4, #3b82f6)' }}
                  onClick={() => { onClose(); onSignIn() }}
                >
                  <Shield size={15} style={{ marginRight: 8 }} /> Upgrade to Full Account
                </button>
              )}
              <button
                onClick={onSignOut}
                style={{
                  background: 'none', border: '1px solid #334155', borderRadius: 8,
                  color: '#94a3b8', padding: '12px 16px', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                  fontSize: 14, width: '100%', transition: 'all 0.2s'
                }}
                onMouseOver={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = '#ef4444'; (e.currentTarget as HTMLButtonElement).style.color = '#ef4444' }}
                onMouseOut={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = '#334155'; (e.currentTarget as HTMLButtonElement).style.color = '#94a3b8' }}
              >
                <LogOut size={15} /> Sign Out
              </button>
            </div>
          ) : (
            <button
              className="auth-submit"
              onClick={() => { onClose(); onSignIn() }}
            >
              Sign In to GraphMind
            </button>
          )}

          {/* Footer */}
          <div style={{ textAlign: 'center', marginTop: 16, color: '#334155', fontSize: 11 }}>
            GraphMind AI · Enterprise Scientific Intelligence · v2.0
          </div>
        </div>
      </div>
    </div>
  )
}
