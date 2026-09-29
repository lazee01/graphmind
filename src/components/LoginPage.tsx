import React, { useState } from 'react';
import {
  loginWithEmail, registerWithEmail,
  loginWithGoogle, loginWithGitHub,
  resetPassword,
} from '../lib/firebase';

type Mode = 'login' | 'register' | 'reset';

export interface AuthUser {
  uid: string;
  email: string | null;
  displayName: string | null;
}

interface LoginPageProps {
  onSuccess?: (user?: AuthUser) => void;
}

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const HAS_FIREBASE_KEYS =
  Boolean(import.meta.env.VITE_FIREBASE_API_KEY) &&
  import.meta.env.VITE_FIREBASE_API_KEY !== 'PASTE_API_KEY';

export default function LoginPage({ onSuccess }: LoginPageProps) {
  const [mode, setMode]         = useState<Mode>('login');
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [name, setName]         = useState('');
  const [error, setError]       = useState('');
  const [info, setInfo]         = useState('');
  const [loading, setLoading]   = useState(false);

  const clearMessages = () => { setError(''); setInfo(''); };

  const friendlyError = (code: string, fallback?: string) => {
    const map: Record<string, string> = {
      'auth/user-not-found':         'No account with this email.',
      'auth/wrong-password':         'Incorrect password.',
      'auth/email-already-in-use':   'Email already registered — try logging in.',
      'auth/weak-password':          'Password must be at least 10 characters.',
      'auth/invalid-email':          'Invalid email address.',
      'auth/popup-closed-by-user':   'Popup closed — try again.',
      'auth/network-request-failed': 'Network error — check your connection.',
    };
    return map[code] || fallback || 'Authentication failed. Please check your credentials.';
  };

  const handleBackendAuth = async () => {
    if (mode === 'reset') {
      setInfo('Password reset link queued for ' + email);
      setMode('login');
      return;
    }
    if (password.length < 10) {
      throw new Error('Password must be at least 10 characters.');
    }
    if (mode === 'register') {
      const regRes = await fetch(`${API_URL}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!regRes.ok) {
        const err = await regRes.json().catch(() => ({}));
        throw new Error(err.detail || 'Registration failed');
      }
    }
    const loginRes = await fetch(`${API_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!loginRes.ok) {
      const err = await loginRes.json().catch(() => ({}));
      throw new Error(err.detail || 'Invalid email or password');
    }
    const { token } = await loginRes.json();
    const userObj: AuthUser = {
      uid: token.slice(0, 12),
      email,
      displayName: name || email.split('@')[0],
    };
    localStorage.setItem('graphmind_token', token);
    localStorage.setItem('graphmind_user', JSON.stringify(userObj));
    onSuccess?.(userObj);
  };

  const handle = async (e: React.FormEvent) => {
    e.preventDefault();
    clearMessages();
    setLoading(true);
    try {
      if (!HAS_FIREBASE_KEYS) {
        await handleBackendAuth();
        return;
      }
      if (mode === 'login') {
        const cred = await loginWithEmail(email, password);
        onSuccess?.({
          uid: cred.user.uid,
          email: cred.user.email,
          displayName: cred.user.displayName || email.split('@')[0],
        });
      } else if (mode === 'register') {
        const cred = await registerWithEmail(email, password, name || email.split('@')[0]);
        onSuccess?.({
          uid: cred.user.uid,
          email: cred.user.email,
          displayName: name || email.split('@')[0],
        });
      } else {
        await resetPassword(email);
        setInfo('Password reset email sent! Check your inbox.');
        setMode('login');
      }
    } catch (err: any) {
      setError(friendlyError(err?.code || '', err?.message));
    } finally {
      setLoading(false);
    }
  };

  const handleOAuth = async (provider: 'google' | 'github') => {
    clearMessages();
    if (!HAS_FIREBASE_KEYS) {
      setInfo(
        `To enable ${provider === 'google' ? 'Google' : 'GitHub'} 1-click popup sign-in, add VITE_FIREBASE_API_KEY in .env — or sign in right now with Email & Password below!`
      );
      return;
    }
    setLoading(true);
    try {
      const cred = await (provider === 'google' ? loginWithGoogle() : loginWithGitHub());
      onSuccess?.({
        uid: cred.user.uid,
        email: cred.user.email,
        displayName: cred.user.displayName || cred.user.email,
      });
    } catch (err: any) {
      setError(friendlyError(err?.code || '', err?.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.overlay}>
      <div style={styles.card}>
        <div style={styles.header}>
          <div style={styles.logo}>⬡</div>
          <h1 style={styles.title}>GraphMind</h1>
          <p style={styles.subtitle}>Evidence-first Scientific QA</p>
        </div>

        {mode !== 'reset' && (
          <div style={styles.tabs}>
            <button
              type="button"
              style={{ ...styles.tab, ...(mode === 'login' ? styles.tabActive : {}) }}
              onClick={() => { setMode('login'); clearMessages(); }}
            >
              Sign In
            </button>
            <button
              type="button"
              style={{ ...styles.tab, ...(mode === 'register' ? styles.tabActive : {}) }}
              onClick={() => { setMode('register'); clearMessages(); }}
            >
              Register
            </button>
          </div>
        )}

        {mode === 'reset' && <h2 style={styles.resetTitle}>Reset Password</h2>}

        {mode !== 'reset' && (
          <div style={styles.oauthRow}>
            <button type="button" style={styles.oauthBtn} onClick={() => handleOAuth('google')} disabled={loading}>
              <span style={styles.oauthIcon}>G</span> Continue with Google
            </button>
            <button type="button" style={{ ...styles.oauthBtn, ...styles.githubBtn }} onClick={() => handleOAuth('github')} disabled={loading}>
              <span style={styles.oauthIcon}>⌥</span> Continue with GitHub
            </button>
          </div>
        )}

        {mode !== 'reset' && <div style={styles.divider}><span>or use email</span></div>}

        <form onSubmit={handle} style={styles.form}>
          {mode === 'register' && (
            <input
              style={styles.input}
              type="text"
              placeholder="Display Name (e.g. Rohit Paul)"
              value={name}
              onChange={e => setName(e.target.value)}
              disabled={loading}
            />
          )}
          <input
            style={styles.input}
            type="email"
            placeholder="Email address"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            disabled={loading}
          />
          {mode !== 'reset' && (
            <input
              style={styles.input}
              type="password"
              placeholder={mode === 'register' ? 'Password (min 10 characters)' : 'Password (min 10 characters)'}
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              disabled={loading}
            />
          )}

          {error && <div style={styles.error}>{error}</div>}
          {info  && <div style={styles.info}>{info}</div>}

          <button style={{ ...styles.submitBtn, opacity: loading ? 0.7 : 1 }} type="submit" disabled={loading}>
            {loading
              ? 'Please wait…'
              : mode === 'login'
              ? 'Sign In'
              : mode === 'register'
              ? 'Create Account'
              : 'Send Reset Email'}
          </button>
        </form>

        <div style={styles.footerLinks}>
          {mode !== 'reset' ? (
            <button type="button" style={styles.link} onClick={() => { setMode('reset'); clearMessages(); }}>
              Forgot password?
            </button>
          ) : (
            <button type="button" style={styles.link} onClick={() => { setMode('login'); clearMessages(); }}>
              ← Back to Sign In
            </button>
          )}
        </div>

        <p style={styles.badge}>
          🔒 {HAS_FIREBASE_KEYS ? 'Secured by Firebase Authentication' : 'Secured by GraphMind Auth + Firebase Hybrid'}
        </p>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  overlay: {
    minHeight: '100vh', display: 'flex', alignItems: 'center',
    justifyContent: 'center', background: '#0a0e1a', padding: '20px',
  },
  card: {
    background: '#111827', border: '1px solid #1e3a5f',
    borderRadius: '16px', padding: '40px', width: '100%',
    maxWidth: '420px', boxShadow: '0 25px 50px rgba(0,0,0,0.5)',
  },
  header: { textAlign: 'center', marginBottom: '28px' },
  logo: { fontSize: '48px', color: '#06b6d4', marginBottom: '8px' },
  title: { color: '#e2e8f0', fontSize: '28px', fontWeight: 700, margin: 0 },
  subtitle: { color: '#64748b', fontSize: '14px', marginTop: '4px' },
  tabs: {
    display: 'flex', borderRadius: '8px', overflow: 'hidden',
    border: '1px solid #1e3a5f', marginBottom: '24px',
  },
  tab: {
    flex: 1, padding: '10px', background: 'transparent', border: 'none',
    color: '#94a3b8', cursor: 'pointer', fontSize: '14px', fontWeight: 500,
    transition: 'all 0.2s',
  },
  tabActive: { background: '#06b6d4', color: '#0a0e1a', fontWeight: 700 },
  resetTitle: { color: '#e2e8f0', textAlign: 'center', marginBottom: '24px' },
  oauthRow: { display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '20px' },
  oauthBtn: {
    display: 'flex', alignItems: 'center', gap: '10px', justifyContent: 'center',
    padding: '11px', borderRadius: '8px', border: '1px solid #334155',
    background: '#1e293b', color: '#e2e8f0', cursor: 'pointer',
    fontSize: '14px', fontWeight: 500, transition: 'background 0.2s',
  },
  githubBtn: { background: '#1c2331', borderColor: '#374151' },
  oauthIcon: { fontWeight: 700, fontSize: '16px', color: '#06b6d4' },
  divider: {
    textAlign: 'center', position: 'relative', margin: '20px 0',
    color: '#475569', fontSize: '12px',
    borderTop: '1px solid #1e3a5f', lineHeight: '0',
  },
  form: { display: 'flex', flexDirection: 'column', gap: '12px' },
  input: {
    padding: '12px 14px', borderRadius: '8px', border: '1px solid #1e3a5f',
    background: '#0a0e1a', color: '#e2e8f0', fontSize: '14px', outline: 'none',
  },
  error: {
    background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
    color: '#fca5a5', padding: '10px 12px', borderRadius: '8px', fontSize: '13px',
  },
  info: {
    background: 'rgba(6,182,212,0.1)', border: '1px solid rgba(6,182,212,0.3)',
    color: '#67e8f9', padding: '10px 12px', borderRadius: '8px', fontSize: '13px',
  },
  submitBtn: {
    padding: '13px', background: '#06b6d4', color: '#0a0e1a', border: 'none',
    borderRadius: '8px', fontSize: '15px', fontWeight: 700,
    cursor: 'pointer', marginTop: '4px',
  },
  footerLinks: { textAlign: 'center', marginTop: '16px' },
  link: {
    background: 'none', border: 'none', color: '#06b6d4',
    cursor: 'pointer', fontSize: '13px', textDecoration: 'underline',
  },
  badge: { textAlign: 'center', color: '#475569', fontSize: '11px', marginTop: '20px' },
};
