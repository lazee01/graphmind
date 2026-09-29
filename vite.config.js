import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: process.env.GITHUB_ACTIONS ? '/graphmind/' : '/',
  plugins: [react()],
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
})
