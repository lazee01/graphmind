import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiUrl = env.VITE_API_URL || 'https://graphmind-api-zhrf.onrender.com'

  return {
    base: process.env.GITHUB_ACTIONS ? '/graphmind/' : '/',
    plugins: [react()],
    define: {
      // Guarantee API URL is baked in correctly regardless of .env encoding
      'import.meta.env.VITE_API_URL': JSON.stringify(apiUrl),
    },
    build: {
      chunkSizeWarningLimit: 650,
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ['react', 'react-dom', 'lucide-react'],
            firebase: [
              'firebase/app',
              'firebase/auth',
              'firebase/database',
              'firebase/firestore',
              'firebase/analytics',
            ],
          },
        },
      },
    },
  }
})
