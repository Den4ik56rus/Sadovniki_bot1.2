import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  base: process.env.NODE_ENV === 'production' ? '/Sadovniki_bot1.2/' : '/',
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@store': path.resolve(__dirname, './src/store'),
      '@types': path.resolve(__dirname, './src/types'),
      '@services': path.resolve(__dirname, './src/services'),
    },
  },
  server: {
    port: 5174,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        // SSE (Server-Sent Events) support
        configure: (proxy, _options) => {
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            // Disable buffering for SSE endpoints
            if (req.url?.includes('/events/')) {
              proxyReq.setHeader('Connection', 'keep-alive')
              proxyReq.setHeader('Cache-Control', 'no-cache')
            }
          })
        },
      },
    },
  },
})
