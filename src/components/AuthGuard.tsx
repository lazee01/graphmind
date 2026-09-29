import { useState, useEffect, type ReactNode } from 'react';
import { onAuthChange, logout, type User } from '../lib/firebase';
import LoginPage from './LoginPage';

interface AuthGuardProps {
  children: (user: User, onLogout: () => void) => ReactNode;
  requireAuth?: boolean;
}

export default function AuthGuard({ children, requireAuth = true }: AuthGuardProps) {
  const [user, setUser]       = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsub = onAuthChange(u => { setUser(u); setLoading(false); });
    return unsub;
  }, []);

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center',
        justifyContent: 'center', background: '#0a0e1a',
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '48px', color: '#06b6d4', marginBottom: '16px' }}>⬡</div>
          <p style={{ color: '#64748b', fontSize: '14px' }}>Initialising GraphMind…</p>
        </div>
      </div>
    );
  }

  if (requireAuth && !user) {
    return <LoginPage />;
  }

  // If auth not required but user is null, pass a guest user
  const activeUser = user || { displayName: 'Guest', email: '', uid: 'guest' } as User;
  return <>{children(activeUser, logout)}</>;
}
