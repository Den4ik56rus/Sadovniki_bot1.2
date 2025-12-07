import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import svgr from 'vite-plugin-svgr'
import path from 'path'
import fs from 'fs'

// Читаем версию из package.json
const packageJson = JSON.parse(fs.readFileSync('./package.json', 'utf-8'))
const APP_VERSION = packageJson.version

// https://vite.dev/config/
export default defineConfig({
  // Base path для GitHub Pages (имя репозитория)
  // При деплое на свой домен можно изменить на '/'
  base: process.env.GITHUB_ACTIONS ? '/Sadovniki_bot1.2/' : '/',
  plugins: [
    react(),
    svgr({
      // Использование ?react для импорта SVG как React компонентов
      include: '**/*.svg?react',
    }),
    // Плагин для генерации version.json
    {
      name: 'generate-version-json',
      writeBundle() {
        const versionData = {
          version: APP_VERSION,
          buildTime: new Date().toISOString(),
        }
        fs.writeFileSync('./dist/version.json', JSON.stringify(versionData, null, 2))
        console.log(`✅ Generated version.json with version ${APP_VERSION}`)
      },
    },
  ],
  define: {
    // Инжектим версию в код
    __APP_VERSION__: JSON.stringify(APP_VERSION),
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@store': path.resolve(__dirname, './src/store'),
      '@types': path.resolve(__dirname, './src/types'),
      '@utils': path.resolve(__dirname, './src/utils'),
      '@constants': path.resolve(__dirname, './src/constants'),
      '@services': path.resolve(__dirname, './src/services'),
      '@assets': path.resolve(__dirname, './src/assets'),
    },
  },
  server: {
    port: 5173,
    host: true, // Для доступа с мобильного устройства в локальной сети
  },
})
