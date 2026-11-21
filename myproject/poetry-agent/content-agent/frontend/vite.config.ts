import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// The Studio talks only to agent-bff (VITE_AGENT_BFF_URL). It never receives a database credential,
// the Java internal-agent token, or the BFF-to-MCP control token.
export default defineConfig({
  plugins: [react()],
  server: { port: 5190 },
});
