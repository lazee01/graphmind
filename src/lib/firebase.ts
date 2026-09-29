// Firebase configuration
// Replace values with your Firebase project config from:
// console.firebase.google.com → Project Settings → Your Apps → Web App → Config

import { initializeApp } from 'firebase/app';
import {
  getAuth,
  GoogleAuthProvider,
  GithubAuthProvider,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  signOut,
  onAuthStateChanged,
  sendPasswordResetEmail,
  updateProfile,
  type User,
} from 'firebase/auth';

// ── Firebase Config ────────────────────────────────────────────────────────
const firebaseConfig = {
  apiKey:            import.meta.env.VITE_FIREBASE_API_KEY            || "PASTE_API_KEY",
  authDomain:        import.meta.env.VITE_FIREBASE_AUTH_DOMAIN        || "PASTE_PROJECT_ID.firebaseapp.com",
  projectId:         import.meta.env.VITE_FIREBASE_PROJECT_ID         || "PASTE_PROJECT_ID",
  storageBucket:     import.meta.env.VITE_FIREBASE_STORAGE_BUCKET     || "PASTE_PROJECT_ID.appspot.com",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "PASTE_SENDER_ID",
  appId:             import.meta.env.VITE_FIREBASE_APP_ID             || "PASTE_APP_ID",
};

const app  = initializeApp(firebaseConfig);
export const auth = getAuth(app);

export const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({ prompt: 'select_account' });
export const githubProvider = new GithubAuthProvider();

export const loginWithEmail    = (email: string, password: string) =>
  signInWithEmailAndPassword(auth, email, password);

export const registerWithEmail = async (email: string, password: string, displayName: string) => {
  const cred = await createUserWithEmailAndPassword(auth, email, password);
  await updateProfile(cred.user, { displayName });
  return cred;
};

export const loginWithGoogle  = () => signInWithPopup(auth, googleProvider);
export const loginWithGitHub  = () => signInWithPopup(auth, githubProvider);
export const logout           = () => signOut(auth);
export const resetPassword    = (email: string) => sendPasswordResetEmail(auth, email);
export const onAuthChange     = (cb: (user: User | null) => void) =>
  onAuthStateChanged(auth, cb);

export type { User };
