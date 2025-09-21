import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/videos': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/metadata': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});


