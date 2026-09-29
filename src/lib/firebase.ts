import { initializeApp } from 'firebase/app';
import { getAnalytics, isSupported } from 'firebase/analytics';
import {
  getAuth,
  GoogleAuthProvider,
  GithubAuthProvider,
  TwitterAuthProvider,
  OAuthProvider,
  RecaptchaVerifier,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  signInAnonymously,
  sendSignInLinkToEmail,
  isSignInWithEmailLink,
  signInWithEmailLink,
  signInWithPhoneNumber,
  signOut,
  onAuthStateChanged,
  sendPasswordResetEmail,
  sendEmailVerification,
  updateProfile,
  type ConfirmationResult,
  type User,
} from 'firebase/auth';
import { getDatabase, ref, push, set } from 'firebase/database';
import { getFirestore, collection, addDoc, serverTimestamp } from 'firebase/firestore';

export const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "AIzaSyBuAUbjiOHrUDmRAZkJQeLgXgvonXeK2R8",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "graphmind-001.firebaseapp.com",
  databaseURL: import.meta.env.VITE_FIREBASE_DATABASE_URL || "https://graphmind-001-default-rtdb.firebaseio.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "graphmind-001",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "graphmind-001.firebasestorage.app",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "582020750202",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:582020750202:web:f70c376a5138c1e47014c3",
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID || "G-MB985RLEM4",
};

export const app = initializeApp(firebaseConfig);

export const analyticsPromise = typeof window !== 'undefined'
  ? isSupported().then(yes => (yes ? getAnalytics(app) : null)).catch(() => null)
  : Promise.resolve(null);

export const auth = getAuth(app);
export const rtdb = getDatabase(app);
export const db = getFirestore(app);

// ── OAuth Providers ───────────────────────────────────────────────────────
export const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({ prompt: 'select_account' });

export const githubProvider = new GithubAuthProvider();
export const microsoftProvider = new OAuthProvider('microsoft.com');
export const appleProvider = new OAuthProvider('apple.com');
export const twitterProvider = new TwitterAuthProvider();

// ── 1. Email & Password + Verification + Reset ────────────────────────────
export const loginWithEmail = (email: string, password: string) =>
  signInWithEmailAndPassword(auth, email, password);

export const registerWithEmail = async (email: string, password: string, displayName?: string) => {
  const cred = await createUserWithEmailAndPassword(auth, email, password);
  if (displayName) {
    await updateProfile(cred.user, { displayName });
  }
  await sendEmailVerification(cred.user).catch(() => null);
  return cred;
};

export const resetPassword = (email: string) => sendPasswordResetEmail(auth, email);

// ── 2. Passwordless Magic Email Link ──────────────────────────────────────
export const sendMagicLink = async (email: string) => {
  const actionCodeSettings = {
    url: typeof window !== 'undefined' ? window.location.origin : 'https://web-graphmind.web.app',
    handleCodeInApp: true,
  };
  await sendSignInLinkToEmail(auth, email, actionCodeSettings);
  if (typeof window !== 'undefined') {
    window.localStorage.setItem('graphmind_magic_email', email);
  }
};

export const completeMagicLinkSignIn = async () => {
  if (typeof window === 'undefined' || !isSignInWithEmailLink(auth, window.location.href)) {
    return null;
  }
  const email = window.localStorage.getItem('graphmind_magic_email') || window.prompt('Confirm your email address to complete sign-in:') || '';
  if (!email) return null;
  const result = await signInWithEmailLink(auth, email, window.location.href);
  window.localStorage.removeItem('graphmind_magic_email');
  return result.user;
};

// ── 3. OAuth Popup Sign-In (Google, GitHub, Microsoft, Apple, X) ──────────
export const loginWithGoogle = () => signInWithPopup(auth, googleProvider);
export const loginWithGitHub = () => signInWithPopup(auth, githubProvider);
export const loginWithMicrosoft = () => signInWithPopup(auth, microsoftProvider);
export const loginWithApple = () => signInWithPopup(auth, appleProvider);
export const loginWithTwitter = () => signInWithPopup(auth, twitterProvider);

// ── 4. Phone / SMS OTP Sign-In ────────────────────────────────────────────
let recaptchaVerifier: RecaptchaVerifier | null = null;

export const sendPhoneOtp = async (phoneNumber: string, containerId = 'recaptcha-container'): Promise<ConfirmationResult> => {
  if (!recaptchaVerifier) {
    recaptchaVerifier = new RecaptchaVerifier(auth, containerId, { size: 'invisible' });
  }
  return signInWithPhoneNumber(auth, phoneNumber, recaptchaVerifier);
};

// ── 5. Anonymous / Instant Guest Trial ────────────────────────────────────
export const loginAnonymously = () => signInAnonymously(auth);

// ── Session Management ────────────────────────────────────────────────────
export const logout = () => signOut(auth);
export const onAuthChange = (cb: (user: User | null) => void) =>
  onAuthStateChanged(auth, cb);

export async function syncQueryToFirebase(payload: {
  question: string;
  answer: string;
  confidence: number;
  status: string;
  userEmail?: string | null;
}): Promise<void> {
  const uid = auth.currentUser?.uid || 'anonymous';
  const entry = {
    uid,
    userEmail: payload.userEmail || auth.currentUser?.email || 'guest',
    question: payload.question,
    answer: payload.answer.slice(0, 1200),
    confidence: payload.confidence,
    status: payload.status,
    timestamp: Date.now(),
  };
  try {
    const historyRef = push(ref(rtdb, `workspaces/${uid}/queries`));
    await set(historyRef, entry);
  } catch {
    // Realtime DB non-blocking
  }
  try {
    await addDoc(collection(db, 'queries'), {
      ...entry,
      createdAt: serverTimestamp(),
    });
  } catch {
    // Firestore non-blocking
  }
}

export type { User, ConfirmationResult };
