/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { storybookTest } from '@storybook/addon-vitest/vitest-plugin';
import { playwright } from '@vitest/browser-playwright';
const dirname = typeof __dirname !== 'undefined' ? __dirname : path.dirname(fileURLToPath(import.meta.url));

// More info at: https://storybook.js.org/docs/next/writing-tests/integrations/vitest-addon
export default defineConfig({
  plugins: [react(), VitePWA({
    registerType: 'autoUpdate',
    includeAssets: ['favicon.svg', 'robots.txt'],
    manifest: {
      name: 'AROL Multi-Agent Platform',
      short_name: 'AROL Agentic',
      description: 'Interfaccia mobile-first per manutenzione macchine AROL',
      theme_color: '#002D54',
      // Blu AROL
      background_color: '#F4F5F7',
      display: 'standalone',
      orientation: 'portrait',
      icons: [{
        src: 'icons/icon-192x192.png',
        sizes: '192x192',
        type: 'image/png'
      }, {
        src: 'icons/icon-512x512.png',
        sizes: '512x512',
        type: 'image/png'
      }]
    }
  })],
  resolve: {
    alias: {
      // Semplifica le importazioni nel codice: import Button from '@/components/ui/Button'
      '@': path.resolve(dirname, './src')
    }
  },
  server: {
    port: 3000,
    host: true // Consente di inquadrare il QR col cellulare reale e testare l'app in locale
  },
  test: {
    projects: [{
      extends: true,
      plugins: [
        // The plugin will run tests for the stories defined in your Storybook config
        // See options at: https://storybook.js.org/docs/next/writing-tests/integrations/vitest-addon#storybooktest
        storybookTest({
          configDir: path.join(dirname, '.storybook')
        })],
      test: {
        name: 'storybook',
        browser: {
          enabled: true,
          headless: true,
          provider: playwright({}),
          instances: [{
            browser: 'chromium'
          }]
        }
      }
    }]
  }
});